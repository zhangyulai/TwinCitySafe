/** Demo access is enforced by the backend; this flag only exposes developer UI. */
export const devControlsEnabled = import.meta.env.VITE_ENABLE_DEV_CONTROLS === 'true';
export const debugEnabled = new URLSearchParams(window.location.search).get('debug') === '1';
