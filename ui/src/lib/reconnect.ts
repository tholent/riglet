import { getStatus } from './api.js';

export async function waitForRestart(timeoutMs = 30000): Promise<boolean> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    await new Promise<void>((r) => setTimeout(r, 1000));
    try {
      const status = await getStatus();
      if (status.status === 'ok') return true;
    } catch {
      // backend not yet up — keep polling
    }
  }
  return false;
}
