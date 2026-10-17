const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const path = require('node:path');
const fs = require('node:fs');

// Development-server browser acceptance. Run npm run test:web3d from frontend/.
const baseURL = process.env.M1_BASE_URL || 'http://127.0.0.1:5173';
const screenshotDir = process.env.M1_SCREENSHOT_DIR || path.resolve(__dirname, '../../docs');
const software = process.env.M1_SOFTWARE_WEBGL === '1';
const sceneSelector = '[data-testid="twin-scene"]';
const results = { renderer: null, checks: [], screenshots: [], warnings: [], errors: [] };
let browser;
const pass = (name, detail) => { results.checks.push({ name, detail }); console.log('PASS', name, detail || ''); };
const numeric = value => Array.isArray(value) ? value : [value.x, value.y, value.z];
const distance = (a, b) => Math.hypot(...numeric(a).map((n, i) => n - numeric(b)[i]));

async function verifyContextRecovery(page) {
  const selectable = await page.locator(sceneSelector).evaluate(el => el.__twinDebug.objects.find(item => item.visible && item.id === 'A-OFFICE'));
  await page.mouse.click(selectable.screen.x, selectable.screen.y);
  await page.waitForFunction(({ selector, id }) => document.querySelector(selector)?.dataset.selected === id, { selector: sceneSelector, id: selectable.id });
  await page.evaluate(selector => {
    const canvas = document.querySelector(selector).querySelector('canvas');
    window.__m1RecoveryOldCanvas = canvas;
    window.__m1RecoveryOldContext = canvas.getContext('webgl2');
    window.__m1RecoveryOldContext.getExtension('WEBGL_lose_context').loseContext();
  }, sceneSelector);
  await page.getByRole('alert').filter({ hasText: '场景加载异常' }).waitFor();
  await page.waitForFunction(() => !window.__m1Probe || window.__m1Probe.pending.size === 0);
  await page.getByRole('button', { name: '重新加载场景', exact: true }).click();
  await page.waitForFunction(selector => document.querySelector(selector)?.__twinDebug?.drawCalls > 0, sceneSelector);
  await page.getByRole('alert').waitFor({ state: 'hidden' });
  await page.getByTestId('building-details').waitFor({ state: 'hidden' });
  const recovered = await page.evaluate(selector => {
    const host = document.querySelector(selector);
    const canvas = host.querySelector('canvas');
    return {
      canvasCount: host.querySelectorAll('canvas').length,
      selected: host.dataset.selected,
      debugSelected: host.__twinDebug.selectedId,
      oldContextLost: window.__m1RecoveryOldContext.isContextLost(),
      oldCanvasDetached: !window.__m1RecoveryOldCanvas.isConnected,
      currentContextActive: !canvas.getContext('webgl2').isContextLost(),
      activeContexts: window.__m1Probe?.contexts.filter(item => !item.context.isContextLost()).length,
    };
  }, sceneSelector);
  assert.equal(recovered.canvasCount, 1);
  assert.equal(recovered.selected, '');
  assert(!recovered.debugSelected);
  assert.equal(recovered.oldContextLost, true);
  assert.equal(recovered.oldCanvasDetached, true);
  assert.equal(recovered.currentContextActive, true);
  if (recovered.activeContexts !== undefined) assert.equal(recovered.activeContexts, 1);
  return recovered;
}
module.exports = { verifyContextRecovery };

