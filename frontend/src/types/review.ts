export type IncidentType = 'FLOOD' | 'PIPELINE_LEAK';
export type IncidentStatus = 'OPEN' | 'DETECTED' | 'CONFIRMED' | 'RESPONDING' | 'STABILIZING' | 'CLOSED' | 'ABORTED';
export interface Incident {
 id:string;incident_code:string;incident_type:IncidentType;source_event_id:string;title:string;area_id:string|null;status:IncidentStatus;
 started_at:string|null;detected_at:string|null;confirmed_at:string|null;response_started_at:string|null;stabilized_at:string|null;closed_at:string|null;
 peak_risk:number|null;peak_water_level:number|null;peak_detection_score:number|null;created_at?:string;updated_at?:string;
 comparisons?:Record<string,unknown>[];executions?:Record<string,unknown>[];work_orders?:WorkOrder[];
}
export interface TimelineEvent {id:string;incident_id:string;event_time:string;simulation_time:number|null;event_type:string;event_level:string;title:string;description:string;source:string;source_id:string;payload:Record<string,unknown>}
export type ReplaySceneState=Record<string,unknown>;
export interface ReplaySnapshot {id:string;timestamp:string;simulation_time:number;risk_score:number|null;risk_level:string|null;scene_state:ReplaySceneState;source_snapshot_id:string|null;missing_fields:string[]}
export interface ReplayGap {from_time:number;to_time:number;duration_seconds?:number;reason?:string}
export interface KeyMoment {id?:string;title:string;simulation_time:number|null;event_time?:string;event_type?:string;type?:string;focus_target_id?:string|null}
export interface ReplayData {metadata:{incident_id:string;incident_type:IncidentType;from_time:number|null;to_time:number|null;step_seconds:number;gaps:ReplayGap[];missing_fields:string[];latency_ms:number;[key:string]:unknown};timeline:TimelineEvent[];snapshots:ReplaySnapshot[];key_moments:KeyMoment[]}
export interface IncidentMetrics {
 incident_id:string;incident_type:IncidentType;snapshot_count:number;
 response_metrics:Record<string,number|null>;peak_metrics:Record<string,number|null>;
 response_effect:{before:Record<string,unknown>|null;after:Record<string,unknown>|null;environment_note:string};
 prediction_review:{label:string;samples:number;water_mae:number|null;risk_mae:number|null;physical_water_mae:number|null;physical_risk_mae:number|null;items:Record<string,unknown>[];message:string};
 missing_fields:string[];
}
export interface ReviewReport {id:string;incident_id:string;generated_at:string;summary:string;cause_analysis:string;response_analysis:string;prediction_analysis:string;impact_analysis:string;lessons:string[];status:string;metrics:IncidentMetrics}
export type WorkOrderStatus='PENDING'|'ASSIGNED'|'IN_PROGRESS'|'COMPLETED'|'CANCELLED';
export interface WorkOrder {id:string;work_order_code:string;incident_id:string;title:string;description:string;category:string;priority:string;status:WorkOrderStatus;assignee:string|null;created_at:string;accepted_at:string|null;completed_at:string|null;result:string|null;created_by:string}
export const incidentTypeLabels:Record<IncidentType,string>={FLOOD:'暴雨内涝',PIPELINE_LEAK:'管网泄漏'};
export const incidentStatusLabels:Record<IncidentStatus,string>={OPEN:'已启动',DETECTED:'已检测',CONFIRMED:'已确认',RESPONDING:'处置中',STABILIZING:'稳定中',CLOSED:'已关闭',ABORTED:'已中断'};
export const workOrderStatusLabels:Record<WorkOrderStatus,string>={PENDING:'待接单',ASSIGNED:'已接单',IN_PROGRESS:'处理中',COMPLETED:'已完成',CANCELLED:'已取消'};
