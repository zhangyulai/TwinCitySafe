import { api } from './client';
import type { PipelineNetwork, Trace, AffectedBuilding, IsolationOption } from '../types/pipeline';
import type { ParkRealtimeState } from '../types/realtime';
export const pipelineApi={
 network:async(signal?:AbortSignal)=>(await api.get<PipelineNetwork>('/pipelines/network',{signal})).data,
 trace:async(id:string,direction:string)=>(await api.get<Trace>(`/pipelines/${id}/${direction}`)).data,
 affected:async(id:string)=>(await api.get<AffectedBuilding[]>(`/pipelines/${id}/affected-buildings`)).data,
 valves:async(id:string)=>(await api.get<{upstream:string[];downstream:string[]}>(`/pipelines/${id}/valves`)).data,
 isolation:async(id:string)=>(await api.post<{options:IsolationOption[]}>(`/pipelines/${id}/isolation-options`)).data.options,
 control:async(id:string,status:'open'|'closed')=>(await api.post<{state:ParkRealtimeState;affectedBuildings:AffectedBuilding[]}>(`/simulation/valve/${id}/state`,{status})).data,
};
