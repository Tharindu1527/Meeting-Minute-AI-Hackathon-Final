import { Monitor, Moon, Sun, type LucideIcon } from "lucide-react";
import { motion } from "motion/react";
import { useId } from "react";
import { cx } from "../lib/format";
import { useTheme, type ThemeChoice } from "../lib/theme";

const OPTIONS: { value: ThemeChoice; label: string; icon: LucideIcon }[] = [
  { value: "light", label: "Light", icon: Sun },
  { value: "system", label: "System", icon: Monitor },
  { value: "dark", label: "Dark", icon: Moon },
];

/** Light / System / Dark segmented control; `labels` shows the words next to the icons */
export function ThemeSwitcher({ labels = false, className }: { labels?: boolean; className?: string }) {
  const { choice, setChoice } = useTheme();
  const pillId = useId();
  return (
    <div role="radiogroup" aria-label="Theme" className={cx("inline-flex rounded-xl border border-line bg-sunken/70 p-1", labels && "w-full", className)}>
      {OPTIONS.map(({ value, label, icon: Icon }) => {
        const active = choice === value;
        return (
          <button
            key={value}
            type="button"
            role="radio"
            aria-checked={active}
            aria-label={labels ? undefined : `${label} theme`}
            title={labels ? undefined : label}
            onClick={(event) => setChoice(value, { x: event.clientX, y: event.clientY })}
            className={cx(
              "relative flex items-center justify-center gap-1.5 rounded-lg text-xs font-medium transition-colors duration-200",
              labels ? "h-8 flex-1 px-2.5" : "size-8",
              active ? "text-ink" : "text-subtle hover:text-ink",
            )}
          >
            {active && (
              <motion.span
                layoutId={pillId}
                className="absolute inset-0 rounded-lg bg-card shadow-card ring-1 ring-line"
                transition={{ type: "spring", stiffness: 500, damping: 38 }}
              />
            )}
            <Icon className={cx("relative size-3.5 transition-transform duration-300", active && "scale-110 text-brand")} />
            {labels && <span className="relative">{label}</span>}
          </button>
        );
      })}
    </div>
  );
}
