import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  return {
    base: env.VITE_BASE_PATH || "/app/",
    plugins: [react()],
    server: {
      proxy: {
        "/v1": "http://localhost:3199"
      }
    }
  };
});
