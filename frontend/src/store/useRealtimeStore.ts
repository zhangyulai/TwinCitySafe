import type {LeakPoint} from "../types/leak";
import {useEmergencyStore} from "./useEmergencyStore";
import type {FloodHistoryPoint} from "../types/flood";
import type { TelemetryPoint } from "../types/operation";
import { computed, ref, shallowRef } from "vue";
import { defineStore } from "pinia";
import { RealtimeSocket } from "../services/realtimeSocket";
import type { StateSource } from "../services/realtimeSocket";
import type { ConnectionStatus, ParkRealtimeState } from "../types/realtime";

export interface WaterSample {
  time: number;
  water: number;
}
export const useRealtimeStore = defineStore("realtime", () => {
  const state = shallowRef<ParkRealtimeState | null>(null);
  const connectionStatus = ref<ConnectionStatus>("disconnected");
  const lastError = ref("");
  const lastReceivedAt = ref<number | null>(null);
  const history = shallowRef<WaterSample[]>([]);
  const leakHistory=shallowRef<LeakPoint[]>([]);
  const floodHistory = shallowRef<FloodHistoryPoint[]>([]);
  const deviceHistory = shallowRef<Record<string, TelemetryPoint[]>>({});
  const weather = computed(() => state.value?.weather ?? null);
  const environment = computed(() => state.value?.environment ?? null);
  const devices = computed(() => state.value?.devices ?? []);
  const pipelines = computed(() => state.value?.pipelines ?? []);
  const system = computed(() => state.value?.system ?? null);
  const lastUpdated = computed(() => state.value?.timestamp ?? null);

  function applyRealtimeState(
    next: ParkRealtimeState,
    source: StateSource = "snapshot",
  ): void {
    const previous = state.value;
    if (previous) {
      if (
        previous.sessionId === next.sessionId &&
        next.revision <= previous.revision
      )
        return;
      // Only a live socket can switch a known session; an old REST response cannot roll back a reconnect.
      if (previous.sessionId !== next.sessionId && source !== "stream") return;
    }
    if (
      !previous ||
      next.sessionId !== previous.sessionId ||
      next.simulationTime < previous.simulationTime
    ) {
      history.value = [];
      deviceHistory.value = {};
    }
    if (
      !previous ||
      next.simulationTime !== previous.simulationTime ||
      next.sessionId !== previous.sessionId
    ) {
      const cutoff = Date.parse(next.timestamp) - 5 * 60 * 1000;
      const updated: Record<string, TelemetryPoint[]> = {};
      for (const device of next.devices) {
        updated[device.id] = [
          ...(deviceHistory.value[device.id] ?? [])
            .filter((point) => Date.parse(point.timestamp) >= cutoff)
            .slice(-299),
          {
            timestamp: next.timestamp,
            temperature: device.temperature,
            vibration: device.vibration,
            current: device.current,
            rpm: device.rpm,
            efficiency: device.efficiency,
            healthScore: device.health,
            anomalyScore: device.analysis?.anomalyScore ?? null,
            status: device.status,
          },
        ];
      }
      deviceHistory.value = updated;
      history.value = [
        ...history.value.slice(-59),
        { time: next.simulationTime, water: next.environment.b2WaterLevel },
      ];
    } else {
      // Paused heartbeats do not add fake samples, but still expire the 5-minute window.
      const cutoff = Date.parse(next.timestamp) - 5 * 60 * 1000;
      const recent: Record<string, TelemetryPoint[]> = {};
      let changed = false;
      for (const [id, points] of Object.entries(deviceHistory.value)) {
        recent[id] = points.filter(point => Date.parse(point.timestamp) >= cutoff);
        changed ||= recent[id].length !== points.length;
      }
      if (changed) deviceHistory.value = recent;
    }
    const flood=next.flood;
    if(!flood?.scenarioId || flood.scenarioId!==previous?.flood?.scenarioId || next.sessionId!==previous?.sessionId)floodHistory.value=[];
    if(flood?.scenarioId && (flood.elapsedSimulationSeconds!==previous?.flood?.elapsedSimulationSeconds || flood.scenarioId!==previous?.flood?.scenarioId)){
      floodHistory.value=[...floodHistory.value.filter(p=>p.time>=flood.elapsedSimulationSeconds-3600).slice(-1799),{time:flood.elapsedSimulationSeconds,rainfall:flood.rainfall,waterLevel:flood.waterLevel,pumpCapacity:flood.effectivePumpCapacity,riskScore:flood.riskScore}];
    }
    const leak=next.leak;
    if(!leak?.scenarioId||leak.scenarioId!==previous?.leak?.scenarioId||next.sessionId!==previous?.sessionId)leakHistory.value=[];
    if(leak?.scenarioId&&(leak.elapsedSimulationSeconds!==previous?.leak?.elapsedSimulationSeconds||leak.scenarioId!==previous?.leak?.scenarioId))leakHistory.value=[...leakHistory.value.filter(p=>p.time>=leak.elapsedSimulationSeconds-3600).slice(-1799),{time:leak.elapsedSimulationSeconds,pressure:leak.downstreamPressure,flow:leak.pipelineFlow,detection:leak.detectionScore,risk:leak.riskScore}];
    state.value = next;
    const emergency=useEmergencyStore();
    if(emergency.scenarioId!==(next.flood?.scenarioId??null)||previous?.sessionId!==next.sessionId)emergency.reset(next.flood?.scenarioId??null);
    emergency.sync(next.emergency??null);
  }
  const socket = new RealtimeSocket({
    emergency:event=>useEmergencyStore().onEvent(event),
    state: (value, source) => {
      lastReceivedAt.value = Date.now();
      applyRealtimeState(value, source);
    },
    status: (value) => {
      connectionStatus.value = value;
    },
    error: (value) => {
      lastError.value = value;
    },
  });
  const connect = () => socket.connect();
  const disconnect = () => socket.disconnect();
  const getDeviceById = (id: string) =>
    devices.value.find((device) => device.id === id);
  function reset(): void {
    // Local cache reset is explicit; disconnection alone intentionally preserves the last snapshot.
    socket.disconnect();
    state.value = null;
    leakHistory.value=[];
    floodHistory.value = [];
    history.value = [];
    deviceHistory.value = {};
    lastReceivedAt.value = null;
    lastError.value = "";
  }
  return {
    state,
    connectionStatus,
    lastError,
    lastReceivedAt,
    weather,
    environment,
    devices,
    pipelines,
    system,
    lastUpdated,
    history,
    deviceHistory,
    floodHistory,
    leakHistory,
    applyRealtimeState,
    getDeviceById,
    connect,
    disconnect,
    reset,
  };
});
