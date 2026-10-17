import type {LeakState} from "./leak";
import type {EmergencyExecution} from "./emergency";
import type {FloodState} from "./flood";
import type { DeviceAnalysis, FaultProfile } from "./operation";
export type WeatherCondition = "clear" | "cloudy" | "rain";
export type DeviceStatus = "offline" | "standby" | "running" | "warning";
export type PipelineKind = "water" | "drain" | "fire";
export interface WeatherState {
  condition: WeatherCondition;
  rainfall: number;
  temperature: number;
  humidity: number;
  windSpeed: number;
}
export interface EnvironmentState {
  b2WaterLevel: number;
  b2WaterArea: number;
  smoke: number;
  airQuality: number;
}
export interface DeviceState {
  startupProgress?: number;
  id: string;
  name: string;
  status: DeviceStatus;
  temperature: number;
  vibration: number;
  current: number;
  rpm: number;
  efficiency: number;
  health: number;
  fault: FaultProfile;
  runtimeHours: number;
  analysis: DeviceAnalysis | null;
}
export interface PipelineState {
  id: string;
  type: PipelineKind;
  pressure: number;
  flow: number;
  status: "normal" | "warning" | "offline" | "isolated";
}
export interface SystemState {
  onlineDevices: number;
  alerts: number;
  eventCount: number;
}
export interface SimulationStatus {
  running: boolean;
  speed: number;
  simulationTime: number;
}
export interface ParkRealtimeState extends SimulationStatus {
  timestamp: string;
  sessionId: string;
  revision: number;
  weather: WeatherState;
  environment: EnvironmentState;
  devices: DeviceState[];
  pipelines: PipelineState[];
  valves?: {id:string;status:"open"|"closed"|"fault";openPercentage:number}[];
  system: SystemState;
  flood?: FloodState;
  emergency?: EmergencyExecution|null;
  leak?: LeakState;
}
export interface RealtimeMessage {
  type: "REALTIME_STATE";
  timestamp: string;
  data: ParkRealtimeState;
}
export type ConnectionStatus = "connecting" | "connected" | "disconnected";
export const weatherLabels: Record<WeatherCondition, string> = {
  clear: "晴天",
  cloudy: "阴天",
  rain: "降雨",
};
export const deviceStatusLabels: Record<DeviceStatus, string> = {
  offline: "离线",
  standby: "待机",
  running: "运行中",
  warning: "预警",
};
export const pipelineLabels: Record<PipelineKind, string> = {
  water: "给水",
  drain: "排水",
  fire: "消防",
};
