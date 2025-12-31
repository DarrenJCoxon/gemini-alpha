import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Transpile packages from the monorepo
  transpilePackages: ["@contrarian-ai/database"],

  // Output configuration for production builds
  output: "standalone",

  // Enable strict mode for React
  reactStrictMode: true,
};

export default nextConfig;
