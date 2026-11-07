import { defineConfig } from "vite";
import tailwindcss from "@tailwindcss/vite";

// Builds to static/dist/app.{js,css} with stable names; Django appends ?v=ASSET_VERSION.
export default defineConfig({
  plugins: [tailwindcss()],
  build: {
    outDir: "static/dist",
    emptyOutDir: true,
    cssCodeSplit: false,
    rollupOptions: {
      input: "static_src/main.js",
      output: {
        entryFileNames: "app.js",
        assetFileNames: (a) => (a.names?.[0]?.endsWith(".css") ? "app.css" : "assets/[name][extname]"),
        inlineDynamicImports: true,
      },
    },
  },
});
