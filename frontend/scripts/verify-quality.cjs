const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const base = process.env.M10_BASE_URL || 'http://127.0.0.1:5173';
const output = process.env.M10_OUTPUT_DIR || path.resolve(__dirname, '../../docs/final');
const result = { renderer: null, samples: [], checks: [], errors: [], notes: ['Scene-only read-only test: no simulation start/reset/control calls.', 'FPS uses the recorded viewport and renderer; software-rendering results are not hardware GPU performance.'] };
const pass = (name, details) => { result.checks.push({ name, details }); console.log('PASS', name); };
const selector = '[data-testid="twin-scene"]';
const debug = page => page.locator(selector).evaluate(el => el.__twinDebug);
const resources = d => ({ geometry: d.geometries, material: d.materialCount, texture: d.textures });
let browser;
(async () => {
  fs.mkdirSync(output, { recursive: true });
  browser = await chromium.launch({ executablePath: process.env.CHROME_PATH || '/opt/google/chrome/chrome', headless: true, args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
  page.on('pageerror', error => result.errors.push(error.message));
  page.on('console', message => { if (message.type() === 'error') result.errors.push(message.text()); });
  await page.goto(base + '/dashboard');
  await page.waitForFunction(s => document.querySelector(s)?.__twinDebug?.fps > 0, selector);
  assert.equal((await debug(page)).quality, 'medium');
  assert.equal(await page.getByTestId('scene-fps').count(), 0);
  await page.locator(selector).evaluate(el => { window.__qualityCanvas = el.querySelector('canvas'); });
  result.renderer = await page.locator(selector + ' canvas').evaluate(canvas => { const gl = canvas.getContext('webgl2'), ext = gl.getExtension('WEBGL_debug_renderer_info'); return ext ? gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) : 'extension unavailable'; });
  const quality = async value => {
    await page.getByTestId('scene-quality').selectOption(value);
    await page.waitForFunction(({ s, value }) => document.querySelector(s)?.__twinDebug?.quality === value, { s: selector, value });
    await page.waitForTimeout(350);
    assert(await page.locator(selector).evaluate(el => window.__qualityCanvas === el.querySelector('canvas')));
    return debug(page);
  };
  for (const viewport of [{ width: 1920, height: 1080 }, { width: 1440, height: 900 }]) {
    await page.setViewportSize(viewport);
    for (const level of ['high', 'medium', 'low']) {
      const d = await quality(level);
      assert.equal(d.profile.shadow.enabled, level !== 'low');
      assert.equal(d.profile.shadow.size, level === 'high' ? 1024 : 512);
      assert.equal(d.profile.rainCapacity, 1800);
      assert.equal(d.profile.rainBudget, { high: 1800, medium: 1000, low: 450 }[level]);
      assert.equal(d.profile.postprocessing.enabled, level !== 'low');
      assert.equal(d.profile.postprocessing.active, false);
      await page.waitForTimeout(1000);
      const frames = await page.evaluate(async () => {
        const intervals = []; let previous;
        await new Promise(resolve => { const start = performance.now(); function sample(now) { if (previous !== undefined) intervals.push(now - previous); previous = now; if (now - start >= 5000) resolve(); else requestAnimationFrame(sample); } requestAnimationFrame(sample); });
        const sorted = [...intervals].sort((a, b) => a - b);
        return { wallTimeMs: intervals.reduce((a, b) => a + b, 0), count: intervals.length, meanFPS: intervals.length * 1000 / intervals.reduce((a, b) => a + b, 0), p95FrameMs: sorted[Math.min(sorted.length - 1, Math.floor(sorted.length * .95))] };
      });
      const latest = await debug(page);
      const box = await page.locator(selector).boundingBox();
      result.samples.push({ viewport, quality: level, sceneSize: { width: box.width, height: box.height }, frames, fpsCounter: latest.fps, drawCalls: latest.drawCalls, triangles: latest.triangles, resources: resources(latest), profile: latest.profile });
    }
  }
  await quality('high');
  await page.getByRole('button', { name: '地下', exact: true }).click();
  assert.equal((await debug(page)).profile.shadow.enabled, false);
  await page.getByRole('button', { name: '地上', exact: true }).click();
  await page.waitForTimeout(300);
  await quality('medium');
  const candidate = (await debug(page)).objects.find(object => object.id === 'A-OFFICE' && object.visible);
  assert(candidate, 'known office mesh remains visible');
  await page.mouse.click(candidate.screen.x, candidate.screen.y);
  await page.waitForFunction(s => document.querySelector(s)?.__twinDebug?.selectedId === 'A-OFFICE' && !document.querySelector(s).__twinDebug.isAnimating, selector);
  const outlined = await quality('high');
  assert.equal(outlined.profile.postprocessing.active, true);
  const lowSelected = await quality('low');
  assert.equal(lowSelected.selectedId, 'A-OFFICE');
  assert.equal(lowSelected.profile.postprocessing.active, false);
  assert(lowSelected.profile.labels.critical >= 1, 'selected object label remains available in low quality');
  pass('low skips selected-object postprocessing while preserving selection and its label', { high: outlined.profile.postprocessing, low: lowSelected.profile.postprocessing });
  await page.getByRole('button', { name: '关闭详情', exact: true }).click();
  await page.getByRole('button', { name: '恢复视角', exact: true }).click();
  await page.waitForFunction(s => !document.querySelector(s)?.__twinDebug?.isAnimating, selector);
  await quality('medium');
  const warm = resources(await debug(page));
  for (let cycle = 0; cycle < 8; cycle++) for (const level of ['low', 'high', 'medium']) await quality(level);
  await page.waitForTimeout(400);
  const after = resources(await debug(page));
  assert.deepEqual(after, warm);
  pass('24 quality switches reuse one canvas and stable resources; underground disables shadows', { before: warm, after });
  const weatherFixture = await page.evaluate(async () => {
    const { RainEffect } = await import('/src/three/effects/RainEffect.ts');
    const rain = new RainEffect(), geometry = rain.object.geometry, buffer = geometry.getAttribute('position').array;
    const counts = [];
    for (const capacity of [1800, 1000, 450, 1800]) { rain.setParticleLimit(capacity); rain.updateWeather({ condition: 'rain', rainfall: 110, windSpeed: 4 }); counts.push({ capacity, count: rain.count, vertices: geometry.drawRange.count }); }
    const same = geometry === rain.object.geometry && buffer === rain.object.geometry.getAttribute('position').array; rain.dispose(); return { counts, same };
  });
  assert(weatherFixture.same); assert.deepEqual(weatherFixture.counts.map(c => c.count), [1800, 1000, 450, 1800]);
  pass('isolated rain visual fixture changes draw range, preserves one pool; no telemetry writes', weatherFixture);
  await page.setViewportSize({ width: 1920, height: 1080 });
  await page.screenshot({ path: path.join(output, 'M10-quality-medium.png') });
  const highDPR = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
  await highDPR.goto(base + '/dashboard?debug=1');
  await highDPR.waitForFunction(s => document.querySelector(s)?.__twinDebug?.fps > 0, selector);
  const ratios = [];
  for (const level of ['high', 'medium', 'low']) { await highDPR.getByTestId('scene-quality').selectOption(level); await highDPR.waitForTimeout(200); ratios.push((await debug(highDPR)).profile.pixelRatio); }
  assert.deepEqual(ratios, [2, 1.5, 1]);
  assert(await highDPR.getByTestId('scene-fps').isVisible());
  pass('DPR2 display obeys caps 2/1.5/1; FPS shown only with debug query', { ratios });
  await highDPR.close();
  await page.close();
  assert.deepEqual(result.errors, []);
  fs.writeFileSync(path.join(output, 'M10-quality-results.json'), JSON.stringify(result, null, 2));
  await browser.close();
})().catch(async error => { result.failure = error.stack; fs.mkdirSync(output, { recursive: true }); fs.writeFileSync(path.join(output, 'M10-quality-results.json'), JSON.stringify(result, null, 2)); console.error(error); await browser?.close(); process.exitCode = 1; });
