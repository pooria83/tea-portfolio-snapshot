"use client";

import { useEffect } from "react";

const overlayStack: string[] = [];

export function useCloseOnBack(open: boolean, onClose: () => void, id: string) {
  useEffect(() => {
    if (!open) {
      return;
    }

    const previousUrl = window.location.href;
    overlayStack.push(id);
    window.history.pushState({ overlayId: id }, "");

    const handlePopState = () => {
      if (overlayStack.at(-1) === id) {
        overlayStack.pop();
        onClose();
      }
    };

    window.addEventListener("popstate", handlePopState);

    return () => {
      window.removeEventListener("popstate", handlePopState);
      const index = overlayStack.indexOf(id);
      if (index !== -1) {
        overlayStack.splice(index, 1);
      }
      if (window.history.state?.overlayId === id) {
        window.history.replaceState({}, "", previousUrl);
      }
    };
  }, [open, onClose, id]);
}
