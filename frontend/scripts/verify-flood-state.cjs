// Deterministic local state fixtures complement the real-network flood scenario.
const {chromium}=require('playwright');const assert=require('node:assert/strict');const fs=require('node:fs');const path=require('node:path');
(async()=>{const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH||'/opt/google/chrome/chrome'});
 try{const page=await browser.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto((process.env.M5_BASE_URL||'http://127.0.0.1:5173')+'/simulation');await page.getByTestId('flood-page').waitFor();
 const result=await page.evaluate(async()=>{
  const {useRealtimeStore}=await import('/src/store/useRealtimeStore.ts');const store=useRealtimeStore();store.disconnect();
  const initial=JSON.parse(JSON.stringify(store.state));let revision=initial.revision;
  function apply(elapsed,id='fixture-event',session=initial.sessionId){store.applyRealtimeState({...initial,sessionId:session,revision:++revision,simulationTime:elapsed,timestamp:new Date(Date.parse(initial.timestamp)+revision*1000).toISOString(),flood:{...initial.flood,scenarioId:id,elapsedSimulationSeconds:elapsed}},'stream');}
  for(let i=0;i<=2000;i++)apply(i);const cap=store.floodHistory.length;
  apply(2000);const paused=store.floodHistory.length;
  apply(5601);const expired=store.floodHistory.length;
  apply(0,'new-event');const switched=store.floodHistory.length;
  apply(10,'new-event');store.disconnect();const retained=store.floodHistory.length;
  apply(20,'new-event','new-session');const session=store.floodHistory.length;
  apply(0,null,'new-session');const reset=store.floodHistory.length;
  return {cap,paused,expired,switched,retained,session,reset};
 });
 assert.deepEqual(result,{cap:1800,paused:1800,expired:1,switched:1,retained:2,session:1,reset:0});assert.deepEqual(errors,[]);
 fs.writeFileSync(process.env.M5_STATE_OUTPUT||path.resolve(__dirname,'../../docs/M5-state-results.json'),JSON.stringify({scope:'Local store fixtures; physics and network are tested separately.',...result,errors},null,2)+'\n');console.log('PASS flood history bound, simulated-time expiry, paused heartbeat, scenario/session switch, disconnect and reset',result);
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
