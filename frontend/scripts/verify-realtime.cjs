const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const path = require('node:path');
const fs = require('node:fs');

// M2 browser integration acceptance. Run npm run test:realtime from frontend/.
const baseURL = process.env.M2_BASE_URL || 'http://127.0.0.1:5173';
const screenshotDir = process.env.M2_SCREENSHOT_DIR || path.resolve(__dirname, '../../docs');
const sceneSelector = '[data-testid="twin-scene"]';
const results = { checks: [], screenshots: [], errors: [], warnings: [], expectedOutageErrors: [], renderer: null };
let browser;
let controlledOutage = false;
const pass = (name, detail) => { results.checks.push({ name, detail }); console.log('PASS', name, detail || ''); };
const weatherCondition = live => typeof live.weather === 'string' ? live.weather : live.weather.condition;

async function verifyDesktopAndSpeed(page) {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.waitForTimeout(350);
  const layout = await page.evaluate(() => ({ viewport: innerWidth, scrollWidth: document.documentElement.scrollWidth }));
  assert(layout.scrollWidth <= layout.viewport + 1, '1440 desktop has no horizontal overflow');
  if (!await page.getByTestId('simulation-controls').isVisible()) await page.getByRole('button', { name: '仿真控制', exact: true }).click();
  const controls = await page.getByTestId('simulation-controls').boundingBox();
  assert(controls.x >= 0 && controls.x + controls.width <= 1441 && controls.y >= 0 && controls.y + controls.height <= 901, 'open simulation controls fit inside 1440×900 viewport');
  await page.getByLabel('模拟速度', { exact: true }).selectOption('2');
  await page.waitForFunction(() => document.querySelector('select[aria-label="模拟速度"]')?.value === '2');
  let speedStatus;
  for (let attempt = 0; attempt < 20; attempt++) {
    speedStatus = await (await page.request.get(baseURL + '/api/v1/simulation/status')).json();
    if (speedStatus.speed === 2) break;
    await page.waitForTimeout(100);
  }
  assert.equal(speedStatus.speed, 2, 'native speed select updates backend to 2×');
  await page.getByTestId('simulation-controls').getByRole('button', { name: 'Reset', exact: true }).click();
  await page.getByTestId('simulation-controls').getByRole('button', { name: 'Start', exact: true }).click();
  const restored = await (await page.request.get(baseURL + '/api/v1/simulation/status')).json();
  assert.equal(restored.speed, 1);
  assert.equal(restored.running, true);
  await page.getByRole('button', { name: '仿真控制', exact: true }).click();
  await page.waitForTimeout(250);
  const screenshot = path.join(screenshotDir, 'M2-1440.png');
  await page.screenshot({ path: screenshot, fullPage: true });
  return { layout, controls, changedSpeed: speedStatus.speed, restoredSpeed: restored.speed, screenshot };
}
module.exports = { verifyDesktopAndSpeed };

