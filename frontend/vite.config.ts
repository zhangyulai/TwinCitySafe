import { fileURLToPath, URL } from "node:url";
import { defineConfig, loadEnv } from "vite";
import vue from "@vitejs/plugin-vue";
import cesium from "vite-plugin-cesium";

const envDir = fileURLToPath(new URL("..", import.meta.url));
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, envDir, "");
  return {
    plugins: [vue(), cesium()],
    envDir,
    build: {
      rollupOptions: {
        output: {
          manualChunks(id) {
            if (id.includes("/node_modules/echarts/")) return "echarts";
            if (id.includes("/node_modules/zrender/")) return "chart-renderer";
            // Cache the graphics engine separately from the editable park and UI.
            if (id.includes("/node_modules/three/build/three.core.js"))
              return "three-core";
            if (id.includes("/node_modules/three/")) return "three-renderer";
          },
        },
      },
    },
    preview: { host: "127.0.0.1", port: Number(env.FRONTEND_PORT || 5173), strictPort: true },
    server: {
      host: "127.0.0.1",
      port: Number(env.FRONTEND_PORT || 5173),
      strictPort: true,
      proxy: {
        "/ws": {
          target: env.VITE_API_PROXY_TARGET || "http://127.0.0.1:8000",
          ws: true,
          changeOrigin: false,
        },
        "/api": {
          target: env.VITE_API_PROXY_TARGET || "http://127.0.0.1:8000",
          changeOrigin: true,
        },
      },
    },
  };
});
