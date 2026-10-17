export type PipelineType = 'water' | 'drainage' | 'fire';
export type PipelineStatus = 'normal' | 'warning' | 'offline' | 'isolated';
export interface PipelineNode { id:string; nodeType:string; name:string; x:number;y:number;z:number;buildingId:string|null; metadata:{pipelineType:PipelineType;criticality:string} }
export interface PipelineAsset { id:string;pipelineCode:string;pipelineType:PipelineType;startNodeId:string;endNodeId:string;diameter:number;length:number;depth:number;material:string;installDate:string;designPressure:number;healthScore:number;status:PipelineStatus }
export interface ValveAsset { id:string;nodeId:string;valveType:string;status:'open'|'closed'|'fault';openPercentage:number;lastMaintenance:string }
export interface PipelineNetwork { nodes:PipelineNode[];edges:PipelineAsset[];valves:ValveAsset[] }
export interface AffectedBuilding {buildingId:string;buildingName:string;connectionNode:string;criticality:string}
export interface Trace {nodes:string[];edges:string[];valves:string[];sources:string[];buildings:AffectedBuilding[]}
export interface IsolationOption {id:string;valves:string[];isolatedEdges:string[];affectedBuildings:AffectedBuilding[];affectedNodes:string[];estimatedScope:{buildingCount:number;edgeCount:number;length:number}}
export const typeLabels:Record<PipelineType,string>={water:'给水',drainage:'排水',fire:'消防'};
export const statusLabels:Record<PipelineStatus,string>={normal:'正常',warning:'预警',offline:'离线',isolated:'隔离'};
export const pipeColors:Record<PipelineType,string>={water:'#29a8ff',drainage:'#29d3a2',fire:'#ff5a67'};
