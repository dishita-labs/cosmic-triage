import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The console is a player of replay artifacts; all data comes from the FastAPI service.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:8000",
      "/theater": "http://127.0.0.1:8000",
    },
  },
});
