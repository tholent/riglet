/**
 * Region-aware amateur band plan data module.
 *
 * Mirrors server/bandplan.py — keep both in sync when adding regions or bands.
 */

export interface BandDef {
	name: string;
	lower_mhz: number;
	upper_mhz: number;
	default_mode: string;
}

// ---------------------------------------------------------------------------
// US (FCC / ARRL) band plan
// ---------------------------------------------------------------------------
const US_BANDS: BandDef[] = [
	{ name: '160m', lower_mhz: 1.8, upper_mhz: 2.0, default_mode: 'LSB' },
	{ name: '80m', lower_mhz: 3.5, upper_mhz: 4.0, default_mode: 'LSB' },
	{ name: '60m', lower_mhz: 5.3305, upper_mhz: 5.4065, default_mode: 'USB' },
	{ name: '40m', lower_mhz: 7.0, upper_mhz: 7.3, default_mode: 'LSB' },
	{ name: '30m', lower_mhz: 10.1, upper_mhz: 10.15, default_mode: 'CW' },
	{ name: '20m', lower_mhz: 14.0, upper_mhz: 14.35, default_mode: 'USB' },
	{ name: '17m', lower_mhz: 18.068, upper_mhz: 18.168, default_mode: 'USB' },
	{ name: '15m', lower_mhz: 21.0, upper_mhz: 21.45, default_mode: 'USB' },
	{ name: '12m', lower_mhz: 24.89, upper_mhz: 24.99, default_mode: 'USB' },
	{ name: '10m', lower_mhz: 28.0, upper_mhz: 29.7, default_mode: 'USB' },
	{ name: '6m', lower_mhz: 50.0, upper_mhz: 54.0, default_mode: 'USB' },
	{ name: '2m', lower_mhz: 144.0, upper_mhz: 148.0, default_mode: 'FM' },
	{ name: '70cm', lower_mhz: 420.0, upper_mhz: 450.0, default_mode: 'FM' },
];

// ---------------------------------------------------------------------------
// EU (IARU Region 1) band plan
// ---------------------------------------------------------------------------
const EU_BANDS: BandDef[] = [
	{ name: '160m', lower_mhz: 1.81, upper_mhz: 2.0, default_mode: 'LSB' },
	{ name: '80m', lower_mhz: 3.5, upper_mhz: 3.8, default_mode: 'LSB' },
	{ name: '60m', lower_mhz: 5.3515, upper_mhz: 5.3665, default_mode: 'USB' },
	{ name: '40m', lower_mhz: 7.0, upper_mhz: 7.2, default_mode: 'LSB' },
	{ name: '30m', lower_mhz: 10.1, upper_mhz: 10.15, default_mode: 'CW' },
	{ name: '20m', lower_mhz: 14.0, upper_mhz: 14.35, default_mode: 'USB' },
	{ name: '17m', lower_mhz: 18.068, upper_mhz: 18.168, default_mode: 'USB' },
	{ name: '15m', lower_mhz: 21.0, upper_mhz: 21.45, default_mode: 'USB' },
	{ name: '12m', lower_mhz: 24.89, upper_mhz: 24.99, default_mode: 'USB' },
	{ name: '10m', lower_mhz: 28.0, upper_mhz: 29.7, default_mode: 'USB' },
	{ name: '6m', lower_mhz: 50.0, upper_mhz: 52.0, default_mode: 'USB' },
	{ name: '2m', lower_mhz: 144.0, upper_mhz: 146.0, default_mode: 'FM' },
	{ name: '70cm', lower_mhz: 430.0, upper_mhz: 440.0, default_mode: 'FM' },
];

// ---------------------------------------------------------------------------
// AU (IARU Region 3 / WIA) band plan
// ---------------------------------------------------------------------------
const AU_BANDS: BandDef[] = [
	{ name: '160m', lower_mhz: 1.8, upper_mhz: 1.875, default_mode: 'LSB' },
	{ name: '80m', lower_mhz: 3.5, upper_mhz: 3.9, default_mode: 'LSB' },
	{ name: '60m', lower_mhz: 5.3515, upper_mhz: 5.3665, default_mode: 'USB' },
	{ name: '40m', lower_mhz: 7.0, upper_mhz: 7.3, default_mode: 'LSB' },
	{ name: '30m', lower_mhz: 10.1, upper_mhz: 10.15, default_mode: 'CW' },
	{ name: '20m', lower_mhz: 14.0, upper_mhz: 14.35, default_mode: 'USB' },
	{ name: '17m', lower_mhz: 18.068, upper_mhz: 18.168, default_mode: 'USB' },
	{ name: '15m', lower_mhz: 21.0, upper_mhz: 21.45, default_mode: 'USB' },
	{ name: '12m', lower_mhz: 24.89, upper_mhz: 24.99, default_mode: 'USB' },
	{ name: '10m', lower_mhz: 28.0, upper_mhz: 29.7, default_mode: 'USB' },
	{ name: '6m', lower_mhz: 50.0, upper_mhz: 54.0, default_mode: 'USB' },
	{ name: '2m', lower_mhz: 144.0, upper_mhz: 148.0, default_mode: 'FM' },
	{ name: '70cm', lower_mhz: 420.0, upper_mhz: 450.0, default_mode: 'FM' },
];

export const BAND_PLANS: Record<string, BandDef[]> = {
	us: US_BANDS,
	eu: EU_BANDS,
	au: AU_BANDS,
};

/**
 * Return the band list for the given region.
 * Throws if the region is unknown.
 */
export function getBands(region: string): BandDef[] {
	const bands = BAND_PLANS[region];
	if (!bands) {
		const known = Object.keys(BAND_PLANS).sort().join(', ');
		throw new Error(`Unknown region '${region}'. Known regions: ${known}`);
	}
	return bands;
}
