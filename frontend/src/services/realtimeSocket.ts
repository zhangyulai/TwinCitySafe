import {isEmergencyMessage,type EmergencyEvent} from "../types/emergency";
import { getRealtimeState } from "../api/realtime";
import { isRealtimeMessage } from "../types/realtimeValidation";
import type { ConnectionStatus, ParkRealtimeState } from "../types/realtime";

export type StateSource = "stream" | "snapshot";
interface RealtimeCallbacks {
  emergency?: (event:EmergencyEvent)=>void;
  state: (state: ParkRealtimeState, source: StateSource) => void;
  status: (status: ConnectionStatus) => void;
  error: (message: string) => void;
}
const retryDelays = [1000, 2000, 5000];

function socketUrl(): string {
  if (import.meta.env.VITE_WS_URL) return import.meta.env.VITE_WS_URL;
  const url = new URL("/ws/realtime", window.location.href);
  url.protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return url.href;
}

/** Owned by the single app-level Pinia store, never created per Dashboard entry. */
export class RealtimeSocket {
  private socket: WebSocket | null = null;
  private reconnectTimer: ReturnType<typeof setTimeout> | undefined;
  private heartbeatTimer: ReturnType<typeof setTimeout> | undefined;
  private request: AbortController | undefined;
  private active = false;
  private attempt = 0;
  private generation = 0;

  constructor(private readonly callbacks: RealtimeCallbacks) {}
  connect(): void {
    if (this.active) return;
    this.active = true;
    this.attempt = 0;
    this.callbacks.status("connecting");
    this.open();
  }
  private open(): void {
    if (!this.active) return;
    const generation = ++this.generation;
    this.request?.abort();
    this.request = new AbortController();
    let receivedStream = false;
    const current = () => this.active && generation === this.generation;
    // REST recovers an initial snapshot even while the socket handshake is in progress.
    void getRealtimeState(this.request.signal)
      .then((state) => {
        if (current() && !receivedStream)
          this.callbacks.state(state, "snapshot");
      })
      .catch(() => {
        if (current() && !receivedStream)
          this.callbacks.error("暂时无法获取实时状态，正在重试连接。");
      });
    let socket: WebSocket;
    try {
      socket = new WebSocket(socketUrl());
    } catch {
      this.failed(generation);
      return;
    }
    this.socket = socket;
    const armHeartbeat = () => {
      clearTimeout(this.heartbeatTimer);
      this.heartbeatTimer = setTimeout(() => {
        if (!current()) return;
        this.callbacks.status("disconnected");
        this.failed(generation);
      }, 6000);
    };
    socket.onopen = () => {
      if (current()) armHeartbeat();
    };
    socket.onmessage = (event: MessageEvent<unknown>) => {
      if (!current() || typeof event.data !== "string") return;
      let parsed: unknown;
      try {
        parsed = JSON.parse(event.data);
      } catch {
        this.callbacks.error("忽略无法解析的实时消息。");
        return;
      }
      if(parsed&&typeof parsed==='object'&&(parsed as {type?:string}).type==='PIPELINE_LEAK_EVENT'){armHeartbeat();return;}
      if(isEmergencyMessage(parsed)){this.callbacks.emergency?.(parsed.data);armHeartbeat();return;}
      if (!isRealtimeMessage(parsed)) {
        this.callbacks.error("忽略格式不符合约定的实时消息。");
        return;
      }
      receivedStream = true;
      this.attempt = 0;
      this.callbacks.state(parsed.data, "stream");
      this.callbacks.status("connected");
      this.callbacks.error("");
      armHeartbeat();
    };
    socket.onerror = () => {
      if (current()) this.callbacks.status("disconnected");
    };
    socket.onclose = () => {
      if (current()) this.failed(generation);
    };
    // A handshake may hang without firing an open/close event.
    armHeartbeat();
  }
  private failed(generation: number): void {
    if (!this.active || generation !== this.generation) return;
    this.generation++;
    clearTimeout(this.heartbeatTimer);
    this.request?.abort();
    if (this.socket) {
      this.socket.onopen =
        this.socket.onmessage =
        this.socket.onclose =
        this.socket.onerror =
          null;
      if (this.socket.readyState !== WebSocket.CLOSED) this.socket.close();
    }
    this.socket = null;
    this.callbacks.status("disconnected");
    const delay =
      retryDelays[Math.min(this.attempt++, retryDelays.length - 1)]!;
    clearTimeout(this.reconnectTimer);
    this.reconnectTimer = setTimeout(() => this.open(), delay);
  }
  disconnect(): void {
    this.active = false;
    this.generation++;
    clearTimeout(this.reconnectTimer);
    clearTimeout(this.heartbeatTimer);
    this.request?.abort();
    if (this.socket) {
      this.socket.onopen =
        this.socket.onmessage =
        this.socket.onclose =
        this.socket.onerror =
          null;
      this.socket.close(1000, "Application unmounted");
      this.socket = null;
    }
    this.callbacks.status("disconnected");
  }
}
