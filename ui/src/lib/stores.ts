import { writable } from 'svelte/store';
import type { RadioState, RigletConfig } from './types.js';
import type { ThemeMode } from './theme.js';

export const radioState = writable<RadioState | null>(null);
export const appConfig = writable<RigletConfig | null>(null);
export const setupStep = writable<number>(0);
export const claimedResources = writable<Record<string, string>>({}); // resourceId -> radioId
export const theme = writable<ThemeMode>('system');
