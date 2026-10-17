const {chromium}=require('playwright');const assert=require('node:assert/strict');const fs=require('node:fs');const path=require('node:path');
const base=process.env.M4_BASE_URL||'http://127.0.0.1:5173';const output=process.env.M4_OUTPUT_DIR||path.resolve(__dirname,'../../docs');fs.mkdirSync(output,{recursive:true});
const result={checks:[],errors:[],performance:{},screenshots:[]};let browser,page;
const pass=(name,detail)=>{result.checks.push({name,detail});console.log('PASS',name,detail??'');};
(async()=>{
 browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH||'/opt/google/chrome/chrome'});page=await browser.newPage({viewport:{width:1920,height:1080}});
 page.on('pageerror',e=>result.errors.push(e.message));page.on('console',m=>{if(m.type()==='error')result.errors.push(m.text());});
 await page.addInitScript(()=>{const W=window.WebSocket;window.__m4Sockets=[];window.WebSocket=class extends W{constructor(...args){super(...args);if(String(args[0]).includes("/ws/realtime"))window.__m4Sockets.push(this);}};});
 const api=async(path,data)=>{const res=data===undefined?await page.request.get(base+'/api/v1/'+path):await page.request.post(base+'/api/v1/'+path,{data});assert(res.ok(),path+' '+res.status());return res.json();};
 const debug=()=>page.getByTestId('twin-scene').evaluate(e=>e.__twinDebug);
 const settle=()=>page.waitForFunction(()=>{const d=document.querySelector('[data-testid=twin-scene]')?.__twinDebug;return d&&d.pipelineCount===32&&!d.isAnimating&&d.fps>0;});
 const shot=async(name)=>{const file=path.join(output,'M4-'+name+'.png');await page.screenshot({path:file,fullPage:true});result.screenshots.push(file);};
 await api('simulation/start',{});await api('simulation/speed',{speed:1});
 const net=await api('pipelines/network');for(const v of net.valves.filter(v=>v.status!=='open'))await api('simulation/valve/'+v.id+'/state',{status:'open'});
 await page.goto(base+'/pipeline');await settle();await page.waitForFunction(()=>parseFloat(document.querySelector('[data-testid=pipe-flow]')?.textContent??'')>0);
 assert.equal((await debug()).mode,'underground');assert.equal((await debug()).pipelineCount,32);assert.equal(await page.evaluate(()=>window.__m4Sockets.length),1);
 const initial=await debug();const offsets=initial.flowOffsets;await page.waitForTimeout(1500);assert.notEqual(offsets.find(e=>e.id==='WS-003').offset,(await debug()).flowOffsets.find(e=>e.id==='WS-003').offset);
 pass('32 assets, automatic underground, one socket, live detail and shader flow');
 await page.locator('.pipe-categories').getByRole('button',{name:'给水',exact:true}).click();assert.equal(await page.locator('.pipe-row').count(),11);assert((await debug()).live.pipelines.filter(p=>p.visible).every(p=>p.type==='water'));
 await page.getByLabel('搜索管段').fill('WS-003');assert.equal(await page.locator('.pipe-row').count(),1);await page.locator('[data-pipeline-id=WS-003]').click();await page.getByLabel('搜索管段').fill('');
 await page.getByRole('button',{name:'上游追踪',exact:true}).click();await page.getByTestId('trace-result').filter({hasText:'WS-SOURCE-01'}).waitFor();
 await page.getByRole('button',{name:'下游追踪',exact:true}).click();await page.getByTestId('affected-buildings').filter({hasText:'科研楼 B'}).waitFor();assert.match(await page.getByTestId('affected-buildings').innerText(),/实验楼 C/);
 await page.getByRole('button',{name:'影响分析',exact:true}).click();await page.waitForTimeout(300);assert.match(await page.getByTestId('affected-buildings').innerText(),/科研楼 B/);
 await page.getByRole('button',{name:'隔离方案',exact:true}).click();await page.locator('.isolation-option').first().waitFor();assert.equal(await page.locator('.isolation-option').count(),3);await page.locator('.isolation-option').first().click();
 pass('type/search filters, upstream/downstream/building impact, three computed isolation candidates');await page.getByTestId('twin-scene').scrollIntoViewIfNeeded();await shot('pipeline-options');
 // Real ECharts graph click, using its coordinate transform only to locate visible targets.
 await page.getByTestId('pipeline-topology').scrollIntoViewIfNeeded();const graph=await page.getByTestId('pipeline-topology').evaluate(e=>e.__topologyDebug);const edge=graph.edges.find(e=>e.id==='WS-007');await page.mouse.click(edge.x,edge.y);
 await page.waitForFunction(()=>document.querySelector('[data-testid=twin-scene]')?.dataset.selectedPipeline==='WS-007');
 assert.match(await page.locator('.pipe-detail h3').innerText(),/WS-007/);
 await page.getByTestId('pipeline-topology').scrollIntoViewIfNeeded();const node=await page.getByTestId('pipeline-topology').evaluate(e=>e.__topologyDebug.nodes.find(n=>n.id==='V-W-02'));await page.mouse.click(node.x,node.y);await page.waitForFunction(()=>document.querySelector('.valve-list .selected')?.textContent.includes('V-W-02'));
 await page.getByTestId('twin-scene').scrollIntoViewIfNeeded();await settle();
 // Select an actual visible pipe with the raycaster.
 const pipes=(await debug()).live.pipelines.filter(p=>p.visible);let hit=false;
 for(const p of pipes){const box=await page.getByTestId('twin-scene').boundingBox();if(p.screen.x<box.x||p.screen.x>box.x+box.width||p.screen.y<box.y||p.screen.y>box.y+box.height)continue;await page.mouse.click(p.screen.x,p.screen.y);await page.waitForTimeout(100);const id=(await debug()).selectedPipelineId;if(id&&id!=='WS-007'){assert.equal((await page.getByTestId('pipeline-topology').evaluate(e=>e.__topologyDebug)).selected,id);hit=true;break;}}
 assert(hit,'real 3D pipe raycast updates graph');pass('real 2D edge/node clicks focus 3D; real 3D pipe click selects 2D');
 await page.locator('[data-pipeline-id=WS-003]').click();await settle();await page.getByTestId('twin-scene').scrollIntoViewIfNeeded();
 await api('simulation/speed',{speed:10});const before=await api('pipelines/WS-003/realtime');
 await page.getByLabel('V-W-02 阀门状态',{exact:true}).selectOption('closed');await page.waitForFunction(()=>document.querySelector('[data-testid=pipe-status]')?.textContent.includes('隔离'));
 const first=await api('pipelines/WS-003/realtime');await page.waitForTimeout(3500);const later=await api('pipelines/WS-003/realtime');assert(first.flow>0&&first.flow<=before.flow+.1);assert(later.flow<first.flow);
 assert.equal((await debug()).live.pipelines.find(p=>p.id==='WS-003').status,'isolated');assert.equal((await debug()).live.pipelines.find(p=>p.id==='WS-003').color,'#65747f');assert.match(await page.getByTestId('affected-buildings').innerText(),/科研楼 B/);await shot('valve-closed');
 await page.getByLabel('V-W-02 阀门状态',{exact:true}).selectOption('open');await page.waitForFunction(()=>document.querySelector('[data-testid=pipe-status]')?.textContent.includes('正常'));await page.waitForTimeout(4000);const recovered=await api('pipelines/WS-003/realtime');assert(recovered.flow>later.flow);await api('simulation/speed',{speed:1});
 pass('valve close yields isolated geometry and smooth flow decline; reopening recovers',{before:before.flow,first:first.flow,later:later.flow,recovered:recovered.flow});
 // Warm all materials once before measuring resource stability.
 await page.locator('.pipe-categories').getByRole('button',{name:'全部',exact:true}).click();await page.getByTestId('twin-scene').scrollIntoViewIfNeeded();await page.waitForTimeout(2000);
 const resources=await debug();const ids=net.edges.filter(e=>e.pipelineType==='water').map(e=>e.id);
 for(let i=0;i<50;i++){await page.locator(`[data-pipeline-id="${ids[i%ids.length]}"]`).click();}
 await settle();await page.getByTestId('twin-scene').scrollIntoViewIfNeeded();const after=await debug();
 assert.equal(resources.geometries,after.geometries);assert.equal(resources.textures,after.textures);assert.equal(resources.materialCount,after.materialCount);
 pass('50 pipe selections preserve geometry/material/texture counts',{before:{geometry:resources.geometries,material:resources.materialCount,texture:resources.textures},after:{geometry:after.geometries,material:after.materialCount,texture:after.textures}});
 await page.locator('[data-pipeline-id=WS-003]').click();await settle();await page.getByTestId('twin-scene').scrollIntoViewIfNeeded();await page.mouse.move(5,5);await page.waitForTimeout(2500);result.performance.pipelineFPS=(await debug()).fps;
 await shot('pipeline-normal');await page.setViewportSize({width:1440,height:1000});await page.waitForTimeout(2000);assert(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth));await shot('pipeline-1440');
 await page.getByRole('navigation').getByRole('link',{name:/事件复盘/}).click();await page.waitForFunction(()=>document.querySelectorAll('canvas').length===0);assert.equal(await page.locator('canvas').count(),0);await page.getByRole('navigation').getByRole('link',{name:/地下管网/}).click();await settle();assert.equal(await page.evaluate(()=>window.__m4Sockets.length),1);
 pass('1440 layout has no overflow; navigation disposes scenes/charts and retains one realtime socket');
 assert.deepEqual(result.errors,[]);fs.writeFileSync(path.join(output,'M4-browser-results.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result,null,2));
})().catch(e=>{console.error(e);process.exitCode=1;}).finally(async()=>{if(page){await page.request.post(base+'/api/v1/simulation/valve/V-W-02/state',{data:{status:'open'}}).catch(()=>{});await page.request.post(base+'/api/v1/simulation/speed',{data:{speed:1}}).catch(()=>{});}await browser?.close();});
