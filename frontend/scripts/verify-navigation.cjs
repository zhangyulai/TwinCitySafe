const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const base = process.env.M10_BASE_URL || 'http://127.0.0.1:5173';
const output = process.env.M10_OUTPUT_DIR || path.resolve(__dirname, '../../docs/final');
const routes = [ ['dashboard', '综合态势'], ['operation', '智慧运维'], ['pipeline', '地下管网'], ['risk', '风险研判'], ['simulation', '应急推演'], ['review', '事件复盘'] ];
const result = { checks: [], cycles: [], layouts: [], screenshots: [], errors: [], warnings: [] };
let browser;
const pass = (name, details) => { result.checks.push({ name, details }); console.log('PASS', name); };
(async () => {
  fs.mkdirSync(path.join(output, 'screenshots'), { recursive: true });
  browser = await chromium.launch({ executablePath: process.env.CHROME_PATH || '/opt/google/chrome/chrome', headless: true, args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
  page.on('pageerror', error => result.errors.push(error.message));
  page.on('console', message => { if (message.type() === 'error') result.errors.push(message.text()); if (message.type() === 'warning') result.warnings.push(message.text()); });
  await page.addInitScript(() => {
    const nativeRequest = window.requestAnimationFrame.bind(window), nativeCancel = window.cancelAnimationFrame.bind(window), pending = new Set();
    window.requestAnimationFrame = callback => { const id = nativeRequest(time => { pending.delete(id); callback(time); }); pending.add(id); return id; };
    window.cancelAnimationFrame = id => { pending.delete(id); nativeCancel(id); };
    const contexts = [], nativeContext = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = function(type, ...args) { const context = nativeContext.call(this, type, ...args); if (context && /webgl/.test(type) && !contexts.some(item => item.context === context)) contexts.push({ canvas: this, context }); return context; };
    for (const type of [WebGLRenderingContext, WebGL2RenderingContext]) {
      for (const name of ['drawArrays','drawElements','drawArraysInstanced','drawElementsInstanced']) {
        const original = type.prototype[name]; if (!original) continue;
        type.prototype[name] = function(...args) { const entry = contexts.find(item => item.context === this); if (entry) entry.drawCalls = (entry.drawCalls || 0) + 1; return original.apply(this,args); };
      }
    }
    const NativeSocket = window.WebSocket, sockets = [];
    // Count the application channel; Vite has an independent development HMR socket.
    window.WebSocket = class extends NativeSocket { constructor(...args) { super(...args); if (String(args[0]).includes('/ws/realtime')) sockets.push(this); } };
    window.__m10Navigation = { pending, contexts, sockets };
  });
  const probe = () => page.evaluate(() => {
    const p = window.__m10Navigation;
    return { raf: p.pending.size, activeContexts: p.contexts.filter(item => !item.context.isContextLost()).length, totalContexts: p.contexts.length, canvas: document.querySelectorAll('canvas').length, sceneCanvas: document.querySelectorAll('[data-testid="twin-scene"] canvas').length, sockets: p.sockets.length, openSockets: p.sockets.filter(item => item.readyState === WebSocket.OPEN).length, connectingSockets: p.sockets.filter(item => item.readyState === WebSocket.CONNECTING).length };
  });
  const visit = async (route, label) => {
    result.currentRoute = route;
    console.log('VISIT', route);
    await page.getByRole('navigation').getByRole('link', { name: new RegExp(label) }).click();
    await page.waitForURL(url => url.pathname === '/' + route);
    if (route === 'review') {
      await page.waitForFunction(() => document.querySelectorAll('canvas').length === 0 && window.__m10Navigation.pending.size === 0, null, { timeout: 15000 });
    } else {
      await page.locator('[data-testid="twin-scene"]').scrollIntoViewIfNeeded();
      await page.waitForFunction(() => window.__m10Navigation.contexts.some(item => document.querySelector('[data-testid="twin-scene"]')?.contains(item.canvas) && item.drawCalls > 0 && !item.context.isContextLost()));
    }
    await page.waitForFunction(() => window.__m10Navigation.sockets.filter(item => item.readyState === WebSocket.OPEN).length === 1);
  };
  const current = await (await page.request.get(base + '/api/v1/realtime/state')).json();
  assert(!current.flood?.scenarioId && !current.leak?.scenarioId, 'Navigation acceptance requires idle demo; this read-only script does not reset active incidents');
  await page.goto(base + '/review');
  await page.waitForFunction(() => window.__m10Navigation.sockets.some(item => item.readyState === WebSocket.OPEN));
  const initial = await probe();
  assert.equal(initial.canvas, 0); assert.equal(initial.activeContexts, 0);
  for (let cycle = 1; cycle <= 10; cycle++) {
    const observations = [];
    for (const [route, label] of routes) {
      await visit(route, label);
      const state = await probe();
      assert.equal(state.openSockets, 1); assert.equal(state.connectingSockets, 0);
      assert.equal(state.activeContexts, route === 'review' ? 0 : 1);
      assert.equal(state.sceneCanvas, route === 'review' ? 0 : 1);
      if (route === 'review') { assert.equal(state.raf, 0); assert.equal(state.canvas, 0); }
      observations.push({ route, ...state });
    }
    result.cycles.push({ cycle, observations });
    console.log('PASS navigation cycle', cycle);
  }
  pass('10 complete six-route cycles release every old WebGL context, all review canvases and RAFs; one WebSocket remains', { initial, final: await probe() });
  for (const viewport of [{ width: 1920, height: 1080 }, { width: 1440, height: 900 }, { width: 1366, height: 768 }]) {
    await page.setViewportSize(viewport);
    for (const [route, label] of routes) {
      await visit(route, label);
      await page.waitForTimeout(350);
      const layout = await page.evaluate(() => ({ width: innerWidth, scrollWidth: document.documentElement.scrollWidth, scrollHeight: document.documentElement.scrollHeight, navigation: Array.from(document.querySelectorAll('nav a')).map(el => { const r = el.getBoundingClientRect(); return { label: el.textContent, left: r.left, right: r.right, top: r.top, bottom: r.bottom }; }), scene: (() => { const el = document.querySelector('[data-testid="twin-scene"]'); if (!el) return null; const r = el.getBoundingClientRect(); return { width: r.width, height: r.height, quality: el.dataset.quality }; })() }));
      assert(layout.scrollWidth <= viewport.width + 1, `${route} overflow at ${viewport.width}: ${layout.scrollWidth}`);
      assert(layout.navigation.every(link => link.left >= 0 && link.right <= viewport.width + 1), `${route} navigation outside viewport`);
      if (layout.scene) assert(layout.scene.width > 250 && layout.scene.height > 200, `${route} scene is usable`);
      result.layouts.push({ viewport, route, ...layout });
      await page.evaluate(() => scrollTo(0, 0));
      const file = path.join(output, 'screenshots', `layout-${viewport.width}-${route}.png`);
      await page.screenshot({ path: file, fullPage: true }); result.screenshots.push(file);
    }
  }
  pass('six pages fit 1920/1440/1366 widths; 18 actual screenshots saved', { layouts: result.layouts.length });
  assert.deepEqual(result.errors, []);
  fs.writeFileSync(path.join(output, 'M10-navigation-results.json'), JSON.stringify(result, null, 2));
  await browser.close();
})().catch(async error => { result.failure = error.stack; fs.mkdirSync(output, { recursive: true }); fs.writeFileSync(path.join(output, 'M10-navigation-results.json'), JSON.stringify(result, null, 2)); console.error(error); await browser?.close(); process.exitCode = 1; });
