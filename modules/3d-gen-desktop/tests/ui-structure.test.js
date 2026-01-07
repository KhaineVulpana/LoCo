import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const html = fs.readFileSync(path.join(__dirname, '..', 'ui', 'index.html'), 'utf8');

const requiredIds = [
  'server-url',
  'workspace-path',
  'auth-token',
  'connect-btn',
  'messages',
  'composer',
  'message-input',
  'viewer',
  'viewer-overlay',
  'vertex-count',
  'triangle-count',
  'mesh-status'
];

test('3d-gen desktop UI includes core elements', () => {
  for (const id of requiredIds) {
    assert.ok(html.includes(`id="${id}"`), `Missing element id: ${id}`);
  }
});

test('3d-gen desktop UI loads app module', () => {
  assert.ok(html.includes('script type="module" src="app.js"'));
});
