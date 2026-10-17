import {ref,shallowRef,onMounted,onBeforeUnmount,watch,type ComputedRef} from 'vue';
import {riskApi} from '../api/risk';import {useRealtimeStore} from '../store/useRealtimeStore';import type {RiskPrediction,RiskModelStatus,PredictionExplanation,PredictionEvaluation} from '../types/risk';
export function useRiskPrediction(enabled:ComputedRef<boolean>,details=false){
 const realtime=useRealtimeStore(),prediction=shallowRef<RiskPrediction|null>(null),model=shallowRef<RiskModelStatus|null>(null),explanation=shallowRef<PredictionExplanation|null>(null),evaluation=shallowRef<PredictionEvaluation|null>(null),error=ref('');
 let alive=true,timer:ReturnType<typeof setInterval>|undefined,request:AbortController|undefined,token=0,lastDetails=0;
 async function refresh(){if(!alive||!enabled.value||realtime.connectionStatus!=='connected')return;const generation=++token;request?.abort();const controller=new AbortController();request=controller;
  const scenarioId=realtime.state?.flood?.scenarioId??null,session=realtime.state?.sessionId;
  try{const result=await riskApi.prediction(controller.signal);if(!alive||generation!==token||result.scenarioId!==(realtime.state?.flood?.scenarioId??null)||result.sessionId!==realtime.state?.sessionId)return;
   prediction.value=result;error.value='';
   if(details&&Date.now()-lastDetails>=9500){lastDetails=Date.now();const [m,e,v]=await Promise.all([riskApi.status(controller.signal),riskApi.explanation(controller.signal),riskApi.evaluation(controller.signal)]);
    if(alive&&generation===token&&scenarioId===(realtime.state?.flood?.scenarioId??null)&&session===realtime.state?.sessionId){model.value=m;explanation.value=e;evaluation.value=v;}}
  }catch{if(alive&&generation===token&&!controller.signal.aborted)error.value='预测更新暂不可用，保留上次结果。';}
 }
 watch(()=>[realtime.state?.sessionId,realtime.state?.flood?.scenarioId],()=>{prediction.value=null;explanation.value=null;evaluation.value=null;lastDetails=0;void refresh();});
 watch(()=>realtime.connectionStatus,status=>{if(status==='connected')void refresh();});watch(enabled,value=>{if(value)void refresh();else{request?.abort();prediction.value=null;}});
 onMounted(()=>{void refresh();timer=setInterval(()=>void refresh(),5000);});onBeforeUnmount(()=>{alive=false;token++;request?.abort();clearInterval(timer);});
 return {prediction,model,explanation,evaluation,error,refresh};
}
