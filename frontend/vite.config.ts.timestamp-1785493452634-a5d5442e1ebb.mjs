// vite.config.ts
import { defineConfig } from "file:///C:/Users/ROHIT/OneDrive/Desktop/SteGO/frontend/node_modules/vite/dist/node/index.js";
import react from "file:///C:/Users/ROHIT/OneDrive/Desktop/SteGO/frontend/node_modules/@vitejs/plugin-react/dist/index.js";
import tailwindcss from "file:///C:/Users/ROHIT/OneDrive/Desktop/SteGO/frontend/node_modules/@tailwindcss/vite/dist/index.mjs";
var vite_config_default = defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      "/auth": "http://127.0.0.1:8000",
      "/encode": "http://127.0.0.1:8000",
      "/decode": "http://127.0.0.1:8000",
      "/operations": "http://127.0.0.1:8000",
      "/storage": "http://127.0.0.1:8000"
    }
  }
});
export {
  vite_config_default as default
};
//# sourceMappingURL=data:application/json;base64,ewogICJ2ZXJzaW9uIjogMywKICAic291cmNlcyI6IFsidml0ZS5jb25maWcudHMiXSwKICAic291cmNlc0NvbnRlbnQiOiBbImNvbnN0IF9fdml0ZV9pbmplY3RlZF9vcmlnaW5hbF9kaXJuYW1lID0gXCJDOlxcXFxVc2Vyc1xcXFxST0hJVFxcXFxPbmVEcml2ZVxcXFxEZXNrdG9wXFxcXFN0ZUdPXFxcXGZyb250ZW5kXCI7Y29uc3QgX192aXRlX2luamVjdGVkX29yaWdpbmFsX2ZpbGVuYW1lID0gXCJDOlxcXFxVc2Vyc1xcXFxST0hJVFxcXFxPbmVEcml2ZVxcXFxEZXNrdG9wXFxcXFN0ZUdPXFxcXGZyb250ZW5kXFxcXHZpdGUuY29uZmlnLnRzXCI7Y29uc3QgX192aXRlX2luamVjdGVkX29yaWdpbmFsX2ltcG9ydF9tZXRhX3VybCA9IFwiZmlsZTovLy9DOi9Vc2Vycy9ST0hJVC9PbmVEcml2ZS9EZXNrdG9wL1N0ZUdPL2Zyb250ZW5kL3ZpdGUuY29uZmlnLnRzXCI7aW1wb3J0IHsgZGVmaW5lQ29uZmlnIH0gZnJvbSAndml0ZSdcbmltcG9ydCByZWFjdCBmcm9tICdAdml0ZWpzL3BsdWdpbi1yZWFjdCdcbmltcG9ydCB0YWlsd2luZGNzcyBmcm9tICdAdGFpbHdpbmRjc3Mvdml0ZSdcblxuLy8gaHR0cHM6Ly92aXRlLmRldi9jb25maWcvXG5leHBvcnQgZGVmYXVsdCBkZWZpbmVDb25maWcoe1xuICBwbHVnaW5zOiBbcmVhY3QoKSwgdGFpbHdpbmRjc3MoKV0sXG4gIHNlcnZlcjoge1xuICAgIHByb3h5OiB7XG4gICAgICAnL2F1dGgnOiAnaHR0cDovLzEyNy4wLjAuMTo4MDAwJyxcbiAgICAgICcvZW5jb2RlJzogJ2h0dHA6Ly8xMjcuMC4wLjE6ODAwMCcsXG4gICAgICAnL2RlY29kZSc6ICdodHRwOi8vMTI3LjAuMC4xOjgwMDAnLFxuICAgICAgJy9vcGVyYXRpb25zJzogJ2h0dHA6Ly8xMjcuMC4wLjE6ODAwMCcsXG4gICAgICAnL3N0b3JhZ2UnOiAnaHR0cDovLzEyNy4wLjAuMTo4MDAwJyxcbiAgICB9XG4gIH1cbn0pXG4iXSwKICAibWFwcGluZ3MiOiAiO0FBQTBVLFNBQVMsb0JBQW9CO0FBQ3ZXLE9BQU8sV0FBVztBQUNsQixPQUFPLGlCQUFpQjtBQUd4QixJQUFPLHNCQUFRLGFBQWE7QUFBQSxFQUMxQixTQUFTLENBQUMsTUFBTSxHQUFHLFlBQVksQ0FBQztBQUFBLEVBQ2hDLFFBQVE7QUFBQSxJQUNOLE9BQU87QUFBQSxNQUNMLFNBQVM7QUFBQSxNQUNULFdBQVc7QUFBQSxNQUNYLFdBQVc7QUFBQSxNQUNYLGVBQWU7QUFBQSxNQUNmLFlBQVk7QUFBQSxJQUNkO0FBQUEsRUFDRjtBQUNGLENBQUM7IiwKICAibmFtZXMiOiBbXQp9Cg==
