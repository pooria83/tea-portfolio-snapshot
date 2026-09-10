"use client";

import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { ArrowUpIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useIsMobile } from "@/hooks/use-mobile";

const SCROLL_THRESHOLD = 200;

export function ScrollToTop() {
  const t = useTranslations("common");
  const isMobile = useIsMobile();
  const [visible, setVisible] = useState(false);
  const [target, setTarget] = useState<Element | null>(null);
  const rafRef = useRef<number | null>(null);

  useEffect(() => {
    const update = (scrolledElement: unknown) => {
      const scrollTop =
        scrolledElement instanceof Element
          ? scrolledElement.scrollTop
          : window.scrollY || document.documentElement.scrollTop || 0;
      setVisible(scrollTop > SCROLL_THRESHOLD);
      setTarget(scrolledElement instanceof Element ? scrolledElement : null);
    };

    const handleScroll = (event: Event) => {
      const scrolledElement = event.target;
      if (rafRef.current !== null) {
        return;
      }
      rafRef.current = requestAnimationFrame(() => {
        rafRef.current = null;
        update(scrolledElement);
      });
    };

    window.addEventListener("scroll", handleScroll, { capture: true });
    update(window);
    return () => {
      if (rafRef.current !== null) {
        cancelAnimationFrame(rafRef.current);
        rafRef.current = null;
      }
      window.removeEventListener("scroll", handleScroll, { capture: true });
    };
  }, []);

  const scrollToTop = () => {
    if (target && target.scrollTop > 0) {
      target.scrollTo({ top: 0, behavior: "smooth" });
    } else {
      window.scrollTo({ top: 0, behavior: "smooth" });
    }
  };

  if (!visible || isMobile) {
    return null;
  }

  return (
    <Button
      variant="secondary"
      size="icon-lg"
      className="fixed end-4 bottom-4 z-50 shadow-lg"
      aria-label={t("scrollToTop")}
      onClick={scrollToTop}
    >
      <ArrowUpIcon />
    </Button>
  );
}
