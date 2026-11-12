import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { tanstackStart } from "@tanstack/react-start/plugin/vite";
import tailwindcss from "@tailwindcss/vite";
import tsConfigPaths from "vite-tsconfig-paths";
import { nitro } from "nitro/vite";

const apiTarget = process.env["VITE_API_URL"] || "http://127.0.0.1:8000";

/** Dev-only proxies to FastAPI. Production traffic goes through Nginx (same-origin). */
const apiProxy = {
  "/api/books": { target: apiTarget, changeOrigin: true },
  "/api/categories": { target: apiTarget, changeOrigin: true },
  "/api/stats": { target: apiTarget, changeOrigin: true },
  "/api/recommendations": { target: apiTarget, changeOrigin: true },
  "/api/auth": { target: apiTarget, changeOrigin: true },
  "/api/users": { target: apiTarget, changeOrigin: true },
  "/api/reviews": { target: apiTarget, changeOrigin: true },
  "/api/wishlist": { target: apiTarget, changeOrigin: true },
  "/api/library": { target: apiTarget, changeOrigin: true },
};

export default defineConfig({
  plugins: [
    tanstackStart({
      server: { entry: "src/server.ts" },
    }),
    nitro({ preset: "node-server" }),
    react(),
    tailwindcss(),
    tsConfigPaths(),
  ],
  server: {
    port: 3000,
    host: "0.0.0.0",
    allowedHosts: true,
    proxy: apiProxy,
  },
  resolve: {
    dedupe: ["react", "react-dom"],
  },
});
