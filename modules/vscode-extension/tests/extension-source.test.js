const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const source = fs.readFileSync(
  path.join(__dirname, '..', 'src', 'extension.ts'),
  'utf8'
);

test('extension registers chat webview and commands', () => {
  assert.ok(source.includes('registerWebviewViewProvider'));
  assert.ok(source.includes('locoAgent.chatView'));
  assert.ok(source.includes('registerCommand'));
  assert.ok(source.includes('locoAgent.openChat'));
  assert.ok(source.includes('locoAgent.sendMessage'));
});

test('extension wires diff commands', () => {
  assert.ok(source.includes('locoAgent.acceptPatch'));
  assert.ok(source.includes('locoAgent.rejectPatch'));
  assert.ok(source.includes('locoAgent.viewDiff'));
});
