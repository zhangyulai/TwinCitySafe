import { api } from './client';
import type { ParkRealtimeState } from '../types/realtime';
export interface ReadinessCheck { available: boolean; status: string; message: string; [key: string]: unknown }
export interface Readiness { ready: boolean; degraded: boolean; demo_enabled: boolean; checked_at: string; backend: ReadinessCheck; database: ReadinessCheck; websocket: ReadinessCheck; anomaly_model: ReadinessCheck; risk_model: ReadinessCheck; pipeline_graph: ReadinessCheck }
export const demoApi = {
  readiness: async () => (await api.get<Readiness>('/system/readiness')).data,
  control: async (action: string, body: Record<string, unknown> = {}) => (await api.post<ParkRealtimeState>(`/demo/${action}`, body, { timeout: 20000 })).data,
};
export function actionError(error: unknown): string {
  const e = error as { response?: { data?: { detail?: unknown } }; message?: string };
  const detail = e.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (detail && typeof detail === 'object' && 'message' in detail) return String(detail.message);
  return e.message === 'Network Error' ? '服务连接中断，请检查后端后重试。' : '操作未完成，请检查系统状态后重试。';
}
