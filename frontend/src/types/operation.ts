export type FaultProfile =
  | "normal"
  | "bearing_degradation"
  | "overheat"
  | "low_efficiency";
export type AnomalyLevel =
  | "normal"
  | "attention"
  | "warning"
  | "critical"
  | "unavailable"
  | "not_applicable"
  | "warming_up";
export interface Contribution {
  feature: string;
  label: string;
  deviation: number;
  contribution: number;
}
export interface MaintenanceAdvice {
  priority: "P0" | "P1" | "P2" | "P3";
  title: string;
  message: string;
}
export interface DeviceAnalysis {
  healthScore: number;
  healthTarget: number;
  healthGrade: string;
  modelAvailable: boolean;
  modelVersion: string | null;
  evaluated: boolean;
  anomalyScore: number | null;
  rawScore: number | null;
  isAnomaly: boolean;
  level: AnomalyLevel;
  contributions: Contribution[];
  explanation: string;
  advice: MaintenanceAdvice;
  activeAlarmId: string | null;
}
export interface DeviceAsset {
  id: string;
  deviceCode: string;
  deviceName: string;
  deviceType: string;
  buildingId: string;
  areaId: string;
  positionX: number;
  positionY: number;
  positionZ: number;
  status: string;
  healthScore: number;
  installDate: string;
  runtimeHours: number;
  lastMaintenance: string;
  ratedPower: number;
  ratedRpm: number;
  ratedCurrent: number;
  ratedCapacity: number;
  createdAt: string;
  updatedAt: string;
}
export interface TelemetryPoint {
  timestamp: string;
  temperature: number;
  vibration: number;
  current: number;
  rpm: number;
  efficiency: number;
  healthScore: number;
  anomalyScore: number | null;
  status: string;
}
export interface TelemetryHistory {
  deviceId: string;
  source: string;
  startTime: string;
  endTime: string;
  sampleIntervalSeconds: number;
  points: TelemetryPoint[];
  total: number;
  downsampled: boolean;
}
export interface SamplingStatus {
  available: boolean;
  intervalSeconds: number;
  lastSampleAt: string | null;
  message: string;
}
export const anomalyLabels: Record<AnomalyLevel, string> = {
  normal: "正常",
  attention: "关注",
  warning: "预警",
  critical: "严重",
  unavailable: "异常模型未加载",
  not_applicable: "非运行工况",
  warming_up: "启动过渡中",
};
export const faultLabels: Record<FaultProfile, string> = {
  normal: "正常工况",
  bearing_degradation: "轴承退化",
  overheat: "过热",
  low_efficiency: "低效率",
};
