"use client";

import {
  createContext,
  useContext,
  useState,
  useCallback,
  useEffect,
} from "react";

export type Theme = "light" | "dark";

interface ThemeContextValue {
  theme: Theme;
  setTheme: (t: Theme) => void;
  toggleTheme: () => void;
}

const ThemeContext = createContext<ThemeContextValue>({
  theme: "light",
  setTheme: () => {},
  toggleTheme: () => {},
});

export const useTheme = () => useContext(ThemeContext);

const STORAGE_KEY = "ai-customer-theme";

function readStored(): Theme {
  if (typeof window === "undefined") return "light";

  const v = localStorage.getItem(STORAGE_KEY);

  if (v === "dark") return "dark";
  if (v === "light") return "light";

  localStorage.setItem(STORAGE_KEY, "light");
  return "light";
}

function applyToDOM(theme: Theme) {
  const root = document.documentElement;

  if (theme === "dark") {
    root.classList.add("dark");
    root.style.colorScheme = "dark";
  } else {
    root.classList.remove("dark");
    root.style.colorScheme = "light";
  }
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(() => {
    if (typeof window === "undefined") return "light";

    return document.documentElement.classList.contains("dark")
      ? "dark"
      : "light";
  });

  const setTheme = useCallback((t: Theme) => {
    applyToDOM(t);
    localStorage.setItem(STORAGE_KEY, t);
    setThemeState(t);
  }, []);

  const toggleTheme = useCallback(() => {
    document.documentElement.classList.add("theme-switching");

    setThemeState((prev) => {
      const next = prev === "dark" ? "light" : "dark";

      applyToDOM(next);
      localStorage.setItem(STORAGE_KEY, next);

      return next;
    });

    requestAnimationFrame(() => {
      document.documentElement.classList.remove("theme-switching");
    });
  }, []);

  return (
    <ThemeContext.Provider value={{ theme, setTheme, toggleTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}
