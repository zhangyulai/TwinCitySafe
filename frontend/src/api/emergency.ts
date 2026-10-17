import {api} from './client';
import type {EmergencyPlan,EmergencyComparison,EmergencyExecution} from '../types/emergency';
export const emergencyApi={
 plans:async()=>(await api.get<EmergencyPlan[]>('/emergency/plans?scenario_type=flood')).data,
 compare:async(plan_codes:string[])=>(await api.post<EmergencyComparison>('/emergency/compare',{plan_codes,horizon_minutes:30})).data,
 preview:async(plan_code:string)=>(await api.post<EmergencyComparison>('/emergency/preview',{plan_code,horizon_minutes:30})).data,
 execute:async(plan_code:string,comparison_id:string)=>(await api.post<EmergencyExecution>('/emergency/execute',{plan_code,comparison_id,confirmed_simulation:true})).data,
 cancel:async(id:string)=>(await api.post<EmergencyExecution>(`/emergency/executions/${id}/cancel`)).data,
};
