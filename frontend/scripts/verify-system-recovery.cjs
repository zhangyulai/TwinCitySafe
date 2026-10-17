/** M10 isolated real-process recovery. Creates only its own disposable DB and services. */
const { chromium } = require('playwright');
const { spawn, spawnSync } = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const net = require('node:net');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '../..');
const output = process.env.M10_RECOVERY_OUTPUT || path.join(root, 'docs/final');
const backendPort = Number(process.env.M10_RECOVERY_BACKEND_PORT || 18000);
const frontendPort = Number(process.env.M10_RECOVERY_FRONTEND_PORT || 15173);
const databasePort = Number(process.env.M10_RECOVERY_DATABASE_PORT || 15433);
const backendURL = `http://127.0.0.1:${backendPort}`;
const frontendURL = `http://127.0.0.1:${frontendPort}`;
const run = process.argv.includes('--run-isolated');
if (!run) {
  console.log('Explicit isolated check: node frontend/scripts/verify-system-recovery.cjs --run-isolated');
  console.log('Uses an already-local postgres:17-alpine image with --pull never, disposable unnamed data, and ports 15433/18000/15173. Main services and .env are untouched.');
  process.exit(0);
}
fs.mkdirSync(output, { recursive: true });
const temporary = fs.mkdtempSync(path.join(os.tmpdir(), 'twincity-m10-recovery-'));
const container = `twincity-m10-recovery-${process.pid}-${Date.now()}`;
const password = `local-probe-${process.pid}-${Date.now()}`;
const results = { checks: [], errors: [], expectedOutageErrors: [], environment: { databasePort, backendPort, frontendPort, modelMutation: 'separate empty temporary directory; original model files untouched' } };
const children = new Set();
let browser, page, backend, frontend, containerCreated = false, controlledOutage = false;
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
function command(args) {
  const result = spawnSync('docker', args, { encoding: 'utf8', maxBuffer: 2e6 });
  if (result.status !== 0) throw new Error(`docker ${args[0]} failed: ${(result.stderr || '').slice(-1000)}`);
  return result.stdout.trim();
}
function launch(command, args, env, name, cwd = root) {
  const log = fs.openSync(path.join(output, `M10-recovery-${name}.log`), 'a');
  const process = spawn(command, args, { cwd, env, detached: true, stdio: ['ignore', log, log] });
  fs.closeSync(log); children.add(process);
  return process;
}
async function stop(child) {
  if (!child || child.exitCode !== null) { children.delete(child); return; }
  try { process.kill(-child.pid, 'SIGTERM'); } catch {}
  const ended = new Promise(resolve => child.once('exit', resolve));
  await Promise.race([ended, delay(10000)]);
  if (child.exitCode === null) {
    try { process.kill(-child.pid, 'SIGKILL'); } catch {}
    await Promise.race([ended, delay(2000)]);
  }
  children.delete(child);
}
async function wait(check, message, timeout = 45000) {
  const deadline = Date.now() + timeout;
  while (Date.now() < deadline) {
    try { const value = await check(); if (value) return value; } catch {}
    await delay(300);
  }
  throw new Error('Timed out: ' + message);
}
async function json(url, options) {
  const response = await fetch(url, { ...options, signal: AbortSignal.timeout(7000) });
  if (!response.ok) throw new Error(`HTTP ${response.status} ${url}`);
  return response.json();
}
const pass = (name, detail) => { results.checks.push({ name, detail }); console.log('PASS', name); };
const environment = { ...process.env, DATABASE_URL: `postgresql+psycopg://recovery:${password}@127.0.0.1:${databasePort}/recovery`,
  BACKEND_HOST: '127.0.0.1', BACKEND_PORT: String(backendPort), FRONTEND_PORT: String(frontendPort),
  APP_ENV: 'production', DEMO_MODE: 'true', CORS_ORIGINS: JSON.stringify([frontendURL]),
  VITE_API_PROXY_TARGET: backendURL, VITE_API_BASE_URL: '/api/v1', VITE_WS_URL: '',
  ANOMALY_MODEL_PATH: '', RISK_MODEL_DIR: '' };
