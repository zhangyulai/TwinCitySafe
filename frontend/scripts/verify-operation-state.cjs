// Complement real-network operation E2E with deterministic local store/empty-model fixtures.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
(async()=>{
 const executablePath=process.env.CHROME_PATH||(fs.existsSync('/opt/google/chrome/chrome')?'/opt/google/chrome/chrome':undefined);
 const browser=await chromium.launch({executablePath,headless:true});
 try {
  const page=await browser.newPage({viewport:{width:1440,height:900}});
  const errors=[];page.on('pageerror',error=>errors.push(error.message));
  await page.goto((process.env.M3_BASE_URL||'http://127.0.0.1:5173')+'/operation');
  await page.waitForFunction(()=>document.querySelector('[data-testid=anomaly-card]')?.dataset.level==='normal');
  const result=await page.evaluate(async()=>{
   const {useRealtimeStore}=await import('/src/store/useRealtimeStore.ts');
   const store=useRealtimeStore();store.disconnect();
   const initial=JSON.parse(JSON.stringify(store.state));
   for(let index=1;index<=305;index++)store.applyRealtimeState({...initial,revision:initial.revision+index,simulationTime:initial.simulationTime+index,timestamp:new Date(Date.parse(initial.timestamp)+index*1000).toISOString()});
   const buffered=store.deviceHistory.P03.length;
   const paused={...JSON.parse(JSON.stringify(store.state)),running:false,revision:store.state.revision+1,timestamp:new Date(Date.parse(store.state.timestamp)+301000).toISOString()};
   store.applyRealtimeState(paused);
   const expired=store.deviceHistory.P03.length;
   const fallback=JSON.parse(JSON.stringify(store.state));fallback.revision++;
   const device=fallback.devices.find(d=>d.id==='P03');
   device.analysis={...device.analysis,modelAvailable:false,modelVersion:null,evaluated:false,anomalyScore:null,rawScore:null,isAnomaly:false,level:'unavailable',explanation:'异常模型未加载，仍显示规则健康指数。',activeAlarmId:null,advice:{priority:'P3',title:'恢复诊断模型',message:'请加载仿真训练模型；当前不能据此判断多变量异常。'}};
   store.applyRealtimeState(fallback);
   return {buffered,expired,retainedDevice:store.getDeviceById('P03').id};
  });
  assert.equal(result.buffered,300);assert.equal(result.expired,0);assert.equal(result.retainedDevice,'P03');
  await page.getByTestId('anomaly-card').filter({hasText:'异常模型未加载'}).waitFor();
  assert(Number(await page.getByTestId('health-card').getAttribute('data-value'))>0);
  assert.equal(await page.locator('[data-testid=twin-scene] canvas').count(),1);
  assert.deepEqual(errors,[]);
  fs.writeFileSync(process.env.M3_STATE_OUTPUT||path.resolve(__dirname,'../../docs/M3-state-results.json'),JSON.stringify({...result,modelMissingUI:true,errors,scope:'Local valid state fixtures; actual missing-file inference is tested in pytest.'},null,2)+'\n');
  console.log('PASS 300-point bound, paused expiry, retained data and missing-model UI',JSON.stringify(result));
 } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
