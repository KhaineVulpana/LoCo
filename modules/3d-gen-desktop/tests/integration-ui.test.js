import test from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { readFile } from 'node:fs/promises';
import { WebSocketServer } from 'ws';

const shouldRun = process.env.RUN_INTEGRATION_TESTS === '1';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const uiDir = path.join(__dirname, '..', 'ui');
const fixturePath = path.join(__dirname, 'fixtures', 'sample-mesh.json');

const CONTENT_TYPES = {
  '.html': 'text/html',
  '.js': 'text/javascript',
  '.css': 'text/css',
  '.json': 'application/json'
};

function readRequestBody(req) {
  return new Promise((resolve) => {
    let body = '';
    req.on('data', (chunk) => {
      body += chunk;
    });
    req.on('end', () => resolve(body));
  });
}

async function serveStatic(req, res) {
  const requestUrl = req.url === '/' ? '/index.html' : req.url;
  const filePath = path.normalize(path.join(uiDir, requestUrl));
  if (!filePath.startsWith(uiDir)) {
    res.writeHead(403);
    res.end('Forbidden');
    return;
  }
  try {
    const data = await readFile(filePath);
    const ext = path.extname(filePath);
    res.writeHead(200, { 'Content-Type': CONTENT_TYPES[ext] || 'application/octet-stream' });
    res.end(data);
  } catch {
    res.writeHead(404);
    res.end('Not found');
  }
}

function createTestServer() {
  const server = http.createServer(async (req, res) => {
    if (req.url === '/v1/workspaces/register' && req.method === 'POST') {
      await readRequestBody(req);
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ id: 'workspace-1' }));
      return;
    }

    if (req.url === '/v1/sessions' && req.method === 'POST') {
      await readRequestBody(req);
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ id: 'session-1', title: 'New chat' }));
      return;
    }

    await serveStatic(req, res);
  });

  const wss = new WebSocketServer({ noServer: true });
  server.on('upgrade', (req, socket, head) => {
    if (req.url && req.url.startsWith('/v1/sessions/')) {
      wss.handleUpgrade(req, socket, head, (ws) => {
        wss.emit('connection', ws);
      });
    } else {
      socket.destroy();
    }
  });

  wss.on('connection', (ws) => {
    ws.send(JSON.stringify({
      type: 'server.hello',
      protocol_version: '1.0.0',
      server_info: { version: 'test' }
    }));

    ws.on('message', (data) => {
      let message = null;
      try {
        message = JSON.parse(data.toString());
      } catch {
        return;
      }

      if (message.type === 'client.ping') {
        ws.send(JSON.stringify({ type: 'server.pong' }));
        return;
      }

      if (message.type === 'client.user_message') {
        const mesh = {
          vertices: [[0, 0, 0], [1, 0, 0], [0, 1, 0]],
          triangles: [[0, 1, 2]]
        };
        const payload = `Here is your mesh:\n\`\`\`json\n${JSON.stringify(mesh)}\n\`\`\``;
        ws.send(JSON.stringify({ type: 'assistant.message_final', message: payload }));
      }
    });
  });

  return new Promise((resolve) => {
    server.listen(0, '127.0.0.1', () => {
      const address = server.address();
      resolve({
        server,
        port: address.port,
        close: () => {
          wss.close();
          server.close();
        }
      });
    });
  });
}

test('integration: connect, chat, import', { skip: !shouldRun }, async () => {
  const { chromium } = await import('playwright');
  const { port, close } = await createTestServer();
  const baseUrl = `http://127.0.0.1:${port}`;

  const browser = await chromium.launch();
  const page = await browser.newPage();

  try {
    await page.goto(`${baseUrl}/index.html`, { waitUntil: 'networkidle' });
    await page.fill('#server-url', baseUrl);
    await page.fill('#workspace-path', 'C:\\Temp\\mesh');
    await page.click('#connect-btn');
    await page.waitForSelector('#status-pill.online', { timeout: 5000 });

    await page.fill('#message-input', 'Generate a mesh');
    await page.click('button[type=\"submit\"]');
    await page.waitForFunction(() => {
      const status = document.querySelector('#mesh-status');
      return status && status.textContent === 'ready';
    }, { timeout: 5000 });

    const vertexText = await page.textContent('#vertex-count');
    assert.equal(vertexText.trim(), '3');

    await page.setInputFiles('#import-file', fixturePath);
    await page.waitForFunction(() => {
      const status = document.querySelector('#mesh-status');
      return status && status.textContent === 'ready';
    });
  } finally {
    await browser.close();
    close();
  }
});
