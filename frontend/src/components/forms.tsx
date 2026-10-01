import { ArrowBigUp, Check, Eye, EyeOff, LockKeyhole, type LucideIcon } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useId, useState, type ComponentProps, type KeyboardEvent, type ReactNode } from "react";
import { cx } from "../lib/format";
import { EASE } from "../lib/motion";
import { inputClass } from "./ui";

/** Text input with a leading icon that lights up while the field has focus */
export function IconInput({ icon: Icon, className, ...props }: ComponentProps<"input"> & { icon: LucideIcon }) {
  return (
    <span className="group relative block">
      <Icon className="pointer-events-none absolute top-1/2 left-3.5 size-[18px] -translate-y-1/2 text-subtle transition-colors duration-200 group-focus-within:text-brand" />
      <input className={cx(inputClass, "h-11 pl-11", className)} {...props} />
    </span>
  );
}

/** Label + control + optional hint, with an action (e.g. "Forgot password?") beside the label */
export function FormField({ label, htmlFor, action, hint, children }: { label: ReactNode; htmlFor: string; action?: ReactNode; hint?: ReactNode; children: ReactNode }) {
  return (
    <div>
      <div className="mb-1.5 flex items-center justify-between gap-3">
        <label htmlFor={htmlFor} className="text-sm font-medium">
          {label}
        </label>
        {action}
      </div>
      {children}
      {hint && <div className="mt-1.5 text-xs text-subtle">{hint}</div>}
    </div>
  );
}

const COMMON = ["password", "12345678", "qwerty", "letmein", "welcome", "iloveyou", "admin123", "abc12345"];

/** 0 (empty) to 4 (strong), with the checks behind it; the server only insists on 8+ characters */
export function passwordStrength(password: string) {
  const checks = {
    length: password.length >= 8,
    cases: /[a-z]/.test(password) && /[A-Z]/.test(password),
    number: /\d/.test(password),
    symbol: /[^A-Za-z0-9]/.test(password),
  };
  if (!password) return { score: 0, checks };
  let score = Number(checks.length) + Number(checks.cases) + Number(checks.number) + Number(checks.symbol);
  if (password.length >= 14) score += 1;
  if (!checks.length || COMMON.some((word) => password.toLowerCase().includes(word)) || new Set(password).size < 4) score = 1;
  return { score: Math.max(1, Math.min(4, score)), checks };
}

const STRENGTH = [
  { label: "", bar: "bg-line", text: "text-subtle" },
  { label: "Weak", bar: "bg-bad", text: "text-bad" },
  { label: "Fair", bar: "bg-warn", text: "text-warn" },
  { label: "Good", bar: "bg-brand", text: "text-brand" },
  { label: "Strong", bar: "bg-good", text: "text-good" },
];

