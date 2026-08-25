import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      "/auth": { target: process.env.VITE_API_URL || "http://localhost:8000", changeOrigin: true },
      "/chat": { target: process.env.VITE_API_URL || "http://localhost:8000", changeOrigin: true },
      "/products": { target: process.env.VITE_API_URL || "http://localhost:8000", changeOrigin: true },
      "/fetch-link": { target: process.env.VITE_API_URL || "http://localhost:8000", changeOrigin: true },
      "/identify-image": { target: process.env.VITE_API_URL || "http://localhost:8000", changeOrigin: true },
      "/compare": { target: process.env.VITE_API_URL || "http://localhost:8000", changeOrigin: true },
      "/reviews": { target: process.env.VITE_API_URL || "http://localhost:8000", changeOrigin: true },
      "/history": { target: process.env.VITE_API_URL || "http://localhost:8000", changeOrigin: true },
      "/wishlist": { target: process.env.VITE_API_URL || "http://localhost:8000", changeOrigin: true },
      "/admin": { target: process.env.VITE_API_URL || "http://localhost:8000", changeOrigin: true },
      "/health": { target: process.env.VITE_API_URL || "http://localhost:8000", changeOrigin: true },
      "/currency": { target: process.env.VITE_API_URL || "http://localhost:8000", changeOrigin: true },
      "/deals": { target: process.env.VITE_API_URL || "http://localhost:8000", changeOrigin: true },
      "/barcode": { target: process.env.VITE_API_URL || "http://localhost:8000", changeOrigin: true },
    },
  },
  build: {
    outDir: "dist",
  },
});
