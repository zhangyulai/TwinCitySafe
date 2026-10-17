import { api } from "./client";
export interface HealthResponse {
  status: "ok";
  service: "TwinCitySafe";
  version: "2.0";
}
export async function getHealth(): Promise<HealthResponse> {
  const { data } = await api.get<HealthResponse>("/health");
  if (
    data.status !== "ok" ||
    data.service !== "TwinCitySafe" ||
    data.version !== "2.0"
  ) {
    throw new Error("Unexpected health response");
  }
  return data;
}
