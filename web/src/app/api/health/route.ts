import { NextResponse } from "next/server";

export const runtime = "edge";

const startedAtMs = Date.now();

export function GET() {
  return NextResponse.json({
    status: "ok",
    service: "product-graph-web-ui",
    environment: process.env.NODE_ENV ?? "development",
    git_sha: process.env.GIT_SHA ?? "dev",
    uptime_seconds: Math.round((Date.now() - startedAtMs) / 1000),
  });
}
