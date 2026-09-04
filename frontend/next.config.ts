import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Emits .next/standalone with only the traced runtime files, so the Docker
  // image ships a ~200MB server instead of the full node_modules tree.
  // Local `next dev` / `next start` are unaffected.
  output: "standalone",
  async rewrites() {
    return [
      {
        source: "/",
        destination: "/landing.html",
      },
    ];
  },
};

export default nextConfig;
