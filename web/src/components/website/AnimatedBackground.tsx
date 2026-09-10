import type { ReactNode } from "react";
import fs from "node:fs";
import path from "node:path";

const rawSvg = fs.readFileSync(path.join(process.cwd(), "public/back-prup.svg"), "utf8");

function buildMosaic(svg: string): string {
  const defsMatch = svg.match(/<defs[\s\S]*?<\/defs>/);
  const defsHtml = defsMatch ? defsMatch[0] : "";

  const gStart = svg.indexOf("<g");
  const gEnd = svg.lastIndexOf("</g>");
  const gHtml = gStart !== -1 && gEnd > gStart ? svg.slice(gStart, gEnd + 5) : "";

  return `${defsHtml}${gHtml}`;
}

const mosaicHtml = buildMosaic(rawSvg);

export default function AnimatedBackground({ children }: { children: ReactNode }) {
  return (
    <>
      <div className="fixed inset-0 overflow-hidden bg-[#572466]" aria-hidden="true">
        <svg
          viewBox="0 0 677.33331 380.99997"
          preserveAspectRatio="xMidYMid slice"
          className="h-full w-full"
          dangerouslySetInnerHTML={{ __html: mosaicHtml }}
        />
        <div className="absolute inset-0 bg-black/80" />
      </div>
      <div className="relative z-10">{children}</div>
    </>
  );
}
