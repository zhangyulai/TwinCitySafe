/* M9: real REST/WS engine, PostgreSQL archives and browser work-order/close UI.
 * Run sequentially with all other scenario scripts; never fixture engine state.
 */
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const base = process.env.M9_BASE_URL || 'http://127.0.0.1:5173';
const output = process.env.M9_OUTPUT_DIR || path.resolve(__dirname, '../../docs');
fs.mkdirSync(output, { recursive: true });
const result = { startedAt: new Date().toISOString(), checks: [], errors: [], screenshots: [], floodIncidentId: null, leakIncidentId: null };
let browser, page;
const confirmation = '确认关闭该软件仿真事件？关闭后事件将进入历史复盘，不再作为当前活动事故。';
const pass = (name, detail) => { result.checks.push({ name, detail }); console.log('PASS', name, detail || ''); };
function physical(state) {
  return { simulationTime: state.simulationTime, devices: state.devices, pipelines: state.pipelines,
    valves: state.valves, environment: state.environment, weather: state.weather,
    flood: Object.fromEntries(['waterLevel','waterArea','floodVolume','effectiveArea','entranceClosed','peopleCount','vehicleCount','vehicleEntryRate','exposureRemaining','exposureTarget','effectivePumpCapacity','outflow','riskScore'].map(key => [key, state.flood[key]])),
    leak: Object.fromEntries(['upstreamPressure','downstreamPressure','pipelineFlow','estimatedLeakFlow','leakSeverity','serviceStatus','leakStatus','affectedBuildings','affectedNodes','affectedEdges','interruptedBuildings','estimatedServiceLoss','suspectedSegments','riskScore'].map(key => [key, state.leak[key]])) };
}
async function request(method, url, data) {
  const response = await page.request[method](base + '/api/v1/' + url, data === undefined ? {} : { data });
  const text = await response.text();
  assert(response.ok(), `${method.toUpperCase()} ${url} ${response.status()}: ${text}`);
  return JSON.parse(text);
}
const get = url => request('get', url);
const post = (url, data) => request('post', url, data);
async function until(label, read, predicate, timeout = 30000) {
  const start = Date.now(); let nextLog = start + 30000; let value;
  while (Date.now() - start < timeout) {
    value = await read();
    if (predicate(value)) return value;
    if (Date.now() >= nextLog) { console.log('WAIT', label, Math.round((Date.now() - start) / 1000) + 's'); nextLog += 30000; }
    await page.waitForTimeout(1000);
  }
  throw new Error(`Timed out: ${label}; last value: ${JSON.stringify(value).slice(0, 1000)}`);
}
async function archived(type, scenarioId) {
  const data = await until(`${type} archive STABILIZING`, () => get(`incidents?type=${type}&limit=100`),
    value => value.items.some(x => x.scenario_id === scenarioId && x.status === 'STABILIZING'));
  return data.items.find(x => x.scenario_id === scenarioId);
}
async function nav(name) {
  await page.getByRole('navigation').getByRole('link', { name }).click();
}
async function screenshot(name, locator) {
  const file = path.join(output, 'M9-lifecycle-' + name + '.png');
  if (locator) await locator.screenshot({ path: file });
  else await page.screenshot({ path: file, fullPage: true });
  result.screenshots.push(file);
}
async function openReview(id) {
  await nav(/事件复盘/);
  await page.getByTestId('review-page').waitFor();
  await page.locator(`[data-incident-id="${id}"]`).click();
  await page.getByTestId('review-work-orders').waitFor();
  await page.getByRole('button', { name: '人工确认关闭事件', exact: true }).waitFor();
}
async function completeWorkOrder(id, team, note) {
  const detail = await get(`incidents/${id}`);
  assert.equal(detail.work_orders.length, 1, 'one automatic main work order');
  const order = detail.work_orders[0];
  assert.equal(order.status, 'PENDING');
  const card = page.locator(`[data-work-order="${order.id}"]`);
  await card.getByLabel('接单班组', { exact: true }).fill(team);
  await card.getByRole('button', { name: '接单', exact: true }).click();
  await card.getByRole('button', { name: '开始处理', exact: true }).waitFor();
  assert.equal((await get(`work-orders/${order.id}`)).status, 'ASSIGNED');
  await card.getByRole('button', { name: '开始处理', exact: true }).click();
  await card.getByRole('button', { name: '完成工单', exact: true }).waitFor();
  assert.equal((await get(`work-orders/${order.id}`)).status, 'IN_PROGRESS');
  await card.getByLabel('工单处理结果', { exact: true }).fill(note);
  await card.getByRole('button', { name: '完成工单', exact: true }).click();
  await until('work order COMPLETED', () => get(`work-orders/${order.id}`), value => value.status === 'COMPLETED');
  // The action refreshes the archive asynchronously; wait for its final UI message before closing.
  await page.getByRole('status').filter({ hasText: '工单状态已保存。' }).waitFor();
  const completed = await get(`work-orders/${order.id}`);
  assert.equal(completed.result, note); assert.equal(completed.assignee, team);
  assert(completed.accepted_at && completed.completed_at);
  pass('browser work order PENDING → ASSIGNED → IN_PROGRESS → COMPLETED', { incidentId: id, orderId: order.id, team });
  return completed;
}
async function confirmClose(id, kind, note) {
  await page.getByLabel('事件关闭说明', { exact: true }).fill(note);
  const before = await get('realtime/state');
  assert.equal(before.running, false, 'pause before verifying exact physical continuity');
  const oldTimeline = await get(`incidents/${id}/timeline`);
  const oldReplay = await get(`incidents/${id}/replay`);
  const oldDetail = await get(`incidents/${id}`);
  assert.equal(oldDetail.status, 'STABILIZING');
  assert(!oldTimeline.items.some(x => x.event_type === 'INCIDENT_CLOSED'));
  const dialogPromise = page.waitForEvent('dialog');
  const clickPromise = page.getByRole('button', { name: '人工确认关闭事件', exact: true }).click();
  const dialog = await dialogPromise;
  assert.equal(dialog.message(), confirmation); await dialog.accept(); await clickPromise;
  await page.getByRole('status').filter({ hasText: '事件已关闭并保留历史档案。' }).waitFor();
  const after = await get('realtime/state'); const closed = await get(`incidents/${id}`);
  assert.equal(closed.status, 'CLOSED'); assert(closed.closed_at && closed.close_result);
  assert.equal(closed.close_result.result, note);
  assert(!after.flood.scenarioId && !after.leak.scenarioId && !after.emergency);
  assert.equal(after.running, false);
  assert.deepEqual(physical(after), physical(before), 'business close must not reset physical device/valve/environment outcomes');
  const replay = await get(`incidents/${id}/replay`); const timeline = await get(`incidents/${id}/timeline`);
  const retry = await post(`incidents/${id}/close`, { confirmed: true, operator: 'demo-user', result: '幂等重试，不改原关闭说明' });
  assert.equal(retry.closed_at, closed.closed_at); assert.deepEqual(retry.close_result, closed.close_result);
  const repeated = await get(`incidents/${id}/timeline`);
  assert.deepEqual(repeated.items, timeline.items);
  assert.equal(timeline.items.filter(x => x.event_type === 'INCIDENT_CLOSED').length, 1);
  assert(replay.snapshots.length >= oldReplay.snapshots.length);
  assert.equal(closed.comparisons.length, oldDetail.comparisons.length);
  assert.equal(closed.executions.length, oldDetail.executions.length);
  assert.equal(closed.work_orders[0].status, 'COMPLETED');
  await page.getByTestId('review-report').getByRole('button', { name: '生成复盘报告', exact: true }).click();
  await page.getByTestId('review-report').getByRole('button', { name: '重新生成报告', exact: true }).waitFor();
  const report = (await get(`incidents/${id}/review`)).report;
  assert(report && report.metrics && report.summary);
  await screenshot(kind + '-closed', page.getByTestId('review-close'));
  const metrics = await get(`incidents/${id}/metrics`);
  const record = { incidentId: id, closedAt: closed.closed_at, before: physical(before), after: physical(after),
    beforeScenario: kind === 'flood' ? before.flood : before.leak, timelineTypes: timeline.items.map(x => x.event_type),
    snapshotCount: replay.snapshots.length, sourceSnapshotCount: replay.metadata.source_snapshot_count,
    timelineCount: timeline.items.length, comparisons: closed.comparisons.length, executions: closed.executions.length,
    workOrder: closed.work_orders[0], metrics, report };
  pass('confirmed close is idempotent and preserves devices, valves, environment and history', { kind, id, snapshots: replay.snapshots.length, timeline: timeline.items.length });
  return record;
}
async function verifyNoActive() {
  await nav(/综合态势/);
  await page.getByText('当前无活动事故', { exact: true }).waitFor();
  assert.equal(await page.getByTestId('dashboard-flood').count(), 0);
  await page.getByTestId('leak-summary').waitFor({ state: 'detached' });
  assert.equal(await page.getByTestId('leak-summary').count(), 0);
  await nav(/风险研判/);
  await page.locator('.risk-empty').getByText('暂无活动事故场景', { exact: true }).waitFor();
  const prediction = await get('risk/prediction');
  assert(!prediction.scenarioId && prediction.mlForecast.length === 0 && prediction.physicalForecast.length === 0);
}

