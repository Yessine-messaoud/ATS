"use client";

import { useEffect, useState } from "react";
import { Laptop, Moon, Sun } from "lucide-react";

import { Menu } from "./interactive";
import { cx } from "./ui";

export type Theme = "light" | "dark" | "system";
const KEY = "theme";

/** Runs before the first paint (inlined in <head>) so the page never flashes the wrong theme. */
export const THEME_SCRIPT = `try{var t=localStorage.getItem("${KEY}");var d=t==="dark"||(t!=="light"&&matchMedia("(prefers-color-scheme: dark)").matches);document.documentElement.classList.toggle("dark",d)}catch(e){}`;

function apply(theme: Theme) {
  const dark = theme === "dark" || (theme === "system" && window.matchMedia("(prefers-color-scheme: dark)").matches);
  document.documentElement.classList.toggle("dark", dark);
}

function stored(): Theme {
  try {
    const value = localStorage.getItem(KEY);
    return value === "light" || value === "dark" ? value : "system";
  } catch {
    return "system";
  }
}

export function useTheme(): [Theme, (theme: Theme) => void] {
  const [theme, setThemeState] = useState<Theme>("system");
  useEffect(() => {
    const initial = stored();
    // Read the saved choice after hydration (the server cannot know it).
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setThemeState(initial);
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const follow = () => stored() === "system" && apply("system");
    media.addEventListener("change", follow);
    return () => media.removeEventListener("change", follow);
  }, []);
  const setTheme = (next: Theme) => {
    try {
      if (next === "system") localStorage.removeItem(KEY);
      else localStorage.setItem(KEY, next);
    } catch {
      // storage unavailable: the choice lasts for this page only
    }
    apply(next);
    setThemeState(next);
  };
  return [theme, setTheme];
}

const OPTIONS = [
  { value: "light" as const, label: "Light", icon: <Sun /> },
  { value: "dark" as const, label: "Dark", icon: <Moon /> },
  { value: "system" as const, label: "System", icon: <Laptop /> },
];

export function ThemeSwitcher({ className }: { className?: string }) {
  const [theme, setTheme] = useTheme();
  const Icon = theme === "dark" ? Moon : theme === "light" ? Sun : Laptop;
  return (
    <Menu
      label={`Theme: ${theme}`}
      className={className}
      trigger={
        <span className="flex size-9 items-center justify-center rounded-lg text-zinc-500 hover:bg-zinc-100 hover:text-zinc-900 dark:hover:bg-zinc-800 dark:hover:text-zinc-100">
          <Icon className="size-4" />
        </span>
      }
      items={OPTIONS.map((option) => ({
        label: option.value === theme ? `${option.label} ✓` : option.label,
        icon: option.icon,
        onSelect: () => setTheme(option.value),
      }))}
    />
  );
}

export function ThemeSegmented() {
  const [theme, setTheme] = useTheme();
  return (
    <div role="radiogroup" aria-label="Theme" className="inline-flex rounded-lg border border-zinc-200 bg-white p-0.5 dark:border-zinc-800 dark:bg-zinc-900">
      {OPTIONS.map((option) => (
        <button
          key={option.value}
          type="button"
          role="radio"
          aria-checked={theme === option.value}
          onClick={() => setTheme(option.value)}
          className={cx(
            "flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm [&>svg]:size-4",
            theme === option.value ? "bg-brand-50 font-medium text-brand-700 dark:bg-brand-950 dark:text-brand-300" : "text-zinc-500",
          )}
        >
          {option.icon}
          {option.label}
        </button>
      ))}
    </div>
  );
}
