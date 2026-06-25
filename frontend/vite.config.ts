import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The frontend calls "/api/..." (same origin as the page); Vite proxies that to
// the analyst API server-side. This avoids browser CORS / IPv4-vs-IPv6 loopback
// issues entirely — the page never makes a cross-origin request.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5180,
    strictPort: true,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/api/, ""),
      },
    },
  },
});
