import { FiLog } from './FiLog';

export interface WsCallbacks {
  onMessage: (data: Record<string, unknown>) => void;
  onOpen:    () => void;
  onFailure: (event: Event) => void;
  onClosed:  (code: number, reason: string) => void;
}

export class WebSocketManager {
  private ws: WebSocket | null = null;

  constructor(private readonly callbacks: WsCallbacks) {}

  connect(url: string): void {
    FiLog.i('WS', `Connecting → ${url}`);
    this.ws = new WebSocket(url);
    this.ws.binaryType = 'arraybuffer';

    this.ws.onopen = () => {
      FiLog.i('WS', 'Connected');
      this.callbacks.onOpen();
    };

    this.ws.onmessage = (ev) => {
      if (typeof ev.data === 'string') {
        FiLog.d('WS', `←JSON ${ev.data.slice(0, 140)}`);
        try {
          this.callbacks.onMessage(JSON.parse(ev.data) as Record<string, unknown>);
        } catch {
          FiLog.e('WS', 'JSON parse error');
        }
      }
      // Binary frames from server are not expected but silently ignored
    };

    this.ws.onerror = (ev) => {
      FiLog.e('WS', 'Error');
      this.callbacks.onFailure(ev);
    };

    this.ws.onclose = (ev) => {
      FiLog.i('WS', `Closed ${ev.code} ${ev.reason}`);
      this.callbacks.onClosed(ev.code, ev.reason);
    };
  }

  sendJson(payload: Record<string, unknown>): boolean {
    if (this.ws?.readyState !== WebSocket.OPEN) {
      FiLog.w('WS', 'sendJson: not connected');
      return false;
    }
    const text = JSON.stringify(payload);
    FiLog.d('WS', `→JSON ${text.slice(0, 140)}`);
    this.ws.send(text);
    return true;
  }

  sendBinary(data: ArrayBuffer): boolean {
    if (this.ws?.readyState !== WebSocket.OPEN) return false;
    this.ws.send(data);
    return true;
  }

  close(): void {
    FiLog.i('WS', 'Closing');
    this.ws?.close(1000, 'Session complete');
    this.ws = null;
  }
}
