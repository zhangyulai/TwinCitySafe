export type FloodScenario='normal'|'heavy_rain'|'extreme_rain';
export type FloodStage='normal'|'watch'|'warning'|'high'|'extreme';
export type FloodRiskLevel='low'|'general'|'elevated'|'high'|'extreme';
export interface FloodRiskFactor {key:string;label:string;weight:number;normalizedValue:number;points:number;contribution:number}
export interface FloodRiskFactors {factors:FloodRiskFactor[];method:string}
export interface FloodAlarm {id:string;alarmType:string;level:'info'|'warning'|'major'|'critical';stage:FloodStage;peakRisk:number;status:'active'|'ended_by_reset';message:string}
export interface FloodState {
 rainfallRecession?:boolean;entranceClosed?:boolean;vehicleEntryRate?:number;
 scenarioId:string|null;running:boolean;scenario:FloodScenario;status:'idle'|'running'|'stopped'|'completed';startedAt:string|null;simulationStartedAt:number;
 elapsedSimulationSeconds:number;durationMinutes:number;autoFault:boolean;faultTriggered:boolean;
 rainfall:number;rainfallTarget:number;surfaceInflow:number;naturalDrainage:number;pumpCapacity:number;pumpEfficiency:number;effectivePumpCapacity:number;outflow:number;
 waterLevel:number;waterArea:number;floodVolume:number;effectiveArea:number;growthRate:number;riskScore:number;riskLevel:FloodRiskLevel;stage:FloodStage;riskBreakdown:FloodRiskFactors;
 peopleCount:number;vehicleCount:number;peakWaterLevel:number;peakRisk:number;alarm:FloodAlarm|null;requiresEmergency:boolean;
}
export interface FloodForecastPoint {minute:number;waterLevel:number;waterArea:number;riskScore:number;riskLevel:FloodRiskLevel}
export interface FloodForecast {scenarioId:string|null;basedOnRevision:number;simulationTime:number;current:FloodForecastPoint;points:FloodForecastPoint[];assumption:string}
export interface FloodHistoryPoint {time:number;rainfall:number;waterLevel:number;pumpCapacity:number;riskScore:number}
export const floodLevelLabels:Record<FloodRiskLevel,string>={low:'低风险',general:'一般风险',elevated:'较高风险',high:'高风险',extreme:'极高风险'};
export const floodStageLabels:Record<FloodStage,string>={normal:'正常',watch:'关注',warning:'预警',high:'高风险',extreme:'极高风险'};
export const floodScenarioLabels:Record<FloodScenario,string>={normal:'正常降雨',heavy_rain:'强降雨',extreme_rain:'极端暴雨'};
export function validFlood(value:unknown):value is FloodState {
 if(typeof value!=='object'||value===null||Array.isArray(value))return false;
 const v=value as Record<string,unknown>;
 const numeric=['simulationStartedAt','elapsedSimulationSeconds','durationMinutes','rainfall','rainfallTarget','surfaceInflow','naturalDrainage','pumpCapacity','pumpEfficiency','effectivePumpCapacity','outflow','waterLevel','waterArea','floodVolume','effectiveArea','growthRate','riskScore','peopleCount','vehicleCount','peakWaterLevel','peakRisk'];
 if(!numeric.every(k=>typeof v[k]==='number'&&Number.isFinite(v[k])))return false;
 if(!['running','autoFault','faultTriggered','requiresEmergency'].every(k=>typeof v[k]==='boolean'))return false;
 if(v.scenarioId!==null&&typeof v.scenarioId!=='string')return false;
 if(!['normal','heavy_rain','extreme_rain'].includes(String(v.scenario))||!['idle','running','stopped','completed'].includes(String(v.status))||!['normal','watch','warning','high','extreme'].includes(String(v.stage))||!['low','general','elevated','high','extreme'].includes(String(v.riskLevel)))return false;
 const b=v.riskBreakdown as FloodRiskFactors|undefined;
 return !!b&&typeof b.method==='string'&&Array.isArray(b.factors)&&b.factors.every(f=>typeof f.key==='string'&&typeof f.label==='string'&&[f.weight,f.normalizedValue,f.points,f.contribution].every(Number.isFinite))&&(v.alarm===null||(typeof v.alarm==='object'&&typeof (v.alarm as FloodAlarm).id==='string'&&typeof (v.alarm as FloodAlarm).message==='string'));
}
