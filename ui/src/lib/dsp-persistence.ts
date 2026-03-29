import { patchDspConfig, type RxDspConfig, type TxDspConfig } from './api.js';

export class DspPersistence {
	private radioId: string;
	private rxTimer: ReturnType<typeof setTimeout> | null = null;
	private txTimer: ReturnType<typeof setTimeout> | null = null;
	private pendingRx: Partial<RxDspConfig> = {};
	private pendingTx: Partial<TxDspConfig> = {};
	private readonly debounceMs: number;

	constructor(radioId: string, debounceMs = 500) {
		this.radioId = radioId;
		this.debounceMs = debounceMs;
	}

	saveRx(partial: Partial<RxDspConfig>): void {
		this.pendingRx = { ...this.pendingRx, ...partial };
		if (this.rxTimer !== null) clearTimeout(this.rxTimer);
		this.rxTimer = setTimeout(() => {
			const patch = this.pendingRx;
			this.pendingRx = {};
			this.rxTimer = null;
			patchDspConfig(this.radioId, { rx: patch }).catch((e) => {
				console.warn('[DSP] Failed to persist RX DSP change:', e);
			});
		}, this.debounceMs);
	}

	saveTx(partial: Partial<TxDspConfig>): void {
		this.pendingTx = { ...this.pendingTx, ...partial };
		if (this.txTimer !== null) clearTimeout(this.txTimer);
		this.txTimer = setTimeout(() => {
			const patch = this.pendingTx;
			this.pendingTx = {};
			this.txTimer = null;
			patchDspConfig(this.radioId, { tx: patch }).catch((e) => {
				console.warn('[DSP] Failed to persist TX DSP change:', e);
			});
		}, this.debounceMs);
	}

	destroy(): void {
		if (this.rxTimer !== null) {
			clearTimeout(this.rxTimer);
			this.rxTimer = null;
		}
		if (this.txTimer !== null) {
			clearTimeout(this.txTimer);
			this.txTimer = null;
		}
	}
}