const python = path.join(root, 'backend/.venv/bin/python');
const readiness = () => json(backendURL + '/api/v1/system/readiness');
const lastState = () => page.evaluate(() => window.__recoveryProbe.messages.at(-1)?.state);
const sockets = () => page.evaluate(() => window.__recoveryProbe.sockets.filter(s => s.socket.readyState === 1).length);
async function freePort(port) {
  await new Promise((resolve, reject) => {
    const server = net.createServer(); server.once('error', reject);
    server.listen(port, '127.0.0.1', () => server.close(resolve));
  });
}
async function startBackend(missing = false) {
  backend = launch(python, ['scripts/start-demo-backend.py'], missing ? { ...environment,
    ANOMALY_MODEL_PATH: path.join(temporary, 'missing-device.joblib'), RISK_MODEL_DIR: temporary } : environment,
    missing ? 'backend-models-missing' : 'backend');
  await wait(async () => (await readiness()).core_ready, 'isolated backend readiness');
}
(async () => {
  await Promise.all([backendPort, frontendPort, databasePort].map(freePort));
  command(['image', 'inspect', 'postgres:17-alpine']);
  command(['run', '-d', '--pull', 'never', '--name', container, '-p', `127.0.0.1:${databasePort}:5432`,
    '-e', 'POSTGRES_DB=recovery', '-e', 'POSTGRES_USER=recovery', '-e', `POSTGRES_PASSWORD=${password}`, 'postgres:17-alpine']);
  containerCreated = true;
  await wait(() => spawnSync('docker', ['exec', container, 'pg_isready', '-U', 'recovery', '-d', 'recovery'], { stdio: 'ignore' }).status === 0, 'temporary PostgreSQL');
  const prepareLog = fs.openSync(path.join(output, 'M10-recovery-prepare.log'), 'w');
  const prepared = spawnSync(python, ['scripts/prepare-demo.py'], { cwd: root, env: environment, stdio: ['ignore', prepareLog, prepareLog] });
  fs.closeSync(prepareLog);
  assert.equal(prepared.status, 0, 'isolated DB migrate and seed');
  await startBackend();
  assert((await readiness()).ready);
  frontend = launch('npm', ['run', 'dev', '--', '--port', String(frontendPort), '--strictPort'], environment, 'frontend', path.join(root, 'frontend'));
  await wait(async () => (await fetch(frontendURL, { signal: AbortSignal.timeout(2000) })).ok, 'isolated frontend');
  browser = await chromium.launch({ executablePath: process.env.CHROME_PATH || '/opt/google/chrome/chrome', headless: true });
  page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  page.on('pageerror', error => results.errors.push(error.message));
  page.on('console', msg => {
    if (msg.type() === 'error') (controlledOutage ? results.expectedOutageErrors : results.errors).push(msg.text());
  });
  await page.addInitScript(() => {
    const Native = window.WebSocket;
    window.__recoveryProbe = { sockets: [], messages: [] };
    window.WebSocket = class extends Native {
      constructor(...args) {
        super(...args);
        if (!String(args[0]).includes('/ws/realtime')) return;
        window.__recoveryProbe.sockets.push({ socket: this, at: performance.now() });
        this.addEventListener('message', event => {
          try { const m = JSON.parse(event.data); if (m.type === 'REALTIME_STATE') window.__recoveryProbe.messages.push({ at: performance.now(), state: m.data }); } catch {}
          if (window.__recoveryProbe.messages.length > 200) window.__recoveryProbe.messages.shift();
        });
      }
    };
  });
  await page.goto(frontendURL + '/review?demo=1');
  await page.waitForFunction(() => window.__recoveryProbe.messages.length >= 2);
  assert.equal(await sockets(), 1);
  pass('isolated production backend, real database and same-origin browser WebSocket ready', await readiness());

  // Real PostgreSQL process stop, never a mocked HTTP response.
  controlledOutage = true;
  command(['stop', '-t', '1', container]);
  const beforeDB = await lastState();
  await wait(async () => !(await readiness()).database.available, 'real DB failure visible');
  const offline = await readiness();
  assert(!offline.ready && offline.websocket.available && offline.risk_model.available);
  const assetResponse = await fetch(backendURL + '/api/v1/devices');
  assert.equal(assetResponse.status, 503);
  await page.waitForFunction(time => window.__recoveryProbe.messages.at(-1)?.state.simulationTime > time, beforeDB.simulationTime);
  assert.equal(await sockets(), 1);
  assert(await page.locator('nav').isVisible());
  command(['start', container]);
  await wait(async () => (await readiness()).ready, 'DB reconnection', 60000);
  const assets = await json(backendURL + '/api/v1/devices');
  assert.equal(assets.length, 3);
  pass('database stop/restore produces explicit 503 while realtime and UI continue', { before: beforeDB.simulationTime,
    after: (await lastState()).simulationTime, recoveredAssets: assets.length, realtimeConnections: await sockets() });

  // Browser owns reconnection; no synthetic WebSocket events and no page reload.
  const firstSession = (await lastState()).sessionId;
  await stop(backend);
  await page.waitForFunction(() => document.querySelector('[data-testid="realtime-connection"]')?.textContent.includes('Disconnected'), undefined, { timeout: 15000 });
  await delay(1500);
  const retained = await lastState();
  await startBackend();
  await page.waitForFunction(id => window.__recoveryProbe.messages.at(-1)?.state.sessionId !== id, firstSession, { timeout: 30000 });
  assert.equal(await sockets(), 1);
  assert.notEqual((await lastState()).sessionId, firstSession);
  pass('real backend restart triggers browser disconnection, retained last frame and automatic single-stream reconnect', {
    previousSession: firstSession, retainedSession: retained.sessionId, newSession: (await lastState()).sessionId,
    attempts: await page.evaluate(() => window.__recoveryProbe.sockets.length), realtimeConnections: await sockets() });

  // Reload only the process with real missing paths, leaving supplied model files unchanged.
  await stop(backend);
  await startBackend(true);
  await wait(async () => (await readiness()).degraded, 'missing model degradation');
  const missing = await readiness();
  assert(!missing.risk_model.available && !missing.anomaly_model.available && missing.core_ready);
  const started = await json(backendURL + '/api/v1/demo/start', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ scenario: 'flood', confirmed: true }) });
  assert(started.flood.scenarioId);
  const prediction = await json(backendURL + '/api/v1/risk/prediction');
  assert.equal(prediction.physicalForecast.length, 3);
  assert.equal(prediction.mlForecast.length, 0);
  await page.goto(frontendURL + '/risk?demo=1');
  await page.getByTestId('risk-model-missing').waitFor({ timeout: 30000 });
  assert.match(await page.getByTestId('risk-comparison').innerText(), /物理预测/);
  assert.equal(await sockets(), 1);
  await page.screenshot({ path: path.join(output, 'M10-model-missing-real.png'), fullPage: true });
  pass('real missing model files retain physical prediction and render explicit UI fallback', { riskModel: missing.risk_model,
    anomalyModel: missing.anomaly_model, physicalForecastPoints: prediction.physicalForecast.length, mlForecastPoints: prediction.mlForecast.length });
  const missingSession = (await lastState()).sessionId;
  await stop(backend);
  await startBackend();
  await wait(async () => (await readiness()).ready, 'supplied model recovery');
  await page.waitForFunction(id => window.__recoveryProbe.messages.at(-1)?.state.sessionId !== id, missingSession, { timeout: 30000 });
  const incidents = await json(backendURL + '/api/v1/incidents');
  assert(incidents.items.some(i => i.scenario_id === started.flood.scenarioId && i.status === 'ABORTED'));
  assert.equal(await sockets(), 1);
  pass('restoring original model paths recovers readiness and preserves interrupted incident as ABORTED', { ready: true, activeConnections: await sockets(), interruptedScenario: started.flood.scenarioId });
  // Expected transport failures were recorded separately throughout controlled outages.
  controlledOutage = false;
  assert.equal(results.errors.length, 0, JSON.stringify(results.errors));
  results.passed = true;
})().catch(error => {
  results.passed = false; results.failure = error.stack; console.error(error); process.exitCode = 1;
}).finally(async () => {
  if (browser) await browser.close().catch(() => {});
  for (const child of [...children]) await stop(child);
  if (containerCreated) {
    try { command(['rm', '-f', '-v', container]); results.cleanedIsolatedContainer = true; } catch (error) { results.cleanupError = error.message; process.exitCode = 1; }
  }
  fs.rmSync(temporary, { recursive: true, force: true });
  fs.writeFileSync(path.join(output, 'M10-recovery-results.json'), JSON.stringify(results, null, 2));
});
