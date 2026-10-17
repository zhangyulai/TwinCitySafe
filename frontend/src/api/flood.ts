import {api} from './client';
import type {FloodForecast,FloodScenario} from '../types/flood';import type {ParkRealtimeState} from '../types/realtime';
export const floodApi={
 command:async(command:'demo-start'|'stop'|'reset'|'emergency-demo-start')=>(await api.post<ParkRealtimeState>('/simulation/flood/'+command)).data,
 start:async(scenario:FloodScenario,peopleCount:number,vehicleCount:number)=>(await api.post<ParkRealtimeState>('/simulation/flood/start',{scenario,durationMinutes:30,peopleCount,vehicleCount})).data,
 exposure:async(peopleCount:number,vehicleCount:number)=>(await api.post<ParkRealtimeState>('/simulation/flood/exposure',{peopleCount,vehicleCount})).data,
 forecast:async(signal?:AbortSignal)=>(await api.get<FloodForecast>('/simulation/flood/forecast',{signal})).data,
 storage:async()=>(await api.get<{available:boolean;intervalSeconds:number;lastSampleAt:string|null;message:string}>('/simulation/flood/storage')).data,
};