(async () => {
  browser = await chromium.launch({ headless: true, executablePath: process.env.CHROME_PATH || '/opt/google/chrome/chrome' });
  page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
  page.on('pageerror', error => result.errors.push(error.message));
  page.on('console', message => { if (message.type() === 'error') result.errors.push(message.text()); });
  await page.addInitScript(() => {
    const Original = window.WebSocket;
    window.__m9LifecycleSockets = []; window.__m9LifecycleEvents = [];
    window.WebSocket = class extends Original {
      constructor(...args) { super(...args); if (String(args[0]).includes('/ws/realtime')) {
        window.__m9LifecycleSockets.push(this);
        this.addEventListener('message', event => {
          const value = JSON.parse(event.data);
          if (value.type === 'REALTIME_STATE') window.__m9LifecycleState = value.data;
          else if (['EMERGENCY_EVENT', 'PIPELINE_LEAK_EVENT'].includes(value.type)) window.__m9LifecycleEvents.push(value);
        });
      } }
    };
  });
  await post('simulation/reset');
  await page.goto(base + '/simulation'); await page.getByTestId('flood-page').waitFor();
  const started = await post('simulation/flood/emergency-demo-start');
  result.floodScenarioId = started.flood.scenarioId;
  await post('simulation/speed', { speed: 10 });
  await until('Flood high risk at T+29min', () => get('realtime/state'), state => state.flood.elapsedSimulationSeconds >= 1740, 240000);
  const floodBefore = await post('simulation/flood/stop');
  assert(floodBefore.flood.riskScore >= 80 && floodBefore.flood.rainfall > 99);
  assert.equal(floodBefore.devices.find(x => x.id === 'P03').fault, 'bearing_degradation');
  const comparison = await post('emergency/compare', { plan_codes: ['FLOOD-A', 'FLOOD-B', 'FLOOD-C'], horizon_minutes: 30 });
  assert.equal(comparison.results.length, 3); assert(comparison.results.every(x => x.timeline.length === 31));
  assert.deepEqual((await get('realtime/state')).flood, floodBefore.flood);
  const execution = await post('emergency/execute', { plan_code: 'FLOOD-B', comparison_id: comparison.id, confirmed_simulation: true });
  assert.equal(execution.status, 'pending');
  await post('simulation/start');
  await until('Flood genuine STABILIZING with risk below 60', () => get('realtime/state'),
    state => state.flood.elapsedSimulationSeconds >= 2500 && state.emergency?.phase === 'STABILIZING' && state.flood.riskScore < 60, 160000);
  const stabilized = await post('simulation/flood/stop');
  assert(stabilized.flood.growthRate < 0 && stabilized.flood.effectivePumpCapacity > floodBefore.flood.effectivePumpCapacity);
  assert(stabilized.flood.rainfall < floodBefore.flood.rainfall, 'record the changing environmental assumption');
  const floodIncident = await archived('FLOOD', result.floodScenarioId); result.floodIncidentId = floodIncident.id;
  pass('real Flood detection → M7 B execution → stable with rain recession', { scenarioId: result.floodScenarioId, incidentId: floodIncident.id, time: stabilized.flood.elapsedSimulationSeconds, risk: stabilized.flood.riskScore });
  await openReview(floodIncident.id);
  await completeWorkOrder(floodIncident.id, '排水班组', '软件演练中 P01/P02 已运行，风险回落；降雨同时减弱，残余积水继续保留。');
  result.flood = await confirmClose(floodIncident.id, 'flood', '已确认软件场景稳定。降雨变化与泵排水共同影响，关闭档案不代表车库积水排空。');
  for (const type of ['SCENARIO_STARTED', 'DEVICE_FAULT', 'PLAN_COMPARED', 'PLAN_SELECTED', 'EXECUTION_STARTED', 'ACTION_COMPLETED', 'RISK_STABILIZED', 'WORK_ORDER_COMPLETED', 'INCIDENT_CLOSED']) assert(result.flood.timelineTypes.includes(type), 'Flood timeline missing ' + type);
  assert(result.flood.metrics.prediction_review.samples > 0, 'actual later observations must exist for due M6 forecasts');
  assert(result.flood.report.response_analysis.includes('降雨'));
  await verifyNoActive();

  await nav(/地下管网/);
  await page.getByRole('button', { name: '泄漏事故模式', exact: true }).click();
  await page.getByTestId('leak-page').waitFor();
  const leakStart = await post('simulation/pipeline-leak/start', {});
  result.leakScenarioId = leakStart.leak?.scenarioId || leakStart.scenarioId;
  assert(result.leakScenarioId);
  await post('simulation/speed', { speed: 10 });
  await until('Leak observations confirm WS-003', () => get('realtime/state'),
    state => state.leak.elapsedSimulationSeconds >= 330 && !!state.leak.confirmedAt, 80000);
  const leakBefore = await post('simulation/pipeline-leak/stop');
  assert.equal(leakBefore.leak.suspectedSegments[0].pipeline_id, 'WS-003');
  const isolation = await post('pipeline-leak/isolation/compare', { pipeline_id: 'WS-003' });
  const option = isolation.options.find(x => x.id === 'option-1');
  assert(option); assert.deepEqual(option.valves, ['V-W-03']); assert.equal(option.affectedBuildings.length, 2);
  await post('pipeline-leak/isolation/execute', { comparison_id: isolation.id, option_id: option.id, confirmed_simulation: true });
  const justIsolated = await get('realtime/state');
  assert.equal(justIsolated.leak.estimatedLeakFlow, leakBefore.leak.estimatedLeakFlow, 'no instant fake leak-flow jump');
  await post('simulation/start');
  await until('Leak gradual isolation → CONTAINED / STABILIZING', () => get('realtime/state'),
    state => state.leak.elapsedSimulationSeconds >= 600 && state.leak.currentStage === 'STABILIZING' && state.leak.leakStatus === 'CONTAINED', 90000);
  const leakStable = await post('simulation/pipeline-leak/stop');
  assert.equal(leakStable.leak.serviceStatus, 'INTERRUPTED'); assert.equal(leakStable.leak.interruptedBuildings.length, 2);
  assert(leakStable.leak.estimatedLeakFlow < .25 && leakStable.leak.riskScore < leakBefore.leak.riskScore);
  const leakIncident = await archived('PIPELINE_LEAK', result.leakScenarioId); result.leakIncidentId = leakIncident.id;
  pass('real leak localization → V-W-03 isolation → contained with service interruption', { scenarioId: result.leakScenarioId, incidentId: leakIncident.id, time: leakStable.leak.elapsedSimulationSeconds, risk: leakStable.leak.riskScore });
  await openReview(leakIncident.id);
  await completeWorkOrder(leakIncident.id, '管网班组', '软件阀门 V-W-03 已关闭，泄漏流量衰减；科研楼 B、实验楼 C 供水中断尚未恢复。');
  result.leak = await confirmClose(leakIncident.id, 'leak', '已确认软件泄漏受控。保持 V-W-03 关闭，科研楼 B 与实验楼 C 供水中断保留；不声明供水恢复。');
  assert.equal(result.leak.after.valves.find(x => x.id === 'V-W-03').status, 'closed');
  for (const type of ['SCENARIO_STARTED', 'LEAK_SUSPECTED', 'LEAK_CONFIRMED', 'PLAN_COMPARED', 'VALVE_CLOSED', 'RISK_STABILIZED', 'WORK_ORDER_COMPLETED', 'INCIDENT_CLOSED']) assert(result.leak.timelineTypes.includes(type), 'Leak timeline missing ' + type);
  assert.equal(result.leak.metrics.prediction_review.samples, 0);
  assert(result.leak.report.impact_analysis.includes('科研楼') && result.leak.report.impact_analysis.includes('实验楼'));
  await verifyNoActive();
  const connectionCount = await page.evaluate(() => window.__m9LifecycleSockets.length);
  assert.equal(connectionCount, 1);
  result.websocket = { connections: connectionCount, events: await page.evaluate(() => window.__m9LifecycleEvents) };
  assert.deepEqual(result.errors, []);
  result.success = true;
  pass('both CLOSED archives retained; Dashboard/Risk idle; one WebSocket; no JS errors');
})().catch(error => {
  result.success = false; result.failure = String(error.stack || error); console.error(error); process.exitCode = 1;
}).finally(async () => {
  // Explicit demo cleanup is separate from business close and never changes CLOSED archives.
  if (page) {
    try {
      await post('simulation/valve/V-W-03/state', { status: 'open' });
      await post('simulation/reset'); await post('simulation/speed', { speed: 1 }); await post('simulation/start');
      const final = await get('realtime/state');
      result.cleanup = { speed: final.speed, running: final.running, floodScenarioId: final.flood.scenarioId,
        leakScenarioId: final.leak.scenarioId, valve: final.valves.find(x => x.id === 'V-W-03') };
    } catch (error) { result.cleanupError = String(error.stack || error); result.success = false; process.exitCode = 1; }
  }
  result.finishedAt = new Date().toISOString();
  fs.writeFileSync(path.join(output, 'M9-lifecycle-results.json'), JSON.stringify(result, null, 2));
  await browser?.close();
});
