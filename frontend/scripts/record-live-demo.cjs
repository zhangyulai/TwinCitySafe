/* Continuous browser video: live UI, REST/WebSocket and persisted replay. No image inputs. */
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const { spawnSync } = require('node:child_process');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '../..');
const work = fs.mkdtempSync(path.join(os.tmpdir(), 'twincity-live-recording-'));
const registry = JSON.parse(fs.readFileSync(path.join(root, 'frontend/node_modules/playwright-core/browsers.json')));
const ffmpeg = registry.browsers.find(b => b.name === 'ffmpeg');
process.env.PLAYWRIGHT_BROWSERS_PATH = path.join(work, 'browser-tools');
const encoderDir = path.join(process.env.PLAYWRIGHT_BROWSERS_PATH, `ffmpeg-${ffmpeg.revision}`);
fs.mkdirSync(encoderDir, { recursive: true });
fs.symlinkSync('/usr/bin/ffmpeg', path.join(encoderDir, 'ffmpeg-linux'));
const { chromium } = require('playwright');
const base = 'http://127.0.0.1:5173';
const probe = process.argv.includes('--probe');
const seven = process.argv.includes('--seven');
const narrated = seven || process.argv.includes('--narrated');
const videoData = seven ? 'docs/video/seven' : 'docs/video';
const narrationEntries = narrated ? JSON.parse(fs.readFileSync(path.join(root,videoData,'narration-cn.json'))) : [];
const output = path.join(root, probe ? 'docs/final/live-recording-probe.mp4' : narrated ? `${videoData}/narrated-capture.mp4` : 'TwinCitySafe-5min-live-demo.mp4');
const evidence = { source: 'Continuous Playwright browser screencast, no screenshot montage, no time compression', work, actions: [], errors: [], samples: [] };
let browser, context, page, storyStart, video, sampler;
let startedScenario = false;
evidence.speechCues=[];evidence.pointerChecks=[];
function narration(id) { if(narrated) evidence.speechCues.push({id,t:(Date.now()-storyStart)/1000}); }
const get = async p => { const r = await fetch(`${base}/api/v1/${p}`); assert(r.ok, `${p}: ${r.status}`); return r.json(); };
function log(action, detail) {
  const t = storyStart ? (Date.now() - storyStart) / 1000 : 0;
  evidence.actions.push({ t, action, detail }); console.log(`${t.toFixed(1)}s ${action}`);
}
async function until(test, timeout = 20000) {
  const begin = Date.now();
  while (Date.now() - begin < timeout) { if (await test()) return; await page.waitForTimeout(350); }
  throw new Error('Required live UI state did not arrive');
}
async function at(seconds) {
  const remain = storyStart + seconds * 1000 - Date.now();
  if (remain > 0) await page.waitForTimeout(remain);
}
async function caption(title, text, mode = '现场仿真 · 10×') {
  log(title, text);
  const entry=narrationEntries.find(x=>x.title===title);if(entry)narration(entry.id);
  await page.evaluate(({ title, text, mode, narrated }) => {
    let panel = document.getElementById('recording-caption');
    if (!panel) {
      panel = document.createElement('div'); panel.id = 'recording-caption';
      panel.style.cssText = `position:fixed;bottom:0;left:0;right:0;z-index:2147483646;height:${narrated?104:68}px;box-sizing:border-box;background:rgba(3,15,25,.96);border-top:2px solid #54d2df;color:#edfaff;display:flex;align-items:${narrated?'flex-start':'center'};gap:22px;padding:${narrated?'8px':'0'} 28px;font-family:"Noto Sans CJK SC",sans-serif;pointer-events:none;`;
      document.body.appendChild(panel);
    }
    panel.replaceChildren();
    const tag = document.createElement('b'); tag.style.cssText='font-size:18px;color:#69d7df;white-space:nowrap'; tag.textContent=title;
    const desc=document.createElement('span');desc.style.cssText='font-size:18px;flex:1';desc.textContent=narrated?'':text;
    const source=document.createElement('span');source.style.cssText='font-size:14px;color:#b4cad4;white-space:nowrap';source.textContent=mode;
    panel.append(tag,desc,source);
  }, { title, text, mode, narrated });
}
async function click(locator) {
  await locator.evaluate(el=>el.scrollIntoView({block:'center',behavior:'instant'}));
  const box = await locator.boundingBox(); assert(box, 'Click target must be visible');
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2, { steps: 18 });
  const label=(await locator.innerText()).trim().slice(0,32)||await locator.getAttribute('aria-label')||'点击';
  await page.evaluate(label=>window.__recordingSetLabel?.('点击：'+label),label);
  await locator.evaluate(el=>el.animate([{outline:'3px solid #ffdc57',outlineOffset:'4px'},{outline:'3px solid transparent',outlineOffset:'9px'}],{duration:1500}));
  await page.waitForTimeout(430); await locator.click();
  log('点击',label);
}
async function select(locator,value){
  await locator.scrollIntoViewIfNeeded();const b=await locator.boundingBox();assert(b);
  await page.mouse.move(b.x+b.width/2,b.y+b.height/2,{steps:18});
  await page.evaluate(label=>window.__recordingSetLabel?.('选择：'+label),await locator.getAttribute('aria-label')||value);
  await page.waitForTimeout(450);await locator.selectOption(value);
  await page.evaluate(()=>window.__recordingPulse?.());log('选择',value);await page.waitForTimeout(250);
}
async function top() { await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'smooth' })); await page.waitForTimeout(550); }
async function nav(name) { await top(); await click(page.getByRole('navigation').getByRole('link', { name: new RegExp(name) })); await page.waitForTimeout(900); }
async function show(locator) { await locator.evaluate(el => el.scrollIntoView({ behavior: 'smooth', block: 'center' })); await page.waitForTimeout(750); }
async function orbit() {
  const canvas = page.getByTestId('twin-scene').locator('canvas').first();
  await show(canvas); const b = await canvas.boundingBox();
  await page.mouse.move(b.x + b.width * .56, b.y + b.height * .48, { steps: 15 });
  await page.mouse.down(); await page.mouse.move(b.x + b.width * .68, b.y + b.height * .52, { steps: 65 }); await page.mouse.up();
  await page.waitForTimeout(1100);
}
async function reset() {
  await top(); await click(page.getByTestId('demo-reset'));
  await until(async () => { const s=await get('realtime/state');return !s.flood.scenarioId&&!s.leak.scenarioId&&s.speed===1; });
}
async function start(kind) {
  await top(); await select(page.getByLabel('演示场景',{exact:true}),kind);
  await click(page.getByTestId('demo-start')); startedScenario=true;
  await until(async()=>!!(await get('realtime/state'))[kind].scenarioId);
}
async function pause() { await top();await click(page.getByTestId('demo-pause')); await until(async()=>!(await get('realtime/state')).running); }
async function resume() { await top();await click(page.getByTestId('demo-pause')); await until(async()=>(await get('realtime/state')).running); }
async function review(id) {
  await nav('事件复盘'); const item=page.locator(`[data-incident-id="${id}"]`);await click(item);
  await page.getByTestId('replay-scrubber').waitFor();await page.waitForTimeout(700);
}
async function type(locator,text) {
  await click(locator);await locator.fill('');await locator.pressSequentially(text,{delay:65});log('填写',text);
}
async function sevenStory(flood) {
  narration('intro');await orbit();await show(page.getByTestId('park-operation-state'));
  await at(17);narration('dashboard');await top();await click(page.getByRole('button',{name:'系统状态',exact:true}));
  await page.waitForTimeout(2500);await click(page.getByRole('button',{name:'关闭系统状态',exact:true}));await show(page.locator('.dashboard-bottom'));
  await at(34);narration('pipeline');await nav('地下管网');
  await click(page.locator('.pipe-categories').getByRole('button',{name:'给水',exact:true}));
  await type(page.getByLabel('搜索管段'),'WS-003');await click(page.locator('[data-pipeline-id="WS-003"]'));await show(page.locator('.pipe-detail'));
  await at(52);narration('trace');await click(page.getByRole('button',{name:'上游追踪',exact:true}));await page.waitForTimeout(1800);
  await click(page.getByRole('button',{name:'下游追踪',exact:true}));await page.waitForTimeout(1600);await click(page.getByRole('button',{name:'影响分析',exact:true}));
  await at(67);narration('topology');await show(page.getByTestId('pipeline-topology'));await page.waitForTimeout(2800);
  await click(page.getByRole('button',{name:'隔离方案',exact:true}));await page.locator('.isolation-option').first().waitFor();await show(page.locator('.isolation-panel'));
  await at(82);narration('flood');await start('flood');await page.getByTestId('flood-page').waitFor();await orbit();
  await at(107);narration('operation');await nav('智慧运维');await click(page.getByTestId('device-P03'));await show(page.getByTestId('health-card'));
  await at(125);narration('trends');await show(page.getByTestId('trend-chart'));
  await at(138);narration('risk');await nav('风险研判');
  await page.waitForFunction(()=>document.querySelectorAll('.risk-horizon').length===3&&document.querySelectorAll('.risk-feature').length>0,null,{timeout:25000});await show(page.getByTestId('risk-forecast'));
  await at(158);narration('comparison');await show(page.getByTestId('risk-comparison'));
  await at(168);narration('charts');await show(page.getByTestId('risk-charts'));
  await at(184);narration('emergency');await nav('应急推演');await pause();await click(page.getByTestId('emergency-open'));await click(page.getByTestId('emergency-compare'));
  await page.getByTestId('emergency-baseline').waitFor();await show(page.getByTestId('emergency-baseline'));
  await at(202);narration('execute');await click(page.locator('[data-plan="FLOOD-B"] button'));await page.waitForTimeout(1700);await click(page.getByTestId('emergency-execute'));await resume();await show(page.getByTestId('twin-scene'));
  await at(215);narration('effect');
  await at(230);narration('switch');await reset();
  await at(239);narration('leak');await start('leak');await page.getByTestId('leak-page').waitFor();await orbit();
  await at(260);narration('leak_details');await show(page.getByTestId('leak-page'));
  await at(275);await until(async()=>!!(await get('realtime/state')).leak.confirmedAt,15000);narration('isolate');await pause();await click(page.getByTestId('leak-compare'));
  await page.locator('[data-option="option-1"] button').waitFor();await page.waitForTimeout(1200);await click(page.locator('[data-option="option-1"] button'));await page.waitForTimeout(1700);await click(page.getByTestId('leak-execute'));await resume();await show(page.getByTestId('twin-scene'));
  await at(294);narration('isolated');
  await at(309);narration('stable');await until(async()=>(await get('realtime/state')).leak.currentStage==='STABILIZING',20000);await pause();
  const live=await get('realtime/state');evidence.isolation={flow:live.leak.estimatedLeakFlow,status:live.leak.serviceStatus,stage:live.leak.currentStage};
  let incident;await until(async()=>{incident=(await get('incidents?limit=100')).items.find(x=>x.scenario_id===live.leak.scenarioId);return incident?.status==='STABILIZING';});
  evidence.currentLeakIncident=incident.id;await review(incident.id);await show(page.getByTestId('review-work-orders'));
  await at(325);narration('workorder');const detail=await get(`incidents/${incident.id}`);assert.equal(detail.work_orders.length,1);const order=detail.work_orders[0];
  const card=page.locator(`[data-work-order="${order.id}"]`);await type(card.getByLabel('接单班组',{exact:true}),'管网演示班组');await click(card.getByRole('button',{name:'接单',exact:true}));
  await card.getByRole('button',{name:'开始处理',exact:true}).waitFor();await click(card.getByRole('button',{name:'开始处理',exact:true}));
  await card.getByRole('button',{name:'完成工单',exact:true}).waitFor();await type(card.getByLabel('工单处理结果',{exact:true}),'已执行 V-W-03 隔离，泄漏受控；科研楼与实验楼仍有供水影响。');await click(card.getByRole('button',{name:'完成工单',exact:true}));
  await until(async()=>(await get(`work-orders/${order.id}`)).status==='COMPLETED');await page.getByRole('status').filter({hasText:'工单状态已保存。'}).waitFor();evidence.completedWorkOrder=await get(`work-orders/${order.id}`);
  await at(343);narration('close');await type(page.getByLabel('事件关闭说明',{exact:true}),'软件演练已稳定；保留关闭阀门及两栋建筑的供水影响，待后续修复。');await click(page.getByRole('button',{name:'人工确认关闭事件',exact:true}));
  await page.getByRole('status').filter({hasText:'事件已关闭并保留历史档案。'}).waitFor();assert.equal((await get(`incidents/${incident.id}`)).status,'CLOSED');
  await show(page.getByTestId('review-report'));await click(page.getByRole('button',{name:'生成复盘报告',exact:true}));await page.getByTestId('review-report').locator('article').first().waitFor();
  await at(362);narration('archive');await review(flood.id);
  await at(373);narration('review_flood');await click(page.locator('[data-jump=peak]'));await select(page.getByLabel('回放速度',{exact:true}),'5');await click(page.getByTestId('replay-play'));await show(page.getByTestId('twin-scene'));
  const playbackStart=Number(await page.getByTestId('replay-scrubber').inputValue());await at(384);await click(page.getByTestId('replay-pause'));const playbackEnd=Number(await page.getByTestId('replay-scrubber').inputValue());assert(playbackEnd>playbackStart);evidence.replay={start:playbackStart,end:playbackEnd};await show(page.getByTestId('replay-chart'));
  await at(390);narration('review_leak');await review(incident.id);await click(page.locator('[data-jump=response]'));await select(page.getByLabel('回放速度',{exact:true}),'5');await click(page.getByTestId('replay-play'));await show(page.getByTestId('twin-scene'));await at(405);await click(page.getByTestId('replay-pause'));
  narration('report');await show(page.getByTestId('review-report'));await at(414);narration('ending');await at(421);
  assert.equal(evidence.errors.length,0,evidence.errors.join('; '));assert(evidence.pointerChecks.every(x=>x.visible));
  assert.equal(evidence.speechCues.length,narrationEntries.length);evidence.modules=['综合态势','地下管网','智慧运维','风险研判','应急推演','事件复盘'];
}
async function main() {
  const readiness=await get('system/readiness');assert(readiness.ready);
  const initial=await get('realtime/state');assert(!initial.flood.scenarioId&&!initial.leak.scenarioId,'Please finish the existing incident before recording');
  const archives=(await get('incidents?status=CLOSED&limit=100')).items;
  const flood=archives.find(x=>x.incident_type==='FLOOD'),leak=archives.find(x=>x.incident_type==='PIPELINE_LEAK');assert(flood&&leak);
  evidence.archives={flood:flood.id,leak:leak.id};
  browser=await chromium.launch({headless:true,executablePath:'/opt/google/chrome/chrome',args:['--no-sandbox','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
  context=await browser.newContext({viewport:{width:1920,height:1080},deviceScaleFactor:1,locale:'zh-CN',recordVideo:{dir:work,size:{width:1920,height:1080}}});
  page=await context.newPage();page.setDefaultTimeout(18000);video=page.video();
  page.on('pageerror',e=>evidence.errors.push(e.message));
  page.on('dialog',async dialog=>{log('确认操作',dialog.message());await page.waitForTimeout(700);await dialog.accept();});
  await page.addInitScript(()=>{
    window.addEventListener('DOMContentLoaded',()=>{
      const cursor=document.createElement('div');cursor.id='recording-pointer';cursor.style.cssText='position:fixed;width:46px;height:52px;z-index:2147483647;pointer-events:none;left:960px;top:500px;filter:drop-shadow(0 2px 4px #000);';
      cursor.innerHTML='<svg width="46" height="52" viewBox="0 0 46 52"><circle cx="12" cy="14" r="12" fill="#ffdd5540"/><path d="M5 3 L5 34 L14 26 L23 44 L30 40 L21 23 L35 23 Z" fill="#ffdf57" stroke="#13222f" stroke-width="3"/><path d="M7 7 L7 29" stroke="white" stroke-width="2"/></svg>';
      const label=document.createElement('div');label.style.cssText='position:absolute;top:49px;left:0;background:#132332ed;border:1px solid #ffdb55;color:#ffe78a;border-radius:5px;padding:4px 8px;white-space:nowrap;font:16px "Noto Sans CJK SC",sans-serif';label.textContent='鼠标位置';cursor.appendChild(label);document.body.appendChild(cursor);
      const update=(x,y)=>{x=Math.max(8,Math.min(innerWidth-50,x));y=Math.max(8,Math.min(innerHeight-60,y));cursor.style.left=x+'px';cursor.style.top=y+'px';label.style.left=x>innerWidth-330?'auto':'0';label.style.right=x>innerWidth-330?'0':'auto';label.style.top=y>innerHeight-180?'-32px':'49px';window.__recordingPointer={x,y};};
      update(960,500);
      document.addEventListener('mousemove',e=>update(e.clientX,e.clientY),true);
      document.addEventListener('pointermove',e=>update(e.clientX,e.clientY),true);
      window.__recordingSetLabel=text=>{label.textContent=text;};
      window.__recordingPulse=()=>cursor.animate([{filter:'drop-shadow(0 0 2px #ffdd55)',transform:'scale(1)'},{filter:'drop-shadow(0 0 15px #ffdd55)',transform:'scale(1.22)'},{filter:'drop-shadow(0 2px 4px #000)',transform:'scale(1)'}],{duration:1100});
      document.addEventListener('mousedown',()=>window.__recordingPulse(),true);
    });
  });
  await page.goto(base+'/dashboard?demo=1');await page.getByTestId('twin-scene').locator('canvas').waitFor();await page.waitForTimeout(2000);
  storyStart=Date.now();evidence.startedAt=new Date(storyStart).toISOString();
  await caption('孪城智安 · TwinCitySafe','监测、预测、推演、处置、复盘：五分钟真实页面操作','连续实录 · 正常监测');
  if (probe) {await orbit();await at(6);return;}
  sampler=setInterval(()=>{get('realtime/state').then(s=>evidence.samples.push({t:(Date.now()-storyStart)/1000,simulationTime:s.simulationTime,running:s.running,flood:{id:s.flood.scenarioId,water:s.flood.waterLevel,risk:s.flood.riskScore},leak:{id:s.leak.scenarioId,flow:s.leak.estimatedLeakFlow,risk:s.leak.riskScore}})).catch(()=>{});page.evaluate(()=>{const el=document.getElementById('recording-pointer'),b=el?.getBoundingClientRect();return !!b&&b.left>=0&&b.top>=0&&b.right<=innerWidth&&b.bottom<=innerHeight&&getComputedStyle(el).visibility!=='hidden';}).then(visible=>evidence.pointerChecks.push({t:(Date.now()-storyStart)/1000,visible})).catch(()=>{});},3000);
  if(seven){await sevenStory(flood);return;}
  await orbit();await top();await click(page.getByRole('button',{name:'系统状态',exact:true}));await page.waitForTimeout(2400);await click(page.getByRole('button',{name:'关闭系统状态',exact:true}));
  await at(15);await caption('01 · 暴雨内涝','点击启动；降雨、积水与设备由同一实时引擎推进');await start('flood');
  await page.getByTestId('flood-page').waitFor();await orbit();await at(40);
  await caption('02 · 智慧运维','观察 P03 轴承退化：温度、振动、效率与健康状态变化');await nav('智慧运维');await orbit();await at(58);
  await page.mouse.wheel(0,540);await page.waitForTimeout(1700);await at(65);
  await caption('03 · 风险研判','实际输入驱动 +10 / +20 / +30 分钟预测；物理模型与 XGBoost 对照');await nav('风险研判');
  await page.waitForFunction(()=>document.querySelectorAll('.risk-horizon').length===3&&document.querySelectorAll('.risk-feature').length>0,null,{timeout:25000});
  await show(page.getByTestId('risk-forecast'));await at(84);narration('risk_compare');await show(page.getByTestId('risk-comparison'));await at(94);narration('risk_charts');await show(page.getByTestId('risk-charts'));await at(109);
  await caption('04 · 应急方案比较','暂停后比较同一基线的 A / B / C；方案由操作者选择并确认');await nav('应急推演');await pause();
  await click(page.getByTestId('emergency-open'));await click(page.getByTestId('emergency-compare'));await page.getByTestId('emergency-baseline').waitFor();await show(page.getByTestId('emergency-baseline'));await at(123);
  await click(page.locator('[data-plan="FLOOD-B"] button'));await page.waitForTimeout(1500);await click(page.getByTestId('emergency-execute'));await resume();
  await caption('方案 B 已执行','备用泵逐步启动；暴雨期间排水能力增加不代表积水立即消失');await show(page.getByTestId('twin-scene'));await at(150);
  await caption('切换演示场景','本次暴雨演练重置并留档；稍后查看已关闭事故的完整历史');await reset();await at(158);
  await caption('05 · 管网泄漏','启动真实软件泄漏；观察压力下降、流量变化与疑似管段排名');await start('leak');await page.getByTestId('leak-page').waitFor();await orbit();await at(181);
  narration('leak_details');await show(page.getByTestId('leak-page'));await at(197);
  await until(async()=>!!(await get('realtime/state')).leak.confirmedAt,15000);
  await caption('06 · 阀门隔离','WS-003 定位后，比较隔离候选并确认关闭 V-W-03');await pause();await click(page.getByTestId('leak-compare'));await page.waitForTimeout(1200);
  await click(page.locator('[data-option="option-1"] button'));await page.waitForTimeout(1700);await click(page.getByTestId('leak-execute'));await resume();
  await caption('隔离效果持续演化','泄漏流量逐步下降；两栋建筑的供水影响单独保留');await show(page.getByTestId('twin-scene'));await at(238);
  const isolated=await get('realtime/state');evidence.isolation={flow:isolated.leak.estimatedLeakFlow,status:isolated.leak.serviceStatus};assert(isolated.leak.serviceStatus==='INTERRUPTED');
  await caption('演练状态留档','重置恢复正常监测；接下来播放数据库中已关闭的真实仿真档案');await reset();startedScenario=false;
  await at(245);await caption('07 · 暴雨历史复盘','切换至已关闭档案：关键节点、三维水位与时间轴联动','历史回放 · 已保存档案');await review(flood.id);
  await click(page.locator('[data-jump=peak]'));await select(page.getByLabel('回放速度',{exact:true}),'5');await click(page.getByTestId('replay-play'));await show(page.getByTestId('twin-scene'));const playbackStart=await page.getByTestId('replay-scrubber').inputValue();await at(265);
  await click(page.getByTestId('replay-pause'));const playbackEnd=await page.getByTestId('replay-scrubber').inputValue();assert(Number(playbackEnd)>Number(playbackStart));evidence.replay={start:playbackStart,end:playbackEnd};
  narration('review_chart');await show(page.getByTestId('replay-chart'));await at(272);
  await caption('08 · 泄漏历史复盘','回放定位与隔离过程；关闭事件仍保留供水中断记录','历史回放 · 已保存档案');await review(leak.id);await click(page.locator('[data-jump=response]'));await select(page.getByLabel('回放速度',{exact:true}),'5');await click(page.getByTestId('replay-play'));await show(page.getByTestId('twin-scene'));await at(286);
  await click(page.getByTestId('replay-pause'));await show(page.getByTestId('review-report'));await at(293);
  await caption('孪城智安 · 安全闭环','安全状态可视、风险趋势可判、处置方案可比、事件全过程可复盘','连续实录 · 演示结束');await nav('综合态势');await show(page.getByTestId('twin-scene'));await at(301);
  assert.equal(evidence.errors.length,0,evidence.errors.join('; '));
  assert(evidence.pointerChecks.every(x=>x.visible),'Pointer must stay within the recorded viewport');
}
main().then(()=>{evidence.success=true;}).catch(e=>{evidence.failure=e.stack;console.error(e);process.exitCode=1;}).finally(async()=>{
  clearInterval(sampler);
  const storyEnd=Date.now();evidence.finishedAt=new Date(storyEnd).toISOString();evidence.storySeconds=(storyEnd-storyStart)/1000;
  if(startedScenario){try{await fetch(`${base}/api/v1/demo/reset`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({confirmed:true})});}catch(e){evidence.cleanupError=String(e);}}
  await context?.close();const raw=video?await video.path():null;await browser?.close();evidence.rawVideo=raw;
  if(evidence.success&&raw){
    const info=JSON.parse(spawnSync('/usr/bin/ffprobe',['-v','error','-show_entries','format=duration','-of','json',raw],{encoding:'utf8'}).stdout);
    const duration=Number(info.format.duration);const trim=Math.max(0,duration-evidence.storySeconds);evidence.rawDuration=duration;evidence.trimStart=trim;
    assert(duration>= (probe?5:seven?420:300),'Continuous raw recording must cover the full duration');
    // Browser screencasts emit sparse frames while a page is still. Resolve
    // their timestamps before cutting so a static final page keeps its duration.
    const encode=spawnSync('/usr/bin/ffmpeg',['-hide_banner','-loglevel','error','-y','-ss',String(trim),'-i',raw,'-vf','fps=25:start_time=0','-t',probe?'5':seven?'420':'300','-an','-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p','-r','25','-movflags','+faststart',output],{stdio:['ignore','inherit','inherit']});
    if(encode.status!==0){evidence.success=false;process.exitCode=1;}else{evidence.output=output;console.log('Saved actual continuous browser video:',output);}
  }
  fs.mkdirSync(path.join(root,videoData),{recursive:true});fs.writeFileSync(path.join(root,videoData,probe?'probe.json':narrated?'narrated-recording.json':'live-recording.json'),JSON.stringify(evidence,null,2));
});
