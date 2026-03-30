import js from '@eslint/js';
import svelte from 'eslint-plugin-svelte';
import tseslint from 'typescript-eslint';
import globals from 'globals';

export default tseslint.config(
	js.configs.recommended,
	...tseslint.configs.recommended,
	...svelte.configs['flat/recommended'],
	{
		languageOptions: {
			globals: { ...globals.browser, ...globals.node },
		},
		rules: {
			// Allow _-prefixed variables as the conventional "intentionally unused" marker.
			'@typescript-eslint/no-unused-vars': ['error', { argsIgnorePattern: '^_', varsIgnorePattern: '^_' }],
			// SvelteKit uses goto() from $app/navigation — resolve() is not applicable.
			'svelte/no-navigation-without-resolve': 'off',
			// Intentional pattern: local $state copy of a prop, synced via $effect,
			// so the component can also mutate it locally before the prop updates.
			'svelte/prefer-writable-derived': 'off',
			// Plain Map/Set are fine for non-reactive (static or internal) data.
			'svelte/prefer-svelte-reactivity': 'off',
		},
	},
	{
		files: ['**/*.svelte'],
		languageOptions: {
			parserOptions: {
				parser: tseslint.parser,
			},
		},
	},
	{
		// AudioWorklet processors run in AudioWorkletGlobalScope, not the main
		// thread. @ts-nocheck is intentional, and the worklet globals are not
		// in the standard browser lib.
		files: ['src/lib/audio/*-worklet*.js', 'src/lib/audio/pcm-worklet*.js'],
		languageOptions: {
			globals: {
				AudioWorkletProcessor: 'readonly',
				registerProcessor: 'readonly',
				currentTime: 'readonly',
				sampleRate: 'readonly',
			},
		},
		rules: {
			'@typescript-eslint/ban-ts-comment': 'off',
			'no-undef': 'off',
		},
	},
	{
		ignores: ['build/', '.svelte-kit/', 'node_modules/'],
	},
);
