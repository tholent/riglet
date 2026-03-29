import type { AudioDevice, PresetConfig, RadioState, RigletConfig, SerialDevice, StatusResponse } from './types.js';
import type { BandDef } from './bandplan.js';

export interface RxDspConfig {
	highpass_enabled: boolean;
	highpass_freq: number;
	lowpass_enabled: boolean;
	lowpass_freq: number;
	peak_enabled: boolean;
	peak_freq: number;
	peak_gain: number;
	peak_q: number;
	noise_blanker_enabled: boolean;
	noise_blanker_freq: number;
	notch_enabled: boolean;
	notch_mode: 'manual' | 'auto';
	notch_freq: number;
	notch_q: number;
	bandpass_enabled: boolean;
	bandpass_preset: 'voice' | 'cw' | 'manual';
	bandpass_center: number;
	bandpass_width: number;
	nr_enabled: boolean;
	nr_amount: number;
}

export interface TxDspConfig {
	highpass_enabled: boolean;
	highpass_freq: number;
	lowpass_enabled: boolean;
	lowpass_freq: number;
	eq_enabled: boolean;
	eq_bass_gain: number;
	eq_mid_gain: number;
	eq_treble_gain: number;
	compressor_enabled: boolean;
	compressor_preset: 'off' | 'light' | 'medium' | 'heavy' | 'manual';
	compressor_threshold: number;
	compressor_ratio: number;
	compressor_attack: number;
	compressor_release: number;
	limiter_enabled: boolean;
	limiter_threshold: number;
	gate_enabled: boolean;
	gate_threshold: number;
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
	const res = await fetch(path, options);
	if (!res.ok) {
		const text = await res.text().catch(() => res.statusText);
		throw new Error(`${res.status} ${res.statusText}: ${text}`);
	}
	if (res.status === 204 || res.headers.get('content-length') === '0') {
		return undefined as T;
	}
	return res.json() as Promise<T>;
}

function json(method: string, body: unknown): RequestInit {
	return {
		method,
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(body),
	};
}

export function getStatus(): Promise<StatusResponse> {
	return request<StatusResponse>('/api/status');
}

export function getConfig(): Promise<RigletConfig> {
	return request<RigletConfig>('/api/config');
}

export function postConfig(config: RigletConfig): Promise<RigletConfig> {
	return request<RigletConfig>('/api/config', json('POST', config));
}

export function postConfigRestart(): Promise<void> {
	return request<void>('/api/config/restart', { method: 'POST' });
}

export function getSerialDevices(): Promise<SerialDevice[]> {
	return request<SerialDevice[]>('/api/devices/serial');
}

export function getAudioDevices(): Promise<AudioDevice[]> {
	return request<AudioDevice[]>('/api/devices/audio');
}

export function getRadioCat(radioId: string): Promise<RadioState> {
	return request<RadioState>(`/api/radio/${radioId}/cat`);
}

export function postFreq(radioId: string, freq: number): Promise<RadioState> {
	return request<RadioState>(`/api/radio/${radioId}/cat/freq`, json('POST', { freq }));
}

export function postMode(radioId: string, mode: string): Promise<RadioState> {
	return request<RadioState>(`/api/radio/${radioId}/cat/mode`, json('POST', { mode }));
}

export function postPtt(radioId: string, active: boolean): Promise<RadioState> {
	return request<RadioState>(`/api/radio/${radioId}/cat/ptt`, json('POST', { active }));
}

export function postNudge(radioId: string, direction: 1 | -1): Promise<RadioState> {
	return request<RadioState>(`/api/radio/${radioId}/cat/nudge`, json('POST', { direction }));
}

export function postCatTest(radioId: string): Promise<{ success: boolean; freq?: number; error?: string }> {
	return request<{ success: boolean; freq?: number; error?: string }>(
		`/api/radio/${radioId}/cat/test`,
		{ method: 'POST' },
	);
}

export function postAudioVolume(
	radioId: string,
	rx_volume: number,
	tx_gain: number,
	nr_level: number,
): Promise<void> {
	return request<void>(
		`/api/radio/${radioId}/audio/volume`,
		json('POST', { rx_volume, tx_gain, nr_level }),
	);
}

export function getHamlibModels(): Promise<{ id: number; name: string }[]> {
	return request<{ id: number; name: string }[]>('/api/hamlib/models');
}

export function getBandPlan(): Promise<{ region: string; bands: BandDef[] }> {
	return request<{ region: string; bands: BandDef[] }>('/api/bandplan');
}

export function getPresets(): Promise<{ presets: PresetConfig[] }> {
	return request<{ presets: PresetConfig[] }>('/api/presets');
}

export function createPreset(preset: PresetConfig): Promise<{ presets: PresetConfig[] }> {
	return request<{ presets: PresetConfig[] }>('/api/presets', json('POST', preset));
}

export function updatePreset(
	presetId: string,
	preset: PresetConfig,
): Promise<{ presets: PresetConfig[] }> {
	return request<{ presets: PresetConfig[] }>(`/api/presets/${presetId}`, json('PUT', preset));
}

export function deletePreset(presetId: string): Promise<{ presets: PresetConfig[] }> {
	return request<{ presets: PresetConfig[] }>(`/api/presets/${presetId}`, { method: 'DELETE' });
}

export function importPresets(presets: PresetConfig[]): Promise<{ presets: PresetConfig[] }> {
	return request<{ presets: PresetConfig[] }>('/api/presets/import', json('POST', { presets }));
}

export function exportPresets(): Promise<{ presets: PresetConfig[] }> {
	return request<{ presets: PresetConfig[] }>('/api/presets/export');
}

export function getRadioModes(radioId: string): Promise<{ modes: string[] }> {
	return request<{ modes: string[] }>(`/api/radio/${radioId}/modes`);
}

export function getDspConfig(radioId: string): Promise<{ rx: RxDspConfig; tx: TxDspConfig }> {
	return request<{ rx: RxDspConfig; tx: TxDspConfig }>(`/api/radios/${radioId}/dsp`);
}

export function patchDspConfig(
	radioId: string,
	patch: { rx?: Partial<RxDspConfig>; tx?: Partial<TxDspConfig> },
): Promise<{ rx: RxDspConfig; tx: TxDspConfig }> {
	return request<{ rx: RxDspConfig; tx: TxDspConfig }>(
		`/api/radios/${radioId}/dsp`,
		json('PATCH', patch),
	);
}
