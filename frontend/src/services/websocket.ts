import { getWsBaseUrl } from '../config/runtime';

export type WebSocketCallback = (event: { type: string; data: any }) => void;

export type WebSocketConnectionStatus =
  | 'IDLE'
  | 'CONNECTING'
  | 'CONNECTED'
  | 'DISCONNECTED'
  | 'UNAUTHORIZED';

export interface ConnectOptions {
  token?: string | null;
  sessionToken?: string | null;
  restaurantId?: number | null;
}

type StatusCallback = (status: WebSocketConnectionStatus, error: string | null) => void;

class WebSocketClient {
  private ws: WebSocket | null = null;
  private url: string = '';
  private currentChannelOrPath: string = '';
  private currentOptions: ConnectOptions = {};
  private subscribers: Set<WebSocketCallback> = new Set();
  private statusSubscribers: Set<StatusCallback> = new Set();
  private reconnectTimeout: ReturnType<typeof setTimeout> | null = null;
  private isConnecting: boolean = false;
  private status: WebSocketConnectionStatus = 'IDLE';
  private authError: string | null = null;

  getStatus(): WebSocketConnectionStatus {
    return this.status;
  }

  getAuthError(): string | null {
    return this.authError;
  }

  private notifyStatus() {
    this.statusSubscribers.forEach((cb) => cb(this.status, this.authError));
  }

  private notifySubscribers(event: { type: string; data: any }) {
    this.subscribers.forEach((cb) => cb(event));
  }

  /**
   * Redacts sensitive tokens (JWTs and session tokens) from URLs before logging.
   */
  private getSanitizedUrl(rawUrl: string): string {
    if (!rawUrl) return '';
    try {
      const parsed = new URL(rawUrl);
      if (parsed.searchParams.has('token')) {
        parsed.searchParams.set('token', '[REDACTED]');
      }
      if (parsed.searchParams.has('session_token')) {
        parsed.searchParams.set('session_token', '[REDACTED]');
      }
      return parsed.toString();
    } catch {
      return rawUrl
        .replace(/([?&]token=)[^&]+/gi, '$1[REDACTED]')
        .replace(/([?&]session_token=)[^&]+/gi, '$1[REDACTED]');
    }
  }

  /**
   * Constructs the backend WebSocket URL with supported query parameters.
   */
  private buildUrl(channelOrPath: string, options: ConnectOptions): string {
    const wsBase = getWsBaseUrl();
    if (!wsBase) {
      return '';
    }

    const normalizedPath = channelOrPath.replace(/^\/+/, '');
    const searchParams = new URLSearchParams();

    if (options.token) {
      searchParams.set('token', options.token);
    }
    if (options.sessionToken) {
      searchParams.set('session_token', options.sessionToken);
    }
    if (options.restaurantId !== undefined && options.restaurantId !== null && options.restaurantId > 0) {
      searchParams.set('restaurant_id', String(options.restaurantId));
    }

    const queryString = searchParams.toString();
    return queryString ? `${wsBase}/${normalizedPath}?${queryString}` : `${wsBase}/${normalizedPath}`;
  }

  connect(channelOrPath: string, options: ConnectOptions = {}) {
    const wsBase = getWsBaseUrl();
    if (!wsBase) {
      this.status = 'IDLE';
      this.notifyStatus();
      return;
    }

    const targetUrl = this.buildUrl(channelOrPath, options);
    if (!targetUrl) {
      return;
    }

    // Avoid redundant reconnect if already connected or connecting to the exact same target URL
    if (
      this.ws &&
      this.url === targetUrl &&
      (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)
    ) {
      return;
    }

    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }

    // Close any prior socket instance
    if (this.ws) {
      try {
        this.ws.onopen = null;
        this.ws.onclose = null;
        this.ws.onerror = null;
        this.ws.onmessage = null;
        this.ws.close();
      } catch {
        // ignore
      }
      this.ws = null;
    }

    this.url = targetUrl;
    this.currentChannelOrPath = channelOrPath;
    this.currentOptions = options;
    this.isConnecting = true;
    this.status = 'CONNECTING';
    this.authError = null;
    this.notifyStatus();

    try {
      this.ws = new WebSocket(this.url);

      this.ws.onopen = () => {
        this.isConnecting = false;
        this.status = 'CONNECTED';
        this.authError = null;
        this.notifyStatus();
        console.log(`[WebSocket] Connected to ${this.getSanitizedUrl(this.url)}`);
      };

      this.ws.onmessage = (messageEvent) => {
        try {
          const payload = JSON.parse(messageEvent.data);
          this.notifySubscribers(payload);
        } catch {
          console.warn('[WebSocket] Non-JSON message payload received');
        }
      };

      this.ws.onclose = (event: CloseEvent) => {
        this.isConnecting = false;
        const sanitized = this.getSanitizedUrl(this.url);

        if (event.code === 1008) {
          this.status = 'UNAUTHORIZED';
          this.authError = 'WebSocket connection rejected: Session expired or access unauthorized (code 1008).';
          try {
            sessionStorage.removeItem('smart_restaurant_session_token');
            localStorage.removeItem('smart_restaurant_session_token');
          } catch {
            // ignore
          }
          this.notifyStatus();
          console.warn(
            `[WebSocket] Access rejected for ${sanitized}: Session expired or unauthorized (code 1008). Automatic reconnection halted.`
          );
          this.notifySubscribers({
            type: 'WS_AUTH_ERROR',
            data: {
              code: 1008,
              reason: 'Session expired or unauthorized',
              path: channelOrPath,
            },
          });
          // Do NOT retry indefinitely with the same invalid credentials
          return;
        }

        this.status = 'DISCONNECTED';
        this.notifyStatus();
        console.log(`[WebSocket] Disconnected from ${sanitized} (code ${event.code}). Retrying in 3s...`);
        this.scheduleReconnect(channelOrPath, options);
      };

      this.ws.onerror = () => {
        console.warn(`[WebSocket] Transport error on ${this.getSanitizedUrl(this.url)}`);
      };
    } catch {
      this.isConnecting = false;
      this.status = 'DISCONNECTED';
      this.notifyStatus();
      this.scheduleReconnect(channelOrPath, options);
    }
  }

  private scheduleReconnect(channelOrPath: string, options: ConnectOptions) {
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }
    // Never reconnect automatically if unauthorized (1008)
    if (this.status === 'UNAUTHORIZED') {
      return;
    }
    this.reconnectTimeout = setTimeout(() => {
      this.connect(channelOrPath, options);
    }, 3000);
  }

  subscribe(callback: WebSocketCallback) {
    this.subscribers.add(callback);
    return () => {
      this.subscribers.delete(callback);
    };
  }

  onStatusChange(callback: StatusCallback) {
    this.statusSubscribers.add(callback);
    callback(this.status, this.authError);
    return () => {
      this.statusSubscribers.delete(callback);
    };
  }

  disconnect() {
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }
    if (this.ws) {
      try {
        this.ws.onopen = null;
        this.ws.onclose = null;
        this.ws.onerror = null;
        this.ws.onmessage = null;
        this.ws.close();
      } catch {
        // ignore
      }
      this.ws = null;
    }
    this.status = 'IDLE';
    this.authError = null;
    this.isConnecting = false;
    this.notifyStatus();
    this.subscribers.clear();
  }
}

export const wsService = new WebSocketClient();
