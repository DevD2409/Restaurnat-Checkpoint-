import { getWsBaseUrl } from '../config/runtime';

type WebSocketCallback = (event: { type: string; data: any }) => void;

class WebSocketClient {
  private ws: WebSocket | null = null;
  private url: string = '';
  private subscribers: Set<WebSocketCallback> = new Set();
  private reconnectTimeout: any = null;
  private isConnecting: boolean = false;

  connect(channelOrPath: string) {
    const wsBase = getWsBaseUrl();
    if (!wsBase) {
      return;
    }
    const normalizedPath = channelOrPath.replace(/^\/+/, '');
    const token = localStorage.getItem('token');
    const tokenQuery = token ? `?token=${encodeURIComponent(token)}` : '';
    this.url = `${wsBase}/${normalizedPath}${tokenQuery}`;

    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      return;
    }

    this.isConnecting = true;
    try {
      this.ws = new WebSocket(this.url);

      this.ws.onopen = () => {
        this.isConnecting = false;
        console.log(`[WebSocket] Connected to ${this.url}`);
      };

      this.ws.onmessage = (messageEvent) => {
        try {
          const payload = JSON.parse(messageEvent.data);
          this.subscribers.forEach((callback) => callback(payload));
        } catch (err) {
          console.warn('[WebSocket] Non-JSON message:', messageEvent.data);
        }
      };

      this.ws.onclose = () => {
        this.isConnecting = false;
        console.log(`[WebSocket] Disconnected from ${this.url}. Retrying in 3s...`);
        this.scheduleReconnect(channelOrPath);
      };

      this.ws.onerror = (err) => {
        console.warn('[WebSocket] Error encountered:', err);
        this.ws?.close();
      };
    } catch (e) {
      this.isConnecting = false;
      this.scheduleReconnect(channelOrPath);
    }
  }

  private scheduleReconnect(channelOrPath: string) {
    if (this.reconnectTimeout) clearTimeout(this.reconnectTimeout);
    this.reconnectTimeout = setTimeout(() => {
      this.connect(channelOrPath);
    }, 3000);
  }

  subscribe(callback: WebSocketCallback) {
    this.subscribers.add(callback);
    return () => {
      this.subscribers.delete(callback);
    };
  }

  disconnect() {
    if (this.reconnectTimeout) clearTimeout(this.reconnectTimeout);
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.subscribers.clear();
  }
}

export const wsService = new WebSocketClient();

