import type { AudioDevice, RadioState, RigletConfig, SerialDevice, StatusResponse } from './types.js';

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
