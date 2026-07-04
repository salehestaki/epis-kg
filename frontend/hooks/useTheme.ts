"use client";

import { useCallback, useEffect, useState } from "react";

export type Theme = "light" | "dark";

function currentTheme(): Theme {
  if (typeof document === "undefined") return "light";
  return document.documentElement.classList.contains("dark") ? "dark" : "light";
}

/** Read/toggle the theme. Initial value is set pre-paint by the inline script
 * in the root layout, so there is no flash of the wrong theme. */
export function useTheme(): { theme: Theme; toggle: () => void } {
  const [theme, setTheme] = useState<Theme>("light");

  useEffect(() => {
    setTheme(currentTheme());
  }, []);

  const toggle = useCallback(() => {
    const next: Theme = currentTheme() === "dark" ? "light" : "dark";
    const root = document.documentElement;
    root.classList.toggle("dark", next === "dark");
    try {
      localStorage.setItem("epis-theme", next);
    } catch {
      /* ignore */
    }
    setTheme(next);
  }, []);

  return { theme, toggle };
}
