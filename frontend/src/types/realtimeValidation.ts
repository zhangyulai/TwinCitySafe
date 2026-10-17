import {validFlood} from "./flood";
import type { ParkRealtimeState, RealtimeMessage } from "./realtime";

const record = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);
const numbers = (value: Record<string, unknown>, keys: string[]) =>
  keys.every(
    (key) => typeof value[key] === "number" && Number.isFinite(value[key]),
  );
const member = (value: unknown, allowed: string[]) =>
  typeof value === "string" && allowed.includes(value);
const dated = (value: unknown) =>
  typeof value === "string" && Number.isFinite(Date.parse(value));

/** Validate network payloads at the boundary, before UI/Three.js consume them. */
export function isParkRealtimeState(
  value: unknown,
): value is ParkRealtimeState {
  if (
    !record(value) ||
    !dated(value.timestamp) ||
    typeof value.sessionId !== "string" ||
    !value.sessionId ||
    !numbers(value, ["simulationTime", "speed", "revision"]) ||
    !Number.isSafeInteger(value.revision) ||
    Number(value.revision) < 0 ||
    Number(value.simulationTime) < 0 ||
    Number(value.speed) <= 0 ||
    typeof value.running !== "boolean"
  )
    return false;
  const { weather, environment, devices, pipelines, system } = value;
  if (
    !record(weather) ||
    !member(weather.condition, ["clear", "cloudy", "rain"]) ||
    !numbers(weather, ["rainfall", "temperature", "humidity", "windSpeed"])
  )
    return false;
  if (
    !record(environment) ||
    !numbers(environment, [
      "b2WaterLevel",
      "b2WaterArea",
      "smoke",
      "airQuality",
    ])
  )
    return false;
  if (
    !record(system) ||
    !numbers(system, ["onlineDevices", "alerts", "eventCount"])
  )
    return false;
  if (
    !Array.isArray(devices) ||
    !devices.every(
      (device: unknown) =>
        record(device) &&
        typeof device.id === "string" &&
        typeof device.name === "string" &&
        member(device.fault, [
          "normal",
          "bearing_degradation",
          "overheat",
          "low_efficiency",
        ]) &&
        numbers(device, ["runtimeHours"]) &&
        (device.analysis === null || validAnalysis(device.analysis)) &&
        member(device.status, ["offline", "standby", "running", "warning"]) &&
        numbers(device, [
          "temperature",
          "vibration",
          "current",
          "rpm",
          "efficiency",
          "health",
        ]),
    )
  )
    return false;
  if (
    !Array.isArray(pipelines) ||
    !pipelines.every(
      (pipeline: unknown) =>
        record(pipeline) &&
        typeof pipeline.id === "string" &&
        member(pipeline.type, ["water", "drain", "fire"]) &&
        member(pipeline.status, ["normal","warning","offline","isolated"]) &&
        numbers(pipeline, ["pressure", "flow"]),
    )
  )
    return false;
  if (value.valves !== undefined && (!Array.isArray(value.valves) || !value.valves.every(v => record(v) && typeof v.id === "string" && member(v.status,["open","closed","fault"]) && numbers(v,["openPercentage"])))) return false;
  if(value.leak!==undefined){const l=value.leak;if(!record(l)||!(l.scenarioId===null||typeof l.scenarioId==='string')||!numbers(l,['elapsedSimulationSeconds','detectionScore','riskScore','estimatedLeakFlow','downstreamPressure','pipelineFlow'])||!Array.isArray(l.suspectedSegments)||!Array.isArray(l.events)||!Array.isArray(l.affectedBuildings)||!Array.isArray(l.riskBreakdown))return false;}
  if(value.flood!==undefined&&!validFlood(value.flood))return false;
  if(value.emergency!==undefined&&value.emergency!==null){
    const e=value.emergency;
    if(!record(e)||typeof e.id!=='string'||typeof e.scenario_id!=='string'||typeof e.plan_code!=='string'||typeof e.phase!=='string'||typeof e.status!=='string'||!Array.isArray(e.steps)||!Array.isArray(e.events))return false;
    if(!e.steps.every(s=>record(s)&&typeof s.message==='string'&&typeof s.status==='string'&&Number.isInteger(s.index)))return false;
    if(!e.events.every(v=>record(v)&&typeof v.message==='string'&&dated(v.timestamp)&&Number.isInteger(v.sequence)))return false;
  }
  if(!devices.every(d=>d.startupProgress===undefined||(typeof d.startupProgress==='number'&&Number.isFinite(d.startupProgress)&&d.startupProgress>=0&&d.startupProgress<=1)))return false;
  return true;
}
export function isRealtimeMessage(value: unknown): value is RealtimeMessage {
  return (
    record(value) &&
    value.type === "REALTIME_STATE" &&
    dated(value.timestamp) &&
    isParkRealtimeState(value.data)
  );
}

function validAnalysis(value: unknown): boolean {
  if (
    !record(value) ||
    !numbers(value, ["healthScore", "healthTarget"]) ||
    typeof value.healthGrade !== "string" ||
    typeof value.modelAvailable !== "boolean" ||
    typeof value.evaluated !== "boolean" ||
    typeof value.isAnomaly !== "boolean" ||
    !member(value.level, [
      "normal",
      "attention",
      "warning",
      "critical",
      "unavailable",
      "not_applicable",
      "warming_up",
    ]) ||
    typeof value.explanation !== "string" ||
    !record(value.advice) ||
    !member(value.advice.priority, ["P0", "P1", "P2", "P3"]) ||
    typeof value.advice.title !== "string" ||
    typeof value.advice.message !== "string"
  )
    return false;
  return (
    ["anomalyScore", "rawScore"].every(
      (key) =>
        value[key] === null ||
        (typeof value[key] === "number" && Number.isFinite(value[key])),
    ) &&
    (value.activeAlarmId === null || typeof value.activeAlarmId === "string") &&
    (value.modelVersion === null || typeof value.modelVersion === "string") &&
    Array.isArray(value.contributions) &&
    value.contributions.every(
      (item: unknown) =>
        record(item) &&
        typeof item.feature === "string" &&
        typeof item.label === "string" &&
        numbers(item, ["deviation", "contribution"]),
    )
  );
}
