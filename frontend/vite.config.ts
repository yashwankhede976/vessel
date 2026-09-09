import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Vite config for the Vessel frontend.
// The dev server runs on port 5173 (matches the backend CORS default).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
  },
});
