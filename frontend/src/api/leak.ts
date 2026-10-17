import {api} from './client';import type {ParkRealtimeState} from '../types/realtime';import type {LeakComparison} from '../types/leak';
export const leakApi={
 start:async()=>(await api.post<ParkRealtimeState>('/simulation/pipeline-leak/start',{})).data,
 command:async(action:'stop'|'reset')=>(await api.post<ParkRealtimeState>('/simulation/pipeline-leak/'+action)).data,
 compare:async(pipelineId:string)=>(await api.post<LeakComparison>('/pipeline-leak/isolation/compare',{pipelineId})).data,
 execute:async(comparisonId:string,optionId:string)=>(await api.post<ParkRealtimeState>('/pipeline-leak/isolation/execute',{comparisonId,optionId,confirmedSimulation:true})).data,
};
