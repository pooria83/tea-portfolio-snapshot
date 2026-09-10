import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin("./src/i18n/request.ts");

const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
let apiOrigin = "";
try {
  apiOrigin = new URL(apiBase).origin;
} catch {
  apiOrigin = "";
}
const wsScheme = apiOrigin.startsWith("https") ? "wss" : "ws";
const wsOrigin = apiOrigin ? `${wsScheme}://${apiOrigin.replace(/^https?:\/\//, "")}` : "";

function buildCsp(): string {
  const scriptSrc =
    process.env.NODE_ENV === "production"
      ? "'self' 'unsafe-inline'"
      : "'self' 'unsafe-inline' 'unsafe-eval'";
  return [
    "default-src 'self'",
    `script-src ${scriptSrc}`,
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: blob: https://portfolio.example.invalid https://portfolio.example.invalid https://portfolio.example.invalid https://portfolio.example.invalid https://cdnjs.cloudflare.com https://tile.openstreetmap.org https://a.tile.openstreetmap.org https://b.tile.openstreetmap.org https://c.tile.openstreetmap.org",
    `connect-src 'self' ${[apiOrigin, wsOrigin, "https://tiles.openstreetmap.org"]
      .filter(Boolean)
      .join(" ")}`,
    "font-src 'self' data:",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'self'",
    "worker-src 'self' blob:",
    "media-src 'self' blob:",
  ].join("; ");
}

const nextConfig: NextConfig = {
  reactCompiler: true,
  serverExternalPackages: ["pino", "pino-pretty"],
  allowedDevOrigins: ["portfolio.example.invalid", "portfolio.example.invalid"],
  env: {
    // Inlined at build time so the edge-runtime /api/health route can report it.
    GIT_SHA: process.env.GIT_SHA || "dev",
  },
  async headers() {
    const headers = [
      { key: "X-Content-Type-Options", value: "nosniff" },
      { key: "X-Frame-Options", value: "SAMEORIGIN" },
      { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
      { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(self)" },
      { key: "Content-Security-Policy", value: buildCsp() },
    ];
    if (process.env.NODE_ENV === "production") {
      headers.push({
        key: "Strict-Transport-Security",
        value: "max-age=63072000; includeSubDomains; preload",
      });
    }
    return [{ source: "/:path*", headers }];
  },
  async redirects() {
    return [
      { source: "/:locale/website", destination: "/:locale", permanent: true },
      {
        source: "/:locale/website/:path*",
        destination: "/:locale/:path*",
        permanent: true,
      },
    ];
  },
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "portfolio.example.invalid" },
      { protocol: "https", hostname: "portfolio.example.invalid" },
      { protocol: "https", hostname: "portfolio.example.invalid" },
      { protocol: "https", hostname: "portfolio.example.invalid" },
    ],
    formats: ["image/webp"],
    imageSizes: [64, 128, 256],
    minimumCacheTTL: 86_400,
    dangerouslyAllowLocalIP: process.env.NODE_ENV === "development",
  },
};

export default withNextIntl(nextConfig);
