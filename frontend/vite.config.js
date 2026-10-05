import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In dev, /api and /files are proxied to FastAPI so you never fight CORS.
const backend = process.env.VITE_PROXY_TARGET || "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { "/api": backend, "/files": backend },
  },
});
