import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Self-contained server for the Docker image (see Dockerfile).
  output: "standalone",
  experimental: {
    serverActions: {
      // CV uploads go through a Server Action; the backend accepts up to 10 MB, plus multipart overhead.
      bodySizeLimit: "11mb",
    },
  },
};

export default nextConfig;
