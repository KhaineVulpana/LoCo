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
  'error-banner',
  'error-banner-text',
  'error-banner-dismiss',
  'prompt-templates',
  'prompt-history',
  'messages',
  'composer',
  'message-input',
  'copy-last-prompt',
  'viewer',
  'viewer-overlay',
  'viewer-overlay-text',
  'viewer-overlay-hint',
  'drop-overlay',
  'toggle-grid',
  'lighting-preset',
  'import-mesh',
  'import-file',
  'export-glb',
  'export-stl',
  'copy-mesh-stats',
  'vertex-count',
  'triangle-count',
  'mesh-status',
  'toast'
];

test('3d-gen desktop UI includes core elements', () => {
  for (const id of requiredIds) {
    assert.ok(html.includes(`id="${id}"`), `Missing element id: ${id}`);
  }
});

test('3d-gen desktop UI loads app module', () => {
  assert.ok(html.includes('script type="module" src="app.js"'));
});
