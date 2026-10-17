import {defineStore} from 'pinia';
import {ref,shallowRef,computed} from 'vue';
import {pipelineApi} from '../api/pipelines';
import type {PipelineNetwork,Trace,IsolationOption,AffectedBuilding} from '../types/pipeline';
export const usePipelineStore=defineStore('pipeline',()=>{
 const assets=shallowRef<PipelineNetwork>({nodes:[],edges:[],valves:[]});
 const selectedPipeline=ref('WS-003'),selectedValve=ref('');
 const topology=computed(()=>assets.value);
 const trace=shallowRef<Trace|null>(null),isolationOptions=shallowRef<IsolationOption[]>([]);
 const affectedBuildings=shallowRef<AffectedBuilding[]>([]),traceEdges=ref<string[]>([]),affectedTrace=ref(false);
 const error=ref(''),loading=ref(false);let generation=0;
 function select(id:string){if(selectedPipeline.value===id)return;generation++;selectedPipeline.value=id;selectedValve.value='';clear();}
 function clear(){trace.value=null;traceEdges.value=[];isolationOptions.value=[];affectedBuildings.value=[];affectedTrace.value=false;}
 async function load(signal?:AbortSignal){loading.value=true;error.value='';try{assets.value=await pipelineApi.network(signal);}catch {if(!signal?.aborted)error.value='管网资产不可用，请确认数据库迁移与 Seed。';}finally{loading.value=false;}}
 async function analyze(kind:'upstream'|'downstream'|'affected'|'isolation'){
  const token=++generation,id=selectedPipeline.value;error.value='';
  try{
   if(kind==='upstream'||kind==='downstream'){const result=await pipelineApi.trace(id,kind);if(token!==generation)return;trace.value=result;traceEdges.value=result.edges;affectedBuildings.value=result.buildings;affectedTrace.value=false;}
   if(kind==='affected'){const result=await pipelineApi.affected(id);if(token!==generation)return;affectedBuildings.value=result;traceEdges.value=[id];affectedTrace.value=true;}
   if(kind==='isolation'){const result=await pipelineApi.isolation(id);if(token!==generation)return;isolationOptions.value=result;}
  }catch{if(token===generation)error.value='分析请求失败，请检查后端连接。';}
 }
 function preview(option:IsolationOption){traceEdges.value=option.isolatedEdges;affectedBuildings.value=option.affectedBuildings;affectedTrace.value=true;}
 return {assets,selectedPipeline,selectedValve,topology,trace,isolationOptions,affectedBuildings,traceEdges,affectedTrace,error,loading,select,clear,load,analyze,preview};
});
