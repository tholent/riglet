export interface RadioConfig {
	id: string;
	name: string;
	hamlib_model: number;
	serial_port: string;
	baud_rate: number;
	ptt_method: 'cat' | 'vox' | 'rts' | 'dtr';
	audio_source: string;
	audio_sink: string;
	rigctld_port: number;
	enabled: boolean;
	polling_interval_ms: number;
}

export interface RigletConfig {
	operator: { callsign: string; grid: string };
	network: { hostname: string; http_port: number };
	audio: { sample_rate: number; chunk_ms: number };
	radios: RadioConfig[];
}

export interface RadioState {
	id: string;
	name: string;
	freq: number;
	mode: string;
	ptt: boolean;
	online: boolean;
	simulation: boolean;
	smeter?: number;
}

export interface SerialDevice {
	port: string;
	vid: string;
	pid: string;
	description: string;
	guessed_model: number | null;
}

export interface AudioDevice {
	id: string;
	name: string;
	source: string;
	sink: string;
	vid: string;
	pid: string;
}

export interface StatusResponse {
	status: string;
	radios: RadioState[];
	setup_required?: boolean;
}
