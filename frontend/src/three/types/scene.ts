import type { Group } from "three";

/** `above` and `underground` remain stable internal names for the public
 * “地上” and “管网” controls. Emergency is an explicit presentation overlay. */
export type SceneMode = "above" | "underground" | "risk" | "emergency";
export type RiskLevel = "low" | "general" | "elevated" | "high";
/** Stable asset contract attached to every pickable building mesh. */
export interface BuildingAssetData {
  id: string;
  name: string;
  type: string;
  floors: number;
  status: string;
  riskLevel: string;
  position: [number, number, number];
}
export interface BuildingMetadata {
  id: string;
  name: string;
  type: "office" | "research" | "laboratory" | "service" | "parking";
  typeLabel: string;
  area: number;
  floors: number;
  deviceCount: number;
  alarms: number;
  safetyIndex: number;
  risk: RiskLevel;
  level: number;
  status: string;
}
export interface BuildingSelection extends BuildingMetadata {
  buildingId: string;
  buildingName: string;
  buildingType: BuildingMetadata["type"];
}
export interface BuildingEntry {
  object: Group;
  metadata: BuildingMetadata;
}
export interface SceneStats {
  fps: number;
  drawCalls: number;
  triangles: number;
}
export const riskColors: Record<RiskLevel, number> = {
  low: 0x419b89,
  general: 0xb8a75e,
  elevated: 0xc67c43,
  high: 0xc65a64,
};
export const riskLabels: Record<RiskLevel, string> = {
  low: "低风险",
  general: "一般风险",
  elevated: "较高风险",
  high: "高风险",
};
