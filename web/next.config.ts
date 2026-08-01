import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin("./src/i18n/request.ts");

const nextConfig: NextConfig = {
  // Self-contained server output for Docker/Fly deploys.
  output: "standalone",
  // onnxruntime-web ships wasm/worker assets; don't let webpack try to bundle `fs` etc.
  webpack: (config) => {
    config.resolve.fallback = { ...config.resolve.fallback, fs: false, path: false };
    return config;
  },
};

export default withNextIntl(nextConfig);
