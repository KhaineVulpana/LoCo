const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const pkg = require(path.join(__dirname, '..', 'package.json'));

test('extension package has activation events', () => {
  assert.ok(Array.isArray(pkg.activationEvents));
  assert.ok(pkg.activationEvents.length > 0);
});

test('extension contributes core commands', () => {
  const commands = pkg.contributes?.commands || [];
  const commandIds = commands.map((cmd) => cmd.command);
  assert.ok(commandIds.includes('locoAgent.openChat'));
  assert.ok(commandIds.includes('locoAgent.sendMessage'));
});

test('extension exposes serverUrl setting', () => {
  const settings = pkg.contributes?.configuration?.properties || {};
  assert.ok(settings['locoAgent.serverUrl']);
  assert.equal(settings['locoAgent.serverUrl'].default, 'http://localhost:3199');
});

test('extension exposes authEnabled setting', () => {
  const settings = pkg.contributes?.configuration?.properties || {};
  assert.ok(settings['locoAgent.authEnabled']);
  assert.equal(settings['locoAgent.authEnabled'].default, false);
});

test('extension modelProvider enum includes ollama', () => {
  const settings = pkg.contributes?.configuration?.properties || {};
  const provider = settings['locoAgent.modelProvider'];
  assert.ok(provider);
  assert.ok(provider.enum.includes('ollama'));
});
