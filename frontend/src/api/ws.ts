// Typed client for the single /ws/live socket (see backend/src/wled_x/api/ws.py).
// Every message is a JSON object with a `type` discriminator. Consumers subscribe
// to a type rather than opening their own connection, so the whole app shares
// one socket with auto-reconnect.

type Listener = (message: Record<string, unknown>) => void;

const WS_URL = `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws/live`;
const RECONNECT_DELAY_MS = 1500;

class LiveSocket {
  private socket: WebSocket | null = null;
  private listeners = new Map<string, Set<Listener>>();
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;

  connect(): void {
    if (this.socket) return;
    const socket = new WebSocket(WS_URL);
    this.socket = socket;

    socket.onmessage = (event) => {
      let message: Record<string, unknown>;
      try {
        message = JSON.parse(event.data);
      } catch {
        return;
      }
      const type = typeof message.type === "string" ? message.type : "";
      this.listeners.get(type)?.forEach((fn) => fn(message));
      this.listeners.get("*")?.forEach((fn) => fn(message));
    };

    socket.onclose = () => {
      this.socket = null;
      this.reconnectTimer = setTimeout(() => this.connect(), RECONNECT_DELAY_MS);
    };

    socket.onerror = () => socket.close();
  }

  disconnect(): void {
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this.socket?.close();
    this.socket = null;
  }

  send(message: Record<string, unknown>): void {
    if (this.socket?.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify(message));
    }
  }

  /** Subscribe to messages of a given `type` (or "*" for all). Returns an unsubscribe fn. */
  on(type: string, listener: Listener): () => void {
    if (!this.listeners.has(type)) this.listeners.set(type, new Set());
    this.listeners.get(type)!.add(listener);
    return () => this.listeners.get(type)?.delete(listener);
  }
}

export const liveSocket = new LiveSocket();