function StrengthMeter({ password }: { password: string }) {
  const { score, checks } = passwordStrength(password);
  const style = STRENGTH[score];
  const tips: [boolean, string][] = [
    [checks.length, "8+ characters"],
    [checks.cases, "Upper & lower case"],
    [checks.number, "A number"],
    [checks.symbol, "A symbol"],
  ];
  return (
    <div className="mt-2.5" aria-live="polite">
      <div className="flex items-center gap-2.5">
        <div className="flex flex-1 gap-1.5">
          {[1, 2, 3, 4].map((segment) => (
            <div key={segment} className="h-1.5 flex-1 overflow-hidden rounded-full bg-sunken">
              <motion.div
                className={cx("h-full rounded-full", style.bar)}
                initial={false}
                animate={{ width: score >= segment ? "100%" : "0%" }}
                transition={{ duration: 0.35, ease: EASE, delay: (segment - 1) * 0.04 }}
              />
            </div>
          ))}
        </div>
        <span className={cx("w-12 text-right text-xs font-semibold", style.text)}>{style.label}</span>
      </div>
      <ul className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1">
        {tips.map(([met, label]) => (
          <li key={label} className={cx("flex items-center gap-1.5 text-xs transition-colors duration-200", met ? "text-good" : "text-subtle")}>
            <span className={cx("flex size-3.5 items-center justify-center rounded-full border transition-colors duration-200", met ? "border-good bg-good text-white dark:text-canvas" : "border-line")}>
              <AnimatePresence>
                {met && (
                  <motion.span initial={{ scale: 0 }} animate={{ scale: 1 }} exit={{ scale: 0 }} transition={{ type: "spring", stiffness: 500, damping: 25 }}>
                    <Check className="size-2.5" strokeWidth={3.5} />
                  </motion.span>
                )}
              </AnimatePresence>
            </span>
            {label}
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Password input with show/hide, a Caps Lock warning and (for new passwords) a strength meter */
export function PasswordInput({
  value,
  onChange,
  showStrength = false,
  className,
  ...props
}: Omit<ComponentProps<"input">, "onChange" | "value" | "type"> & { value: string; onChange: (value: string) => void; showStrength?: boolean }) {
  const [visible, setVisible] = useState(false);
  const [capsLock, setCapsLock] = useState(false);
  const capsId = useId();
  const detectCaps = (event: KeyboardEvent<HTMLInputElement>) => setCapsLock(event.getModifierState?.("CapsLock") ?? false);
  return (
    <div>
      <span className="group relative block">
        <LockKeyhole className="pointer-events-none absolute top-1/2 left-3.5 size-[18px] -translate-y-1/2 text-subtle transition-colors duration-200 group-focus-within:text-brand" />
        <input
          type={visible ? "text" : "password"}
          className={cx(inputClass, "h-11 pr-11 pl-11", className)}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={detectCaps}
          onKeyUp={detectCaps}
          onBlur={() => setCapsLock(false)}
          aria-describedby={capsLock ? capsId : undefined}
          {...props}
        />
        <button
          type="button"
          onClick={() => setVisible(!visible)}
          aria-label={visible ? "Hide password" : "Show password"}
          aria-pressed={visible}
          className="absolute inset-y-0 right-0 flex w-11 items-center justify-center text-subtle transition hover:text-ink"
        >
          <AnimatePresence mode="wait" initial={false}>
            <motion.span
              key={visible ? "hide" : "show"}
              initial={{ opacity: 0, rotate: -40, scale: 0.6 }}
              animate={{ opacity: 1, rotate: 0, scale: 1 }}
              exit={{ opacity: 0, rotate: 40, scale: 0.6 }}
              transition={{ duration: 0.15 }}
            >
              {visible ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
            </motion.span>
          </AnimatePresence>
        </button>
      </span>
      <AnimatePresence>
        {capsLock && (
          <motion.div
            id={capsId}
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="overflow-hidden"
          >
            <div className="mt-1.5 flex items-center gap-1.5 text-xs font-medium text-warn">
              <ArrowBigUp className="size-3.5" /> Caps Lock is on
            </div>
          </motion.div>
        )}
      </AnimatePresence>
      {showStrength && value && <StrengthMeter password={value} />}
    </div>
  );
}

/** Checkbox with an animated tick */
export function Checkbox({ checked, onChange, children }: { checked: boolean; onChange: (checked: boolean) => void; children: ReactNode }) {
  return (
    <label className="group flex cursor-pointer items-center gap-2.5 text-sm select-none">
      <input type="checkbox" className="peer sr-only" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      <span
        className={cx(
          "flex size-[18px] shrink-0 items-center justify-center rounded-md border transition duration-200",
          "peer-focus-visible:ring-4 peer-focus-visible:ring-brand/20",
          checked ? "border-transparent bg-brand-gradient text-white shadow-glow dark:text-brand-ink" : "border-line bg-card group-hover:border-brand/40",
        )}
      >
        <motion.svg viewBox="0 0 16 16" className="size-3" fill="none" stroke="currentColor" strokeWidth={2.6} strokeLinecap="round" strokeLinejoin="round">
          <motion.path d="M3.5 8.5 6.5 11.5 12.5 4.5" initial={false} animate={{ pathLength: checked ? 1 : 0 }} transition={{ duration: 0.25, ease: EASE }} />
        </motion.svg>
      </span>
      <span className="text-subtle transition-colors group-hover:text-ink">{children}</span>
    </label>
  );
}
