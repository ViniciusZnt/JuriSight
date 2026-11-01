import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Imagem Docker de produção: server.js autocontido (frontend/Dockerfile).
  output: "standalone",
};

export default nextConfig;
