const RECONNECT_BASE_MS = 1000;
const RECONNECT_MAX_MS = 30000;

export class AudioWebSocket {
	private radioId: string;
	private onBinaryFrame: (buffer: ArrayBuffer) => void;
	private ws: WebSocket | null = null;
	private reconnectDelay = RECONNECT_BASE_MS;
	private active = true;
	private reconnectTimer: ReturnType<typeof setTimeout> | null = null;

	constructor(radioId: string, onBinaryFrame: (buffer: ArrayBuffer) => void) {
		this.radioId = radioId;
		this.onBinaryFrame = onBinaryFrame;
	}

	connect(): void {
		if (!this.active) return;

		const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
		const url = `${proto}//${location.host}/api/radio/${this.radioId}/ws/audio`;

		this.ws = new WebSocket(url);
		this.ws.binaryType = 'arraybuffer';

		this.ws.onmessage = (event: MessageEvent) => {
			if (event.data instanceof ArrayBuffer) {
				this.onBinaryFrame(event.data);
			}
		};

		this.ws.onclose = () => {
			this.ws = null;
			if (!this.active) return;
			this.scheduleReconnect();
		};

		this.ws.onerror = () => {
			this.ws?.close();
		};

		this.ws.onopen = () => {
			this.reconnectDelay = RECONNECT_BASE_MS;
		};
	}

	private scheduleReconnect(): void {
		if (!this.active) return;
		this.reconnectTimer = setTimeout(() => {
			this.connect();
		}, this.reconnectDelay);
		this.reconnectDelay = Math.min(this.reconnectDelay * 2, RECONNECT_MAX_MS);
	}

	sendBinary(buffer: ArrayBuffer): void {
		if (this.ws && this.ws.readyState === WebSocket.OPEN) {
			this.ws.send(buffer);
		}
	}

	disconnect(): void {
		this.active = false;
		if (this.reconnectTimer !== null) {
			clearTimeout(this.reconnectTimer);
			this.reconnectTimer = null;
		}
		if (this.ws) {
			this.ws.close();
			this.ws = null;
		}
	}
}

export class ControlWebSocket {
	private radioId: string;
	private onMessage: (msg: object) => void;
	private ws: WebSocket | null = null;
	private reconnectDelay = RECONNECT_BASE_MS;
	private active = true;
	private reconnectTimer: ReturnType<typeof setTimeout> | null = null;

	constructor(radioId: string, onMessage: (msg: object) => void) {
		this.radioId = radioId;
		this.onMessage = onMessage;
	}

	connect(): void {
		if (!this.active) return;

		const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
		const url = `${proto}//${location.host}/api/radio/${this.radioId}/ws/control`;

		this.ws = new WebSocket(url);

		this.ws.onmessage = (event: MessageEvent) => {
			try {
				const msg = JSON.parse(event.data as string) as object;
				this.onMessage(msg);
			} catch {
				// ignore malformed frames
			}
		};

		this.ws.onclose = () => {
			this.ws = null;
			if (!this.active) return;
			this.scheduleReconnect();
		};

		this.ws.onerror = () => {
			this.ws?.close();
		};

		this.ws.onopen = () => {
			this.reconnectDelay = RECONNECT_BASE_MS;
		};
	}

	private scheduleReconnect(): void {
		if (!this.active) return;
		this.reconnectTimer = setTimeout(() => {
			this.connect();
		}, this.reconnectDelay);
		this.reconnectDelay = Math.min(this.reconnectDelay * 2, RECONNECT_MAX_MS);
	}

	send(msg: object): void {
		if (this.ws && this.ws.readyState === WebSocket.OPEN) {
			this.ws.send(JSON.stringify(msg));
		}
	}

	disconnect(): void {
		this.active = false;
		if (this.reconnectTimer !== null) {
			clearTimeout(this.reconnectTimer);
			this.reconnectTimer = null;
		}
		if (this.ws) {
			this.ws.close();
			this.ws = null;
		}
	}
}
