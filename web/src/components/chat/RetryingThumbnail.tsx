"use client";

import { ImageIcon } from "lucide-react";
import Image from "next/image";
import { memo, useCallback, useState } from "react";

export function normalizeSrc(
  src: string,
  hostname = typeof window === "undefined" ? "" : window.location.hostname,
): string {
  if (hostname === "portfolio.example.invalid" && src.startsWith("https://portfolio.example.invalid/")) {
    return src.replace("portfolio.example.invalid", "portfolio.example.invalid");
  }
  return src;
}

export const RetryingThumbnail = memo(function RetryingThumbnail({
  src,
  alt,
}: {
  src: string;
  alt: string;
}) {
  const [failed, setFailed] = useState(false);

  const handleError = useCallback(() => {
    setFailed(true);
  }, []);

  if (failed) {
    return (
      <div className="text-muted-foreground grid size-full place-items-center" title={alt}>
        <ImageIcon className="size-5" aria-hidden />
      </div>
    );
  }

  return (
    <Image
      src={normalizeSrc(src)}
      alt={alt}
      width={512}
      height={512}
      sizes="(max-width: 640px) 45vw, 288px"
      className="size-full object-cover"
      onError={handleError}
    />
  );
});
