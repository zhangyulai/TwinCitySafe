/* Verifies that the shared GIS layer is rendered inside the six-panel app. */
const { chromium } = require('playwright');
const assert = require('node:assert/strict');

(async () => {
  const base = process.env.GIS_BASE_URL || 'http://127.0.0.1:5173';
  const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROME_PATH || '/usr/bin/google-chrome', args: ['--use-angle=swiftshader'] });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto(`${base}/dashboard`, { waitUntil: 'networkidle' });
  await page.getByTestId('twin-scene').waitFor();
  await page.locator('[data-testid="twin-scene"] canvas').waitFor({ state: 'visible', timeout: 30000 });
  await page.locator('.twin-gis-status').waitFor({ state: 'visible', timeout: 20000 });
  const result = await page.evaluate(() => ({
    navigation: [...document.querySelectorAll('.workspace-navigation a')].map(item => item.textContent?.trim()),
    canvas: !!document.querySelector('[data-testid="twin-scene"] canvas'),
    source: document.querySelector('.twin-gis-status')?.textContent?.trim(),
    title: document.querySelector('.twin-title')?.textContent?.trim(),
  }));
  assert.equal(result.navigation.length, 6, 'six business panels remain available');
  assert.equal(result.navigation.some(item => item?.includes('园区 GIS')), false, 'GIS is shared, not a seventh business panel');
  assert.equal(result.canvas, true, 'shared Three.js canvas is visible');
  assert.match(result.source || '', /GIS/, 'shared GIS source is disclosed');
  assert.match(result.title || '', /GIS|数字孪生/, 'scene describes the GIS base');
  assert.equal(errors.length, 0, errors.join('\n'));
  console.log(JSON.stringify({ result, errors }, null, 2));
  await browser.close();
})().catch(error => { console.error(error); process.exitCode = 1; });
