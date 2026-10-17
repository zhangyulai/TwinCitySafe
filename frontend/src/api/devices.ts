import { api } from "./client";
import type {
  DeviceAsset,
  TelemetryHistory,
  SamplingStatus,
} from "../types/operation";
export const deviceApi = {
  list: async (signal?: AbortSignal) =>
    (await api.get<DeviceAsset[]>("/devices", { signal })).data,
  history: async (id: string, range: string, signal?: AbortSignal) =>
    (
      await api.get<TelemetryHistory>(
        `/devices/${encodeURIComponent(id)}/telemetry`,
        { params: { range }, signal },
      )
    ).data,
  sampling: async () =>
    (await api.get<SamplingStatus>("/telemetry/status")).data,
};
