import {api} from './client';
import type {Incident,IncidentMetrics,ReplayData,ReviewReport,WorkOrder,WorkOrderStatus} from '../types/review';
export interface IncidentFilters {type?:string;status?:string;start_time?:string;end_time?:string;keyword?:string;limit?:number;offset?:number}
export const reviewApi={
 list:async(params:IncidentFilters={},signal?:AbortSignal)=>(await api.get<{items:Incident[];total:number}>('/incidents',{params,signal})).data,
 detail:async(id:string,signal?:AbortSignal)=>(await api.get<Incident>(`/incidents/${id}`,{signal})).data,
 replay:async(id:string,signal?:AbortSignal)=>(await api.get<ReplayData>(`/incidents/${id}/replay`,{params:{step_seconds:5},signal,timeout:15000})).data,
 metrics:async(id:string,signal?:AbortSignal)=>(await api.get<IncidentMetrics>(`/incidents/${id}/metrics`,{signal})).data,
 report:async(id:string,signal?:AbortSignal)=>(await api.get<{report:ReviewReport|null}>(`/incidents/${id}/review`,{signal})).data.report,
 generate:async(id:string)=>(await api.post<ReviewReport>(`/incidents/${id}/review/generate`)).data,
 close:async(id:string,result:string)=>(await api.post<Incident>(`/incidents/${id}/close`,{result,operator:'demo-user',confirmed:true})).data,
 createWorkOrder:async(incident_id:string,title:string,assignee:string)=>(await api.post<WorkOrder>('/work-orders',{incident_id,title,assignee,category:'EMERGENCY',priority:'HIGH',description:'软件仿真事故处置与复核',created_by:'demo-user'})).data,
 patchWorkOrder:async(id:string,status:WorkOrderStatus,assignee?:string,result?:string)=>(await api.patch<WorkOrder>(`/work-orders/${id}`,{status,...(assignee?{assignee}:{}),...(result?{result}:{})})).data,
};