if (require.main === module) (async () => {
  browser = await chromium.launch({
    executablePath: process.env.CHROME_PATH || (fs.existsSync('/opt/google/chrome/chrome') ? '/opt/google/chrome/chrome' : undefined), headless: true,
    args: software ? ['--use-angle=swiftshader', '--enable-unsafe-swiftshader'] : [],
  });
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
  page.on('pageerror', error => results.errors.push(error.message));
  page.on('console', message => {
    if (message.type() === 'warning' || message.type() === 'warn') results.warnings.push(message.text());
    if (message.type() === 'error') results.errors.push(message.text());
  });
  await page.addInitScript(() => {
    const pending = new Set();
    const nativeRequest = window.requestAnimationFrame.bind(window);
    const nativeCancel = window.cancelAnimationFrame.bind(window);
    window.requestAnimationFrame = callback => {
      const id = nativeRequest(time => { pending.delete(id); callback(time); });
      pending.add(id);
      return id;
    };
    window.cancelAnimationFrame = id => { pending.delete(id); nativeCancel(id); };
    const contexts = [];
    const nativeGetContext = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = function(kind, ...args) {
      const context = nativeGetContext.call(this, kind, ...args);
      if (context && /webgl/.test(kind) && !contexts.some(record => record.context === context)) {
        contexts.push({ canvas: this, context });
      }
      return context;
    };
    window.__m1Probe = { pending, contexts, lastScene: null };
  });
  const debug = () => page.locator(sceneSelector).evaluate(el => el.__twinDebug);
  const settle = () => page.waitForFunction(selector => {
    const debug = document.querySelector(selector)?.__twinDebug;
    return debug && !debug.isAnimating;
  }, sceneSelector, { timeout: 12000 });
  const screenshot = async name => {
    const file = path.join(screenshotDir, `M1-${name}.png`);
    await page.screenshot({ path: file, fullPage: true });
    results.screenshots.push(file);
  };
  const nav = label => page.getByRole('navigation').getByRole('link', { name: new RegExp(label) });
  const reset = async () => {
    await page.getByRole('button', { name: '恢复视角', exact: true }).click();
    await settle();
  };
  const clickBuilding = async excludedId => {
    const objects = (await debug()).objects;
    for (const object of objects) {
      if (object.id === excludedId || !object.visible || !object.screen) continue;
      const { x, y } = object.screen;
      const box = await page.locator(sceneSelector).boundingBox();
      if (x < box.x + 25 || x > box.x + box.width - 25 || y < box.y + 65 || y > box.y + box.height - 45) continue;
      await page.mouse.move(x, y);
      try {
        await page.waitForFunction(({ selector, id }) => document.querySelector(selector)?.__twinDebug?.hoveredId === id,
          { selector: sceneSelector, id: object.id }, { timeout: 1400 });
      } catch { continue; }
      assert.equal(await page.locator(sceneSelector + ' canvas').evaluate(el => getComputedStyle(el).cursor), 'pointer');
      const before = await debug();
      await page.evaluate(selector => {
        window.__m1TweenSamples = [];
        window.__m1TweenTimer = setInterval(() => {
          const d = document.querySelector(selector)?.__twinDebug;
          if (d) window.__m1TweenSamples.push({ time: performance.now(), position: d.cameraPosition, target: d.target, active: d.isAnimating });
        }, 50);
      }, sceneSelector);
      await page.mouse.click(x, y);
      await page.waitForFunction(({ selector, id }) => document.querySelector(selector)?.dataset.selected === id,
        { selector: sceneSelector, id: object.id });
      const start = await debug();
      await settle();
      const end = await debug();
      const samples = await page.evaluate(() => { clearInterval(window.__m1TweenTimer); return window.__m1TweenSamples; });
      assert(start.isAnimating || samples.some(sample => sample.active), 'building click starts a camera tween');
      assert(distance(before.cameraPosition, end.cameraPosition) > 0.1, 'focus camera moves');
      assert(samples.some(sample => distance(sample.position, before.cameraPosition) > 0.01 && distance(sample.position, end.cameraPosition) > 0.01), 'camera has intermediate tween position');
      await page.getByTestId('building-details').waitFor();
      const details = await page.getByTestId('building-details').innerText();
      assert(details.includes(object.name), 'details names the clicked building');
      assert.match(details, /建筑面积|面积/);
      assert.match(details, /楼层/);
      assert.match(details, /设备/);
      assert.match(details, /告警/);
      assert.match(details, /安全指数/);
      pass('mesh hover, click, metadata and camera tween', { id: object.id, cameraMoved: distance(before.cameraPosition, end.cameraPosition), targetMoved: distance(before.target, end.target), tweenSamples: samples.length, activeSamples: samples.filter(sample => sample.active).length });
      return object.id;
    }
    throw new Error('No real mesh could be selected at the projected building-body coordinates');
  };

  await page.goto(baseURL + '/review');
  // Health now initializes at App level, including direct non-Dashboard entry.
  await page.getByRole('button', { name: '后端服务：Online', exact: true }).waitFor();
  await page.getByRole('button', { name: '后端服务：Online', exact: true }).waitFor();
  await page.waitForTimeout(350);
  const baselineRAF = await page.evaluate(() => window.__m1Probe.pending.size);
  pass('M0 backend Online before scene mount', { baselineRAF });
  await nav('综合态势').click();
  await page.locator(sceneSelector + ' canvas').waitFor();
  await page.waitForFunction(selector => !!document.querySelector(selector)?.__twinDebug, sceneSelector);
  await settle();
  await page.waitForFunction(selector => document.querySelector(selector)?.__twinDebug?.drawCalls > 0, sceneSelector);
  assert.equal(await page.locator(sceneSelector + ' canvas').count(), 1);
  const initial = await debug();
  assert.equal(initial.mode, 'above');
  assert(initial.objects.filter(o => o.visible).length >= 4, 'at least four visible buildings');
  assert(initial.pipelineCount >= 3, 'three pipeline demo classes');
  assert.match(JSON.stringify(initial.devices), /P01/i);
  assert.match(JSON.stringify(initial.devices), /P02/i);
  assert.match(JSON.stringify(initial.devices), /P03/i);
  const labels = page.locator('.twin-label[data-building-id]');
  assert(await labels.count() >= 4, 'major buildings have CSS2D labels');
  assert.equal(await labels.first().evaluate(el => getComputedStyle(el).pointerEvents), 'none');
  const renderer = await page.evaluate(() => {
    const record = window.__m1Probe.contexts.at(-1);
    const gl = record.context;
    const extension = gl.getExtension('WEBGL_debug_renderer_info');
    return { vendor: extension ? gl.getParameter(extension.UNMASKED_VENDOR_WEBGL) : gl.getParameter(gl.VENDOR),
      renderer: extension ? gl.getParameter(extension.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER),
      version: gl.getParameter(gl.VERSION), activeContexts: window.__m1Probe.contexts.filter(item => !item.context.isContextLost()).length };
  });
  results.renderer = renderer;
  pass('real WebGL canvas, building labels, pipeline and device inventory', { renderer, stats: { drawCalls: initial.drawCalls, triangles: initial.triangles, geometries: initial.geometries, textures: initial.textures } });
  await screenshot('above');

  const canvas = page.locator(sceneSelector + ' canvas');
  const box = await canvas.boundingBox();
  const dragX = box.x + box.width * 0.72;
  const dragY = box.y + box.height * 0.76;
  const beforeDrag = await debug();
  await page.mouse.move(dragX, dragY);
  await page.mouse.down();
  await page.mouse.move(dragX + 70, dragY - 30, { steps: 12 });
  await page.mouse.up();
  await page.waitForTimeout(350);
  const afterDrag = await debug();
  assert(distance(beforeDrag.cameraPosition, afterDrag.cameraPosition) > 0.1, 'drag rotates camera');
  await page.mouse.wheel(0, -250);
  await page.waitForTimeout(350);
  const afterZoom = await debug();
  assert(Math.abs(distance(afterZoom.cameraPosition, afterZoom.target) - distance(afterDrag.cameraPosition, afterDrag.target)) > 0.1, 'wheel changes camera distance');
  await page.mouse.down({ button: 'right' });
  await page.mouse.move(dragX + 110, dragY - 30, { steps: 10 });
  await page.mouse.up({ button: 'right' });
  await page.waitForTimeout(350);
  const afterPan = await debug();
  assert(distance(afterZoom.target, afterPan.target) > 0.1, 'right drag pans target');
  await reset();
  assert(distance(initial.cameraPosition, (await debug()).cameraPosition) < 0.02, 'reset restores overview camera');
  pass('OrbitControls rotation, wheel zoom, pan and reset');

  const selected1 = await clickBuilding();
  const focusBox = await canvas.boundingBox();
  await page.mouse.move(focusBox.x + focusBox.width * 0.12, focusBox.y + focusBox.height * 0.45);
  await page.mouse.wheel(0, 300);
  await page.waitForTimeout(250);
  const beforeFocusButton = await debug();
  await page.getByRole('button', { name: '聚焦建筑', exact: true }).click();
  await settle();
  assert(distance(beforeFocusButton.cameraPosition, (await debug()).cameraPosition) > 0.1, 'focus button flies back to selected building');
  assert.equal((await debug()).selectedId, selected1);
  pass('explicit focus button retains selection and refocuses camera');
  await page.getByRole('button', { name: '关闭详情', exact: true }).click();
  await page.getByTestId('building-details').waitFor({ state: 'hidden' });
  assert(!(await debug()).selectedId, 'closing card clears selection');
  await reset();
  const selected2 = await clickBuilding(selected1);
  assert.notEqual(selected1, selected2);
  // Pull back with OrbitControls without clearing the existing selection.
  const focusedBox = await canvas.boundingBox();
  await page.mouse.move(focusedBox.x + focusedBox.width * 0.12, focusedBox.y + focusedBox.height * 0.45);
  await page.mouse.wheel(0, 1100);
  await page.waitForTimeout(400);
  assert.equal((await debug()).selectedId, selected2, 'zoom preserves selection');
  const selected3 = await clickBuilding(selected2);
  assert.notEqual(selected3, selected2, 'new mesh click replaces the previous selection');
  assert.equal((await debug()).selectedId, selected3);
  // An empty corner of the actual canvas, above the bottom HUD, clears selection.
  let cleared = false;
  const emptyBox = await canvas.boundingBox();
  for (const [u, v] of [[0.08, 0.2], [0.08, 0.68], [0.92, 0.2], [0.5, 0.18]]) {
    const x = emptyBox.x + emptyBox.width * u;
    const y = emptyBox.y + emptyBox.height * v;
    await page.mouse.move(x, y);
    await page.waitForTimeout(80);
    if ((await debug()).hoveredId) continue;
    await page.mouse.click(x, y);
    if (!(await debug()).selectedId) { cleared = true; break; }
  }
  assert(cleared, 'clicking an empty mesh area clears selection');
  pass('different building selection, detail close and blank-area deselection');
  await reset();

  await page.getByRole('button', { name: '地下', exact: true }).click();
  await page.waitForFunction(selector => document.querySelector(selector)?.dataset.mode === 'underground', sceneSelector);
  const underground = await debug();
  const undergroundParking = underground.objects.find(object => /PARKING|parking/i.test(object.id + object.name));
  assert(undergroundParking?.visible, 'underground parking becomes visible');
  assert(underground.objects.filter(object => !/PARKING|parking/i.test(object.id + object.name)).some(object => object.opacity < 0.8), 'above-ground buildings become transparent');
  await page.waitForTimeout(250);
  await screenshot('underground');
  pass('underground mode and transparent buildings', { parking: undergroundParking, pipelineCount: underground.pipelineCount });
  await page.getByRole('button', { name: '风险', exact: true }).click();
  await page.waitForFunction(selector => document.querySelector(selector)?.dataset.mode === 'risk', sceneSelector);
  await page.waitForTimeout(250);
  await screenshot('risk');
  pass('risk mode activates; screenshot captures risk coloring');
  await page.getByRole('button', { name: '地上', exact: true }).click();
  await reset();

  const cruiseStart = await debug();
  await page.getByRole('button', { name: '自动巡游', exact: true }).click();
  await page.getByRole('button', { name: '停止巡游', exact: true }).waitFor();
  assert.equal((await debug()).cruising, true);
  await page.waitForTimeout(1800);
  const cruiseMiddle = await debug();
  assert(distance(cruiseStart.cameraPosition, cruiseMiddle.cameraPosition) > 0.1, 'cruise camera moves');
  await page.waitForFunction(selector => { const d = document.querySelector(selector)?.__twinDebug; return d?.cruising && d.mode === 'underground'; }, sceneSelector, { timeout: 20000 });
  await page.getByRole('button', { name: '停止巡游', exact: true }).click();
  await page.getByRole('button', { name: '自动巡游', exact: true }).waitFor();
  assert.equal((await debug()).cruising, false);
  await page.getByRole('button', { name: '地上', exact: true }).click();
  await reset();
  pass('cruise starts, moves through stops to underground parking and stops');

  const performance = await page.evaluate(async () => {
    const intervals = [];
    let previous;
    const start = performance.now();
    await new Promise(resolve => {
      const sample = time => {
        if (previous !== undefined) intervals.push(time - previous);
        previous = time;
        if (time - start >= 2500) resolve(); else requestAnimationFrame(sample);
      };
      requestAnimationFrame(sample);
    });
    return { samples: intervals.length, averageFPS: intervals.length * 1000 / intervals.reduce((a, b) => a + b, 0),
      meanFrameMs: intervals.reduce((a, b) => a + b, 0) / intervals.length };
  });
  results.performance = { ...performance, environment: /swiftshader|llvmpipe|software/i.test(renderer.renderer) ? 'Headless software renderer; not a desktop GPU acceptance benchmark' : 'Headless browser; hardware identified above' };
  pass('recorded browser frame sampling', results.performance);

  await page.setViewportSize({ width: 1440, height: 900 });
  await page.waitForTimeout(350);
  const narrowBox = await canvas.boundingBox();
  assert(narrowBox.width > 300 && narrowBox.height > 300, 'scene retains usable desktop dimensions');
  const layout = await page.evaluate(() => ({ viewport: innerWidth, scrollWidth: document.documentElement.scrollWidth }));
  assert(layout.scrollWidth <= layout.viewport + 1, '1440 viewport has no horizontal overflow');
  await screenshot('1440');
  pass('1440×900 layout, resize and no horizontal overflow', narrowBox);

  await page.evaluate(selector => { window.__m1Probe.lastScene = document.querySelector(selector); }, sceneSelector);
  await nav('事件复盘').click();
  await page.locator(sceneSelector).waitFor({ state: 'detached' });
  await page.waitForFunction(baseline => {
    const probe = window.__m1Probe;
    return probe.pending.size <= baseline && probe.contexts.every(record => record.context.isContextLost());
  }, baselineRAF, { timeout: 12000 });
  const disposed = await page.evaluate(() => ({ pendingRAF: window.__m1Probe.pending.size,
    canvasCount: document.querySelectorAll('canvas').length,
    activeContexts: window.__m1Probe.contexts.filter(item => !item.context.isContextLost()).length,
    debugRemoved: !('__twinDebug' in window.__m1Probe.lastScene) }));
  assert.equal(disposed.canvasCount, 0);
  assert.equal(disposed.activeContexts, 0);
  assert.equal(disposed.debugRemoved, true);
  pass('unmount cancels RAF, disposes WebGL context and clears diagnostics', disposed);
  for (let i = 0; i < 2; i++) {
    await nav('综合态势').click();
    await page.waitForFunction(selector => !!document.querySelector(selector)?.__twinDebug, sceneSelector);
    assert.equal(await page.locator(sceneSelector + ' canvas').count(), 1, 'reentry has exactly one canvas');
    assert.equal(await page.evaluate(() => window.__m1Probe.contexts.filter(item => !item.context.isContextLost()).length), 1, 'reentry has exactly one active WebGL context');
    await nav('事件复盘').click();
    await page.waitForFunction(baseline => window.__m1Probe.pending.size <= baseline && window.__m1Probe.contexts.every(item => item.context.isContextLost()), baselineRAF);
  }
  await nav('综合态势').click();
  await page.waitForFunction(selector => !!document.querySelector(selector)?.__twinDebug, sceneSelector);
  await page.getByRole('button', { name: '后端服务：Online', exact: true }).waitFor();
  pass('three dashboard reentries, one canvas/context each, M0 backend Online');
  pass('WebGL context loss shows recovery UI; retry creates one fresh canvas and clears selection', await verifyContextRecovery(page));
  const meaningfulWarnings = results.warnings.filter(message => !/Automatic fallback to software WebGL|GL Driver Message|GPU stall due to ReadPixels/.test(message));
  assert.deepEqual(results.errors, [], 'no page or console errors');
  assert.deepEqual(meaningfulWarnings, [], 'no application or Three.js warnings');
  console.log('M1_BROWSER_RESULT', JSON.stringify(results, null, 2));
  await browser.close();
})().catch(async error => {
  console.error('M1_BROWSER_FAILED', error.stack);
  console.error('M1_BROWSER_PARTIAL', JSON.stringify(results, null, 2));
  if (browser) await browser.close();
  process.exitCode = 1;
});
