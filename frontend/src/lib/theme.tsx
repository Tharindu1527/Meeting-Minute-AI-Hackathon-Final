import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { flushSync } from "react-dom";

export type ThemeChoice = "light" | "dark" | "system";
type Resolved = "light" | "dark";

// index.html reads the same key before the app loads, so the page never flashes the wrong theme
const THEME_KEY = "meeting-minutes-theme";

function systemTheme(): Resolved {
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function savedChoice(): ThemeChoice {
  try {
    const saved = localStorage.getItem(THEME_KEY);
    if (saved === "light" || saved === "dark" || saved === "system") return saved;
  } catch {
    // Storage unavailable: follow the system
  }
  return "system";
}

function apply(resolved: Resolved) {
  document.documentElement.dataset.theme = resolved;
}

interface ThemeValue {
  choice: ThemeChoice;
  resolved: Resolved;
  /** Change the theme; pass the click position for a circular reveal from that point */
  setChoice: (choice: ThemeChoice, origin?: { x: number; y: number }) => void;
}

const ThemeContext = createContext<ThemeValue>({ choice: "system", resolved: "light", setChoice: () => {} });

export const useTheme = () => useContext(ThemeContext);

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [choice, setChoiceState] = useState<ThemeChoice>(savedChoice);
  const [system, setSystem] = useState<Resolved>(systemTheme);
  const resolved = choice === "system" ? system : choice;

  useEffect(() => {
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const update = () => setSystem(media.matches ? "dark" : "light");
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);

  useEffect(() => apply(resolved), [resolved]);

  const setChoice = useCallback(
    (next: ThemeChoice, origin?: { x: number; y: number }) => {
      try {
        localStorage.setItem(THEME_KEY, next);
      } catch {
        // Not remembered across visits; the choice still applies now
      }
      const nextResolved = next === "system" ? systemTheme() : next;
      const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      if (!origin || reduced || nextResolved === resolved || !document.startViewTransition) {
        setChoiceState(next);
        return;
      }
      // Reveal the new theme in a growing circle from where the user clicked
      let applied = false;
      const update = () => {
        if (applied) return;
        applied = true;
        flushSync(() => setChoiceState(next));
        apply(nextResolved);
      };
      const transition = document.startViewTransition(update);
      // The transition waits for a rendered frame, which never comes in a background tab: switch anyway
      window.setTimeout(update, 300);
      const radius = Math.hypot(Math.max(origin.x, innerWidth - origin.x), Math.max(origin.y, innerHeight - origin.y));
      transition.ready
        .then(() =>
          document.documentElement.animate(
            { clipPath: [`circle(0px at ${origin.x}px ${origin.y}px)`, `circle(${radius}px at ${origin.x}px ${origin.y}px)`] },
            { duration: 550, easing: "cubic-bezier(0.22, 1, 0.36, 1)", pseudoElement: "::view-transition-new(root)" },
          ),
        )
        .catch(() => {});
    },
    [resolved],
  );

  return <ThemeContext.Provider value={{ choice, resolved, setChoice }}>{children}</ThemeContext.Provider>;
}