if (require.main === module) (async () => {
  browser = await chromium.launch({ executablePath: process.env.CHROME_PATH || (fs.existsSync('/opt/google/chrome/chrome') ? '/opt/google/chrome/chrome' : undefined), headless: true });
  const context = await browser.newContext({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
  const page = await context.newPage();
  page.on('pageerror', error => results.errors.push(error.message));
  page.on('console', message => {
    if (['warning', 'warn'].includes(message.type())) results.warnings.push(message.text());
    if (message.type() === 'error') (controlledOutage ? results.expectedOutageErrors : results.errors).push(message.text());
  });
  await page.addInitScript(() => {
    const NativeWebSocket = window.WebSocket;
    const sockets = [];
    const messages = [];
    window.WebSocket = class extends NativeWebSocket {
      constructor(...args) {
        super(...args);
        if (!String(args[0]).includes('/ws/realtime')) return;
        const record = { socket: this, createdAt: performance.now(), openedAt: null, closedAt: null };
        sockets.push(record);
        this.addEventListener('open', () => { record.openedAt = performance.now(); });
        this.addEventListener('close', () => { record.closedAt = performance.now(); });
        this.addEventListener('message', event => {
          try {
            const message = JSON.parse(event.data);
            if (message.type === 'REALTIME_STATE') {
              messages.push({ receivedAt: performance.now(), state: message.data });
              if (messages.length > 600) messages.shift();
            }
          } catch { /* Application owns malformed-message handling. */ }
        });
      }
    };
    window.__m2Probe = { sockets, messages, originalCanvas: null };
  });
  const debug = () => page.locator(sceneSelector).evaluate(el => el.__twinDebug);
  const lastState = () => page.evaluate(() => window.__m2Probe.messages.at(-1)?.state);
  const liveSocketCount = () => page.evaluate(() => window.__m2Probe.sockets.filter(item => item.socket.readyState === WebSocket.OPEN).length);
  const screenshot = async name => {
    const file = path.join(screenshotDir, `M2-${name}.png`);
    await page.screenshot({ path: file, fullPage: true });
    results.screenshots.push(file);
  };
  const showControls = async () => {
    if (!await page.getByTestId('simulation-controls').isVisible()) await page.getByRole('button', { name: '仿真控制', exact: true }).click();
    await page.getByTestId('simulation-controls').waitFor();
  };
  const hideControls = async () => {
    if (await page.getByTestId('simulation-controls').isVisible()) await page.getByRole('button', { name: '仿真控制', exact: true }).click();
  };
  const waitForState = async condition => {
    await page.waitForFunction(condition, undefined, { timeout: 15000 });
  };
  const assertDevice = async (id, status) => {
    await page.waitForFunction(({ selector, id, status }) => {
      const live = document.querySelector(selector)?.__twinDebug?.live;
      return live?.deviceStates?.some(device => device.id.toUpperCase().endsWith(id) && device.status === status);
    }, { selector: sceneSelector, id, status }, { timeout: 12000 });
    if (id === 'P03') await page.waitForFunction(status => document.querySelector('[data-testid="p03-card"]')?.dataset.status === status, status);
  };
  const getDeviceVisual = async id => (await debug()).live.deviceStates.find(device => device.id.toUpperCase().endsWith(id));
  const sampleFPS = () => page.evaluate(async () => {
    const intervals = [];
    let previous;
    const start = performance.now();
    await new Promise(resolve => {
      const step = time => {
        if (previous !== undefined) intervals.push(time - previous);
        previous = time;
        if (time - start >= 2200) resolve(); else requestAnimationFrame(step);
      };
      requestAnimationFrame(step);
    });
    return { frames: intervals.length, averageFPS: intervals.length * 1000 / intervals.reduce((a, b) => a + b, 0) };
  });
  const post = async (suffix, data) => {
    const response = await page.request.post(baseURL + '/api/v1/simulation/' + suffix, data ? { data } : {});
    assert(response.ok(), `${suffix}: HTTP ${response.status()}`);
    return response.json();
  };

  await page.goto(baseURL + '/dashboard');
  await page.getByTestId('realtime-badge').waitFor();
  await waitForState(() => window.__m2Probe.messages.length > 1);
  await page.waitForFunction(selector => !!document.querySelector(selector)?.__twinDebug?.live, sceneSelector);
  await page.getByRole('button', { name: '后端服务：Online', exact: true }).waitFor();
  assert.equal(await liveSocketCount(), 1);
  assert.match(await page.getByTestId('realtime-badge').innerText(), /实时仿真/);
  await showControls();
  await page.getByTestId('simulation-controls').getByRole('button', { name: 'Reset', exact: true }).click();
  await post('start');
  await post('speed', { speed: 1 });
  await page.getByTestId('simulation-controls').getByRole('button', { name: 'Clear', exact: true }).click();
  await assertDevice('P03', 'running');
  await page.waitForFunction(selector => {
    const d = document.querySelector(selector)?.__twinDebug;
    const w = d?.live?.weather;
    return d?.drawCalls > 0 && (typeof w === 'string' ? w : w?.condition) === 'clear';
  }, sceneSelector);
  await page.evaluate(selector => { window.__m2Probe.originalCanvas = document.querySelector(selector).querySelector('canvas'); }, sceneSelector);
  const restResponse = await page.request.get(baseURL + '/api/v1/realtime/state');
  assert(restResponse.ok());
  const restState = await restResponse.json();
  assert.equal(restState.devices.length, 3);
  assert.equal(restState.pipelines.length, 32);
  assert.equal(restState.weather.condition, 'clear');
  assert.equal(restState.running, true);
  results.renderer = await page.locator(sceneSelector + ' canvas').evaluate(canvas => {
    const gl = canvas.getContext('webgl2');
    const extension = gl.getExtension('WEBGL_debug_renderer_info');
    return extension ? gl.getParameter(extension.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER);
  });
  await hideControls();
  await page.mouse.move(12, 12);
  await screenshot('clear');
  results.clearPerformance = await sampleFPS();
  pass('app connects once, REST and WebSocket share state, Dashboard renders live simulation', { renderer: results.renderer, performance: results.clearPerformance });

  const updatedBefore = await page.getByTestId('realtime-updated').getAttribute('data-timestamp');
  await page.waitForFunction(previous => document.querySelector('[data-testid="realtime-updated"]')?.dataset.timestamp !== previous, updatedBefore, { timeout: 7000 });
  assert.match(await page.getByTestId('p03-card').innerText(), /P03/);
  pass('Dashboard timestamp and P03 telemetry refresh');

  const clearLighting = (await debug()).live.lighting;
  await showControls();
  await page.getByTestId('simulation-controls').getByRole('button', { name: 'Cloudy', exact: true }).click();
  await page.waitForFunction(selector => {
    const weather = document.querySelector(selector)?.__twinDebug?.live?.weather;
    return (typeof weather === 'string' ? weather : weather?.condition) === 'cloudy';
  }, sceneSelector);
  await page.waitForFunction(({ selector, ambient }) => document.querySelector(selector)?.__twinDebug?.live?.lighting?.ambient < ambient, { selector: sceneSelector, ambient: clearLighting.ambient });
  pass('Cloudy reduces actual scene lighting', { clear: clearLighting, cloudy: (await debug()).live.lighting });
  await page.getByTestId('simulation-controls').getByRole('button', { name: 'Rain', exact: true }).click();
  await page.waitForFunction(selector => {
    const live = document.querySelector(selector)?.__twinDebug?.live;
    return live?.rainVisible && live.rainParticleCount > 0;
  }, sceneSelector, { timeout: 15000 });
  assert.equal(weatherCondition((await debug()).live), 'rain');
  const earlyRain = await lastState();
  await hideControls();
  await page.mouse.move(12, 12);
  await screenshot('rain');
  results.rainPerformance = await sampleFPS();
  const rainLater = await lastState();
  assert(rainLater.weather.rainfall >= earlyRain.weather.rainfall, 'rainfall approaches rain target gradually');
  assert(rainLater.weather.rainfall > 0);
  pass('Clear / Cloudy / Rain controls reach scene and create rain particles', { earlyRainfall: earlyRain.weather.rainfall, laterRainfall: rainLater.weather.rainfall, particles: (await debug()).live.rainParticleCount, performance: results.rainPerformance });

  await showControls();
  const deviceVisuals = {};
  deviceVisuals.running = await getDeviceVisual('P03');
  const isolatedP01 = await getDeviceVisual('P01');
  for (const status of ['warning', 'offline', 'running']) {
    await page.getByLabel('P03 状态', { exact: true }).selectOption(status);
    await assertDevice('P03', status);
    deviceVisuals[status] = await getDeviceVisual('P03');
    const currentP01 = await getDeviceVisual('P01');
    assert.equal(currentP01.color, isolatedP01.color, 'P03 change must not recolor P01');
    assert.equal(currentP01.status, isolatedP01.status, 'P03 change must not change P01 status');
    await page.waitForFunction(status => window.__m2Probe.messages.at(-1)?.state.devices.find(device => device.id === 'P03')?.status === status, status);
  }
  assert.notDeepEqual(deviceVisuals.warning.color, deviceVisuals.running.color);
  assert.notDeepEqual(deviceVisuals.offline.color, deviceVisuals.running.color);
  for (const id of ['P01', 'P02']) {
    await page.getByLabel(id + ' 状态', { exact: true }).selectOption('running');
    await assertDevice(id, 'running');
    await page.getByLabel(id + ' 状态', { exact: true }).selectOption('standby');
    await assertDevice(id, 'standby');
  }
  pass('P01 / P02 controls and P03 Running / Warning / Offline update UI and existing Three.js materials', deviceVisuals);

  // With P03 temporarily offline during moderate rain, check physical water-level linkage.
  const waterBefore = (await debug()).live;
  await page.getByLabel('P03 状态', { exact: true }).selectOption('offline');
  await assertDevice('P03', 'offline');
  await page.waitForFunction(({ selector, previous }) => {
    const live = document.querySelector(selector)?.__twinDebug?.live;
    return live && Math.abs(live.waterLevel - previous) > 0.001;
  }, { selector: sceneSelector, previous: waterBefore.waterLevel }, { timeout: 15000 });
  const waterAfter = (await debug()).live;
  assert(Math.abs(waterAfter.waterY - waterBefore.waterY) > 0.000001, 'water mesh responds to measured centimeters');
  assert(waterAfter.waterLevel < 10, 'M2 remains below incident-scale flooding');
  await page.getByLabel('P03 状态', { exact: true }).selectOption('running');
  await assertDevice('P03', 'running');
  await hideControls();
  pass('water surface height follows continuous B2 water level', { before: { level: waterBefore.waterLevel, y: waterBefore.waterY }, after: { level: waterAfter.waterLevel, y: waterAfter.waterY } });

  // Sample 30 genuinely pushed revisions after rain is warm to account for lazy GPU allocation.
  await page.mouse.move(12, 12);
  const stableStart = await page.evaluate(selector => ({ index: window.__m2Probe.messages.length, revision: window.__m2Probe.messages.at(-1).state.revision,
    geometryCount: document.querySelector(selector).__twinDebug.geometries,
    textureCount: document.querySelector(selector).__twinDebug.textures }), sceneSelector);
  await page.waitForFunction(start => window.__m2Probe.messages.slice(start.index).filter(item => item.state.revision > start.revision).length >= 30, stableStart, { timeout: 45000 });
  const samples = await page.evaluate(start => window.__m2Probe.messages.slice(start.index).filter(item => item.state.revision > start.revision), stableStart);
  const stableEnd = await debug();
  assert.equal(stableEnd.geometries, stableStart.geometryCount, '30 states do not allocate more WebGL geometries');
  assert.equal(stableEnd.textures, stableStart.textureCount, '30 states do not allocate more textures');
  assert.equal(await page.evaluate(selector => window.__m2Probe.originalCanvas === document.querySelector(selector).querySelector('canvas'), sceneSelector), true, 'real-time updates retain the same canvas');
  assert.equal(await liveSocketCount(), 1);
  const intervals = [];
  for (let i = 1; i < samples.length; i++) {
    const previous = samples[i - 1];
    const current = samples[i];
    intervals.push(current.receivedAt - previous.receivedAt);
    assert(current.state.revision > previous.state.revision, 'state revisions advance');
    assert(Math.abs(current.state.weather.rainfall - previous.state.weather.rainfall) < 5, 'rainfall is continuous');
    assert(Math.abs(current.state.environment.b2WaterLevel - previous.state.environment.b2WaterLevel) < 1, 'water level is continuous');
    assert(Math.abs(current.state.devices.find(d => d.id === 'P03').temperature - previous.state.devices.find(d => d.id === 'P03').temperature) < 3, 'pump temperature is continuous');
  }
  const meanInterval = intervals.reduce((a, b) => a + b, 0) / intervals.length;
  assert(meanInterval > 750 && meanInterval < 1600, 'WebSocket cadence stays close to 1 Hz');
  pass('30 consecutive live updates keep geometry/texture/canvas identity stable and data continuous', { states: samples.length, meanIntervalMs: meanInterval, geometries: stableEnd.geometries, textures: stableEnd.textures });

  await page.getByRole('button', { name: '地下', exact: true }).click();
  await page.waitForFunction(selector => document.querySelector(selector)?.dataset.mode === 'underground', sceneSelector);
  let selectedPipeline;
  const pipes = (await debug()).live.pipelines;
  for (const pipe of pipes) {
    if (!pipe.visible || !pipe.screen) continue;
    for (const [dx, dy] of [[0, 0], [2, 0], [-2, 0], [0, 2], [0, -2]]) {
      await page.mouse.click(pipe.screen.x + dx, pipe.screen.y + dy);
      if (await page.getByTestId('pipeline-details').isVisible()) { selectedPipeline = pipe; break; }
    }
    if (selectedPipeline) break;
  }
  assert(selectedPipeline, 'real pipe mesh click opens pipeline telemetry');
  const pipeDetailsBefore = await page.getByTestId('pipeline-details').textContent();
  assert.match(pipeDetailsBefore, /压力|pressure/i);
  assert.match(pipeDetailsBefore, /流量|flow/i);
  assert(pipeDetailsBefore.includes(selectedPipeline.id));
  await page.waitForFunction(previous => document.querySelector('[data-testid="pipeline-details"]')?.textContent !== previous, pipeDetailsBefore, { timeout: 10000 });
  await screenshot('underground');
  pass('underground real pipeline raycast opens pressure/flow details that update live', { id: selectedPipeline.id });

  const initialSocketCreations = await page.evaluate(() => window.__m2Probe.sockets.length);
  for (let i = 0; i < 3; i++) {
    await page.getByRole('navigation').getByRole('link', { name: /事件复盘/ }).click();
    await page.locator(sceneSelector).waitFor({ state: 'detached' });
    assert.equal(await liveSocketCount(), 1, 'global realtime stream survives route leave');
    await page.getByRole('navigation').getByRole('link', { name: /综合态势/ }).click();
    await page.waitForFunction(selector => !!document.querySelector(selector)?.__twinDebug?.live, sceneSelector);
    assert.equal(await page.locator(sceneSelector + ' canvas').count(), 1);
    assert.equal(await liveSocketCount(), 1);
  }
  assert.equal(await page.evaluate(() => window.__m2Probe.sockets.length), initialSocketCreations, 'route changes do not instantiate new app WebSockets');
  pass('three route reentries retain one global WebSocket and one scene canvas');

  await showControls();
  await page.getByTestId('simulation-controls').getByRole('button', { name: 'Stop', exact: true }).click();
  await page.waitForFunction(() => window.__m2Probe.messages.at(-1)?.state.running === false);
  const stopped = await lastState();
  await page.waitForTimeout(2200);
  assert.equal((await lastState()).simulationTime, stopped.simulationTime, 'Stop freezes simulation time');
  await page.getByTestId('simulation-controls').getByRole('button', { name: 'Reset', exact: true }).click();
  await page.waitForFunction(() => window.__m2Probe.messages.at(-1)?.state.simulationTime === 0);
  const reset = await lastState();
  assert.equal(reset.weather.condition, 'clear');
  assert.equal(reset.devices.find(d => d.id === 'P03').status, 'running');
  await page.getByTestId('simulation-controls').getByRole('button', { name: 'Start', exact: true }).click();
  await page.waitForFunction(() => window.__m2Probe.messages.at(-1)?.state.simulationTime > 0);
  await hideControls();
  pass('Stop freezes, Reset restores baseline, Start resumes through UI');

  const desktop = await verifyDesktopAndSpeed(page);
  results.screenshots.push(desktop.screenshot);
  pass('1440 desktop, bounded developer panel, 2× speed control and default restoration', desktop);
  const creationsBeforeDrop = await page.evaluate(() => window.__m2Probe.sockets.length);
  controlledOutage = true;
  await context.setOffline(true);
  await page.evaluate(() => window.__m2Probe.sockets.filter(item => item.socket.readyState === WebSocket.OPEN).forEach(item => item.socket.close(4001, 'M2 controlled outage probe')));
  await page.waitForFunction(() => /数据连接断开/.test(document.querySelector('[data-testid="realtime-badge"]')?.textContent || ''), undefined, { timeout: 5000 });
  const retainedBefore = await page.getByTestId('p03-card').innerText();
  const lastTimestampBefore = await page.getByTestId('realtime-updated').getAttribute('data-timestamp');
  await page.waitForTimeout(8500);
  assert.equal(await page.getByTestId('p03-card').innerText(), retainedBefore, 'outage retains last telemetry card');
  assert.equal(await page.getByTestId('realtime-updated').getAttribute('data-timestamp'), lastTimestampBefore, 'outage retains last update time');
  const attempts = await page.evaluate(start => window.__m2Probe.sockets.slice(start).map(item => item.createdAt), creationsBeforeDrop);
  assert(attempts.length >= 2 && attempts.length <= 4, 'offline retry uses a bounded backoff');
  const retryGaps = attempts.slice(1).map((time, i) => time - attempts[i]);
  const firstRetryDelay = await page.evaluate(start => window.__m2Probe.sockets[start].createdAt - window.__m2Probe.sockets[start - 1].closedAt, creationsBeforeDrop);
  assert(firstRetryDelay >= 850 && firstRetryDelay < 2500, 'first retry waits about 1 second');
  assert(retryGaps.length >= 2, 'observe the 2-second and 5-second retry stages');
  for (const [index, target] of [2000, 5000].entries()) assert(retryGaps[index] >= target * 0.85 && retryGaps[index] < target + 2000, 'retry delay follows 1/2/5 second backoff');
  await context.setOffline(false);
  await page.waitForFunction(() => /实时仿真/.test(document.querySelector('[data-testid="realtime-badge"]')?.textContent || ''), undefined, { timeout: 15000 });
  await page.waitForFunction(previous => document.querySelector('[data-testid="realtime-updated"]')?.dataset.timestamp !== previous, lastTimestampBefore, { timeout: 8000 });
  assert.equal(await liveSocketCount(), 1);
  controlledOutage = false;
  pass('offline retains data, disconnected indicator and delayed retries; reconnect recovers one stream', { attempts: attempts.length, firstRetryDelayMs: firstRetryDelay, retryGapsMs: retryGaps });

  // Leave the shared demonstration in a clean, running, clear baseline.
  await post('stop');
  await post('reset');
  await post('speed', { speed: 1 });
  await post('start');
  await page.waitForFunction(selector => {
    const w = document.querySelector(selector)?.__twinDebug?.live?.weather;
    return (typeof w === 'string' ? w : w?.condition) === 'clear';
  }, sceneSelector);
  const meaningfulWarnings = results.warnings.filter(message => !/GL Driver Message|GPU stall due to ReadPixels|Automatic fallback to software WebGL/.test(message));
  assert.deepEqual(results.errors, [], 'no unexpected page or console errors');
  assert.deepEqual(meaningfulWarnings, [], 'no unexpected Three.js/application warnings');
  results.performanceEnvironment = /swiftshader|llvmpipe|software/i.test(results.renderer) ? 'Headless software rendering; the >45 FPS desktop GPU target is not established by this run' : 'Headless browser; identified renderer above';
  console.log('M2_BROWSER_RESULT', JSON.stringify(results, null, 2));
  await browser.close();
})().catch(async error => {
  console.error('M2_BROWSER_FAILED', error.stack);
  console.error('M2_BROWSER_PARTIAL', JSON.stringify(results, null, 2));
  if (browser) await browser.close();
  process.exitCode = 1;
});
