import test from 'node:test';
import assert from 'node:assert/strict';

const shouldRun = process.env.RUN_TAURI_UI_TESTS === '1';
const appPath = process.env.TAURI_APP_PATH;
const driverUrl = process.env.TAURI_DRIVER_URL || 'http://localhost:4444';

test('tauri ui boots and shows core controls', { skip: !shouldRun }, async () => {
  assert.ok(appPath, 'TAURI_APP_PATH must point to the built app binary.');

  const { Builder, By, until } = await import('selenium-webdriver');
  const capabilities = {
    browserName: 'wry',
    'tauri:options': {
      application: appPath
    }
  };

  const driver = await new Builder()
    .usingServer(driverUrl)
    .withCapabilities(capabilities)
    .build();

  try {
    await driver.wait(until.elementLocated(By.id('connect-btn')), 15000);
    await driver.wait(until.elementLocated(By.id('viewer')), 15000);
    const title = await driver.getTitle();
    assert.ok(title.includes('LoCo 3D-Gen'));
  } finally {
    await driver.quit();
  }
});
