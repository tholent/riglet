import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [sveltekit()],
	server: {
		proxy: {
			'/api': { target: 'http://localhost:8080', changeOrigin: true },
		},
	},
	test: {
		environment: 'node',
		include: ['src/**/*.test.ts'],
		alias: {
			'$lib': new URL('./src/lib', import.meta.url).pathname,
		},
	},
});
