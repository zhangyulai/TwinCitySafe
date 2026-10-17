import {computed,ref,shallowRef} from 'vue';
import {defineStore} from 'pinia';
import {isAxiosError} from 'axios';
import {reviewApi} from '../api/review';
import type {Incident,IncidentMetrics,ReplayData,ReplayGap,ReplaySceneState,ReplaySnapshot,ReviewReport} from '../types/review';
// Only measured continuous quantities interpolate. All statuses, identities, ranks,
// open percentages, event metadata and collections remain at the left sample.
const continuous=new Set(['rainfall','temperature','humidity','windSpeed','b2WaterLevel','b2WaterArea','waterLevel','waterArea','floodVolume','riskScore','pressure','flow','inletPressure','outletPressure','inletFlow','outletFlow','upstreamPressure','downstreamPressure','pipelineFlow','estimatedLeakFlow','detectionScore','pressureDropRate','flowChangeRate','pumpCapacity','effectivePumpCapacity','pumpEfficiency','efficiency','startupProgress','current','rpm','vibration','health','surfaceInflow','naturalDrainage','outflow','growthRate','estimatedServiceLoss']);
function object(value:unknown):value is Record<string,unknown>{return value!==null&&typeof value==='object'&&!Array.isArray(value);}
function clone<T>(value:T):T{return JSON.parse(JSON.stringify(value)) as T;}
export function mergeHistoricalState(previous:ReplaySceneState,current:ReplaySceneState):ReplaySceneState {
 const result:ReplaySceneState=clone(previous);
 for(const [key,value] of Object.entries(current)){
  if(value===undefined)continue;
  // An explicitly recorded null is not replaced with a later value.
  if(object(value)&&object(result[key]))result[key]=mergeHistoricalState(result[key] as ReplaySceneState,value);
  else if(Array.isArray(value)&&Array.isArray(result[key])&&['devices','pipelines'].includes(key)){const old=result[key] as unknown[];result[key]=value.map(item=>{const prior=object(item)?old.find(x=>object(x)&&x.id===item.id):undefined;return object(item)&&object(prior)?mergeHistoricalState(prior,item):clone(item);});}
  else result[key]=clone(value);
 }
 return result;
}
export function interpolateReplayState(left:ReplaySceneState,right:ReplaySceneState,ratio:number):ReplaySceneState {
 if(ratio<=0)return clone(left);if(ratio>=1)return clone(right);
 function visit(a:unknown,b:unknown,key:string):unknown {
  if(typeof a==='number'&&typeof b==='number'&&Number.isFinite(a)&&Number.isFinite(b)&&continuous.has(key))return a+(b-a)*ratio;
  if(object(a)&&object(b)){const result:Record<string,unknown>={};for(const k of Object.keys(a))result[k]=k in b?visit(a[k],b[k],k):clone(a[k]);return result;}
  if(Array.isArray(a)&&Array.isArray(b)&&['devices','pipelines'].includes(key))return a.map(item=>{const next=object(item)?b.find(x=>object(x)&&x.id===item.id):undefined;return next?visit(item,next,''):clone(item);});
  return clone(a);
 }
 return visit(left,right,'') as ReplaySceneState;
}
export function locateReplayIndex(snapshots:ReplaySnapshot[],time:number):number {let low=0,high=snapshots.length-1;while(low<=high){const mid=(low+high)>>>1;if(snapshots[mid]!.simulation_time<=time)low=mid+1;else high=mid-1;}return Math.max(0,high);}
export function replayGapAt(gaps:ReplayGap[],time:number):ReplayGap|undefined{return gaps.find(g=>time>g.from_time&&time<g.to_time);}
export function reviewError(error:unknown):string {if(isAxiosError(error)){const d=error.response?.data?.detail;return typeof d==='string'?d:typeof d?.message==='string'?d.message:'历史数据请求失败，请检查服务状态。';}return error instanceof Error?error.message:'历史数据请求失败。';}
export const useReplayStore=defineStore('replay',()=>{
 const selectedId=ref(''),incident=shallowRef<Incident|null>(null),replay=shallowRef<ReplayData|null>(null),metrics=shallowRef<IncidentMetrics|null>(null),report=shallowRef<ReviewReport|null>(null);
 const snapshots=shallowRef<ReplaySnapshot[]>([]),currentTime=ref(0),playbackSpeed=ref(1),isPlaying=ref(false),loading=ref(false),error=ref(''),warnings=ref<string[]>([]);
 let raf:number|null=null,lastFrame:number|null=null,generation=0,controller:AbortController|null=null;
 const currentIndex=computed(()=>locateReplayIndex(snapshots.value,currentTime.value));
 const startTime=computed(()=>snapshots.value[0]?.simulation_time??0),endTime=computed(()=>snapshots.value.at(-1)?.simulation_time??0);
 const gaps=computed(()=>replay.value?.metadata.gaps??[]),currentGap=computed(()=>replayGapAt(gaps.value,currentTime.value));
 const timelineEvents=computed(()=>replay.value?.timeline??[]),keyMoments=computed(()=>replay.value?.key_moments??[]);
 const currentSnapshot=computed(()=>snapshots.value[currentIndex.value]??null);
 const sceneState=computed<ReplaySceneState>(()=>{
  const left=currentSnapshot.value;if(!left)return {};
  const withBasis=(value:ReplaySceneState):ReplaySceneState=>{const basis=replay.value?.metadata.rendering_basis;return basis?{...value,rendering_basis:clone(basis)}:value;};
  const right=snapshots.value[currentIndex.value+1];
  if(!right||currentGap.value||right.simulation_time<=left.simulation_time)return withBasis(clone(left.scene_state));
  // Do not interpolate across a declared gap even at its boundary.
  if(gaps.value.some(g=>g.from_time<right.simulation_time&&g.to_time>left.simulation_time))return withBasis(clone(left.scene_state));
  return withBasis(interpolateReplayState(left.scene_state,right.scene_state,(currentTime.value-left.simulation_time)/(right.simulation_time-left.simulation_time)));
 });
 const originalTime=computed(()=>{
  const left=currentSnapshot.value;if(!left)return null;const next=snapshots.value[currentIndex.value+1];
  if(!next||currentGap.value)return left.timestamp;
  const span=next.simulation_time-left.simulation_time;if(span<=0)return left.timestamp;
  const ratio=(currentTime.value-left.simulation_time)/span;
  return new Date(Date.parse(left.timestamp)+(Date.parse(next.timestamp)-Date.parse(left.timestamp))*ratio).toISOString();
 });
 const isPaused=computed(()=>!isPlaying.value);
 function pause(){isPlaying.value=false;if(raf!==null)cancelAnimationFrame(raf);raf=null;lastFrame=null;}
 function seek(time:number){if(!Number.isFinite(time))return;currentTime.value=Math.min(endTime.value,Math.max(startTime.value,time));if(currentTime.value>=endTime.value)pause();}
 function step(milliseconds:number){if(!isPlaying.value||!Number.isFinite(milliseconds)||milliseconds<0)return;seek(currentTime.value+milliseconds/1000*playbackSpeed.value);}
 function frame(now:number){raf=null;if(!isPlaying.value)return;if(lastFrame!==null)step(Math.min(now-lastFrame,1000));lastFrame=now;if(isPlaying.value)raf=requestAnimationFrame(frame);}
 function play(){if(isPlaying.value||snapshots.value.length<2)return;if(currentTime.value>=endTime.value)currentTime.value=startTime.value;isPlaying.value=true;lastFrame=null;raf=requestAnimationFrame(frame);}
 function stop(){pause();currentTime.value=startTime.value;}
 function setSpeed(value:number){if([.5,1,2,5].includes(value))playbackSpeed.value=value;}
 function ingest(data:ReplayData){
  pause();replay.value=data;let state:ReplaySceneState={};
  // Only historical observations from this event supply missing dynamic fields.
  snapshots.value=[...data.snapshots].filter(s=>Number.isFinite(s.simulation_time)).sort((a,b)=>a.simulation_time-b.simulation_time||a.timestamp.localeCompare(b.timestamp)).map(s=>{state=mergeHistoricalState(state,s.scene_state??{});return {...s,scene_state:state};});
  currentTime.value=startTime.value;
 }
 function clearData(){pause();incident.value=null;replay.value=null;metrics.value=null;report.value=null;snapshots.value=[];currentTime.value=0;warnings.value=[];error.value='';}
 async function select(id:string){
  const token=++generation;controller?.abort();controller=new AbortController();clearData();selectedId.value=id;loading.value=true;
  const signal=controller.signal;
  const results=await Promise.allSettled([reviewApi.detail(id,signal),reviewApi.replay(id,signal),reviewApi.metrics(id,signal),reviewApi.report(id,signal)] as const);
  if(token!==generation)return;
  const [detail,history,stats,review]=results;
  if(detail.status==='fulfilled')incident.value=detail.value;else error.value=reviewError(detail.reason);
  if(history.status==='fulfilled')ingest(history.value);else error.value=reviewError(history.reason);
  if(stats.status==='fulfilled')metrics.value=stats.value;else warnings.value.push('统计读取失败，当前不显示指标。');
  if(review.status==='fulfilled')report.value=review.value;else if(!isAxiosError(review.reason)||review.reason.response?.status!==404)warnings.value.push('报告读取失败，可稍后重新生成。');
  loading.value=false;
 }
 async function refresh(){const id=selectedId.value;if(!id)return;const time=currentTime.value;await select(id);seek(time);}
 function dispose(){generation++;controller?.abort();controller=null;clearData();selectedId.value='';loading.value=false;}
 return {selectedId,incident,replay,metrics,report,snapshots,currentTime,currentIndex,playbackSpeed,isPlaying,isPaused,loading,error,warnings,startTime,endTime,gaps,currentGap,currentSnapshot,sceneState,originalTime,timelineEvents,keyMoments,play,pause,stop,seek,setSpeed,step,ingest,select,refresh,dispose};
});
