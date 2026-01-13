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

test('extension exposes includeWorkspaceRag setting', () => {
  const settings = pkg.contributes?.configuration?.properties || {};
  assert.ok(settings['locoAgent.includeWorkspaceRag']);
  assert.equal(settings['locoAgent.includeWorkspaceRag'].default, true);
});

test('extension exposes autoIndexWorkspace setting', () => {
  const settings = pkg.contributes?.configuration?.properties || {};
  assert.ok(settings['locoAgent.autoIndexWorkspace']);
  assert.equal(settings['locoAgent.autoIndexWorkspace'].default, false);
});

test('extension exposes autoWatchWorkspace setting', () => {
  const settings = pkg.contributes?.configuration?.properties || {};
  assert.ok(settings['locoAgent.autoWatchWorkspace']);
  assert.equal(settings['locoAgent.autoWatchWorkspace'].default, true);
});

test('extension exposes usePollingWatcher setting', () => {
  const settings = pkg.contributes?.configuration?.properties || {};
  assert.ok(settings['locoAgent.usePollingWatcher']);
  assert.equal(settings['locoAgent.usePollingWatcher'].default, false);
});

test('extension modelProvider enum includes ollama', () => {
  const settings = pkg.contributes?.configuration?.properties || {};
  const provider = settings['locoAgent.modelProvider'];
  assert.ok(provider);
  assert.ok(provider.enum.includes('ollama'));
});

test('extension exposes workspace policy settings', () => {
  const settings = pkg.contributes?.configuration?.properties || {};
  assert.ok(settings['locoAgent.policy.commandApproval']);
  assert.ok(settings['locoAgent.policy.allowedCommands']);
  assert.ok(settings['locoAgent.policy.blockedCommands']);
  assert.ok(settings['locoAgent.policy.allowedReadGlobs']);
  assert.ok(settings['locoAgent.policy.allowedWriteGlobs']);
  assert.ok(settings['locoAgent.policy.blockedGlobs']);
  assert.ok(settings['locoAgent.policy.networkEnabled']);
  assert.ok(settings['locoAgent.policy.autoApproveSimpleChanges']);
  assert.ok(settings['locoAgent.policy.autoApproveTests']);
  assert.ok(settings['locoAgent.policy.autoApproveTools.readFile']);
  assert.ok(settings['locoAgent.policy.autoApproveTools.writeFile']);
  assert.ok(settings['locoAgent.policy.autoApproveTools.listFiles']);
  assert.ok(settings['locoAgent.policy.autoApproveTools.applyPatch']);
  assert.ok(settings['locoAgent.policy.autoApproveTools.proposePatch']);
  assert.ok(settings['locoAgent.policy.autoApproveTools.proposeDiff']);
  assert.ok(settings['locoAgent.policy.autoApproveTools.reportPlan']);
  assert.ok(settings['locoAgent.policy.autoApproveTools.runCommand']);
  assert.ok(settings['locoAgent.policy.autoApproveTools.runTests']);
});
