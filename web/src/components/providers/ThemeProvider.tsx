"use client";

import { useSyncExternalStore, createContext, useContext, useEffect, type ReactNode } from "react";

type Theme = "dark" | "light";

interface ThemeContextValue {
  theme: Theme;
  setTheme: (theme: Theme) => void;
}

const ThemeContext = createContext<ThemeContextValue>({
  theme: "dark",
  setTheme: () => {},
});

export function useTheme() {
  return useContext(ThemeContext);
}

function getSnapshot(): Theme {
  if (typeof document === "undefined") return "dark";
  if (document.documentElement.classList.contains("light")) return "light";
  return "dark";
}

function subscribe(callback: () => void): () => void {
  const observer = new MutationObserver(callback);
  observer.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
  return () => observer.disconnect();
}

interface ThemeProviderProps {
  children: ReactNode;
  defaultTheme?: Theme;
}

export function ThemeProvider({ children }: ThemeProviderProps) {
  const theme = useSyncExternalStore(subscribe, getSnapshot, () => "dark" as Theme);

  useEffect(() => {
    try {
      const stored = localStorage.getItem("theme");
      if (
        (stored === "dark" || stored === "light") &&
        !document.documentElement.classList.contains(stored)
      ) {
        document.documentElement.classList.remove("dark", "light");
        document.documentElement.classList.add(stored);
      }
    } catch (error) {
      console.warn("Failed to restore theme from localStorage:", error);
    }
  }, []);

  const setTheme = (newTheme: Theme) => {
    try {
      localStorage.setItem("theme", newTheme);
    } catch {
      console.warn("Failed to persist theme preference to localStorage");
    }
    document.documentElement.classList.remove("dark", "light");
    document.documentElement.classList.add(newTheme);
  };

  return <ThemeContext.Provider value={{ theme, setTheme }}>{children}</ThemeContext.Provider>;
}
