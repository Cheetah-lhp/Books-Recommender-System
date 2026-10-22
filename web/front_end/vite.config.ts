import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { tanstackStart } from "@tanstack/react-start/plugin/vite";
import tailwindcss from "@tailwindcss/vite";
import tsConfigPaths from "vite-tsconfig-paths";

export default defineConfig({
  plugins: [
    // TanStack Start (SSR + server functions + file-based routing)
    tanstackStart({
      server: { entry: "src/server.ts" },
    }),
    // React Fast Refresh
    react(),
    // Tailwind CSS v4
    tailwindcss(),
    // TypeScript path aliases (@ → src/)
    tsConfigPaths(),
  ],
  server: {
    port: 3000,
    host: "0.0.0.0",
    allowedHosts: true,
    proxy: {
      "/api": {
        target: process.env.VITE_API_URL || "https://01a0c9d9-f877-73c4-a505-60067dcbdc6c-8000.eur-1.aiven.app",
        changeOrigin: true,
      },
    },
  },
  preview: {
    port: 3000,
    host: "0.0.0.0",
    allowedHosts: true,
    proxy: {
      "/api": {
        target: process.env.VITE_API_URL || "https://01a0c9d9-f877-73c4-a505-60067dcbdc6c-8000.eur-1.aiven.app",
        changeOrigin: true,
      },
    },
  },
  resolve: {
    dedupe: ["react", "react-dom"],
  },
});
