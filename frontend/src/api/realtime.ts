import type { FaultProfile } from "../types/operation";
import { api } from "./client";
import { isParkRealtimeState } from "../types/realtimeValidation";
import type {
  DeviceStatus,
  ParkRealtimeState,
  SimulationStatus,
  WeatherCondition,
} from "../types/realtime";

export async function getRealtimeState(
  signal?: AbortSignal,
): Promise<ParkRealtimeState> {
  const { data } = await api.get<unknown>("/realtime/state", { signal });
  if (!isParkRealtimeState(data)) throw new Error("实时状态格式无效");
  return data;
}
export async function getSimulationStatus(): Promise<SimulationStatus> {
  return (await api.get<SimulationStatus>("/simulation/status")).data;
}
async function command(
  path: string,
  body?: unknown,
): Promise<ParkRealtimeState> {
  const { data } = await api.post<unknown>(`/simulation/${path}`, body);
  if (!isParkRealtimeState(data)) throw new Error("仿真控制返回格式无效");
  return data;
}
export const simulationApi = {
  start: () => command("start"),
  stop: () => command("stop"),
  reset: () => command("reset"),
  weather: (condition: WeatherCondition) => command("weather", { condition }),
  device: (id: string, status: DeviceStatus) =>
    command(`device/${encodeURIComponent(id)}/state`, { status }),
  fault: (id: string, fault: FaultProfile) =>
    command(`device/${encodeURIComponent(id)}/fault`, { fault }),
  speed: (speed: number) => command("speed", { speed }),
};
