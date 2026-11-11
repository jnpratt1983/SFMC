import type { NextConfig } from "next";
import { PHASE_DEVELOPMENT_SERVER } from "next/constants";

export default function nextConfig(phase: string): NextConfig {
  return {
    output: "export",
    // The static export needs trailing slashes (out/<route>/index.html). The dev
    // server does not, and behind a proxy that strips them (the v0 preview) the
    // two redirects chase each other: "redirected you too many times".
    trailingSlash: phase !== PHASE_DEVELOPMENT_SERVER,
    images: { unoptimized: true },
    turbopack: {
      rules: {
        "*.css": {
          loaders: ["@tailwindcss/turbopack"],
          as: "*.css",
        },
      },
    },
  };
}
