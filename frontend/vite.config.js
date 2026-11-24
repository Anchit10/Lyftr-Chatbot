import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Vite config. We run the dev server and preview on port 3000 so it matches the
// assignment ("frontend on http://localhost:3000").
export default defineConfig({
  plugins: [react()],
  server: { host: true, port: 3000 },
  preview: { host: true, port: 3000 },
});
