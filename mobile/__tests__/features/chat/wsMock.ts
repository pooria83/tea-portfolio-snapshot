export class MockWebSocket {
  static OPEN = 1;
  static CLOSED = 3;
  static CONNECTING = 0;
  static CLOSING = 2;

  static instances: MockWebSocket[] = [];

  url: string;
  readyState: number = MockWebSocket.CONNECTING;
  sent: unknown[] = [];
  onopen: (() => void) | null = null;
  onclose: ((event: {code?: number; reason?: string}) => void) | null = null;
  onerror: (() => void) | null = null;
  onmessage: ((event: {data?: unknown}) => void) | null = null;

  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);
  }

  send(data: unknown) {
    this.sent.push(data);
  }

  close(code?: number, reason?: string) {
    this.readyState = MockWebSocket.CLOSING;
    queueMicrotask(() => {
      this.readyState = MockWebSocket.CLOSED;
      this.onclose?.({code, reason});
    });
  }

  open() {
    this.readyState = MockWebSocket.OPEN;
    this.onopen?.();
  }

  receive(data: unknown) {
    this.onmessage?.({data: JSON.stringify(data)});
  }

  get lastSent(): unknown {
    return this.sent[this.sent.length - 1];
  }
}

export function installMockWebSocket() {
  const original = globalThis.WebSocket;
  globalThis.WebSocket = MockWebSocket as unknown as typeof WebSocket;
  MockWebSocket.instances = [];
  return {
    MockWebSocket,
    restore: () => {
      globalThis.WebSocket = original;
    },
  };
}

export function expectSendFrame(
  socket: MockWebSocket,
  type: string,
): Record<string, unknown> {
  const frame = socket.sent.find((entry) => {
    if (typeof entry !== 'string') {
      return false;
    }
    try {
      return (JSON.parse(entry) as Record<string, unknown>).type === type;
    } catch {
      return false;
    }
  });
  if (typeof frame !== 'string') {
    throw new Error(`No ${type} frame was sent`);
  }
  return JSON.parse(frame) as Record<string, unknown>;
}
