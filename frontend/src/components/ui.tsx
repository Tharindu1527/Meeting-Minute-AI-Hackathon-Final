import { CircleAlert, CircleCheck, Info, LoaderCircle, TriangleAlert, type LucideIcon } from "lucide-react";
import { motion } from "motion/react";
import type { ComponentProps, ReactNode } from "react";
import { cx } from "../lib/format";
import { AnimatedNumber, EASE } from "../lib/motion";

type Variant = "primary" | "secondary" | "ghost" | "danger";

const VARIANTS: Record<Variant, string> = {
  primary: "bg-brand-gradient text-white shadow-glow hover:brightness-110 dark:text-brand-ink",
  secondary: "bg-card text-ink border border-line shadow-card hover:bg-sunken hover:border-brand/30",
  ghost: "text-subtle hover:text-ink hover:bg-sunken",
  danger: "bg-bad text-white shadow-[0_10px_24px_-12px_var(--bad)] hover:brightness-110",
};

export function Button({
  variant = "secondary",
  size = "md",
  icon: Icon,
  loading = false,
  className,
  children,
  disabled,
  ...props
}: ComponentProps<"button"> & {
  variant?: Variant;
  size?: "sm" | "md" | "lg";
  icon?: LucideIcon;
  loading?: boolean;
}) {
  return (
    <button
      type="button"
      disabled={disabled || loading}
      className={cx(
        "inline-flex items-center justify-center gap-2 rounded-xl font-medium whitespace-nowrap",
        "transition-all duration-200 ease-out active:scale-[0.97]",
        "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand",
        "disabled:pointer-events-none disabled:opacity-50",
        size === "sm" ? "h-8 px-3 text-sm" : size === "lg" ? "h-12 px-6 text-[15px]" : "h-10 px-4 text-sm",
        VARIANTS[variant],
        className,
      )}
      {...props}
    >
      {loading ? <LoaderCircle className="size-4 animate-spin" /> : Icon && <Icon className="size-4" />}
      {children}
    </button>
  );
}

export function Card({
  title,
  description,
  icon: Icon,
  actions,
  children,
  className,
}: {
  title?: ReactNode;
  description?: ReactNode;
  icon?: LucideIcon;
  actions?: ReactNode;
  children?: ReactNode;
  className?: string;
}) {
  return (
    <section className={cx("rounded-2xl border border-line bg-card p-5 shadow-card sm:p-6", className)}>
      {(title || actions) && (
        <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
          <div className="flex min-w-0 items-start gap-3">
            {Icon && <IconTile icon={Icon} />}
            <div className="min-w-0">
              {title && <h2 className="text-[15px] font-semibold tracking-tight">{title}</h2>}
              {description && <p className="mt-0.5 text-sm text-subtle">{description}</p>}
            </div>
          </div>
          {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
        </div>
      )}
      {children}
    </section>
  );
}

/** Small tinted square with an icon, used in card headers and stats */
export function IconTile({ icon: Icon, tone = "brand", size = "md" }: { icon: LucideIcon; tone?: Tone; size?: "md" | "lg" }) {
  return (
    <span className={cx("inline-flex shrink-0 items-center justify-center rounded-xl", size === "lg" ? "size-11" : "size-9", TONES[tone])}>
      <Icon className={size === "lg" ? "size-5" : "size-[18px]"} />
    </span>
  );
}

type Tone = "neutral" | "brand" | "good" | "warn" | "bad";

const TONES: Record<Tone, string> = {
  neutral: "bg-sunken text-subtle",
  brand: "bg-brand-soft text-brand",
  good: "bg-good-soft text-good",
  warn: "bg-warn-soft text-warn",
  bad: "bg-bad-soft text-bad",
};

const DOTS: Record<Tone, string> = {
  neutral: "bg-subtle",
  brand: "bg-brand",
  good: "bg-good",
  warn: "bg-warn",
  bad: "bg-bad",
};

export function Badge({ tone = "neutral", dot = false, children }: { tone?: Tone; dot?: boolean; children: ReactNode }) {
  return (
    <span className={cx("inline-flex max-w-full items-center gap-1.5 overflow-hidden rounded-full px-2.5 py-0.5 text-xs font-medium whitespace-nowrap", TONES[tone])}>
      {dot && <span className={cx("size-1.5 shrink-0 rounded-full", DOTS[tone])} />}
      {children}
    </span>
  );
}

export const PRIORITY_TONE: Record<string, Tone> = { High: "bad", Medium: "warn", Low: "neutral" };
export const STATUS_TONE: Record<string, Tone> = { Open: "brand", "In progress": "warn", Done: "good" };
export const CLAIM_TONE: Record<string, Tone> = {
  Verified: "good",
  "Partially verified": "warn",
  Refuted: "bad",
  Unverifiable: "neutral",
};

export const inputClass =
  "w-full rounded-xl border border-line bg-card px-3.5 py-2.5 text-sm text-ink shadow-[inset_0_1px_1px_rgb(0_0_0/0.02)] " +
  "placeholder:text-subtle/60 transition duration-200 hover:border-brand/30 " +
  "focus:border-brand focus:outline-none focus:ring-4 focus:ring-brand/12 disabled:opacity-60";

export function Field({ label, hint, children, className }: { label: ReactNode; hint?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <label className={cx("block", className)}>
      <span className="mb-1.5 block text-sm font-medium">{label}</span>
      {children}
      {hint && <span className="mt-1.5 block text-xs text-subtle">{hint}</span>}
    </label>
  );
}

const ALERTS: Record<"error" | "warning" | "info" | "success", { icon: LucideIcon; className: string }> = {
  error: { icon: CircleAlert, className: "bg-bad-soft text-bad border-bad/20" },
  warning: { icon: TriangleAlert, className: "bg-warn-soft text-warn border-warn/20" },
  info: { icon: Info, className: "bg-brand-soft text-brand border-brand/20" },
  success: { icon: CircleCheck, className: "bg-good-soft text-good border-good/20" },
};

export function Alert({ tone = "info", children, className }: { tone?: keyof typeof ALERTS; children: ReactNode; className?: string }) {
  const { icon: Icon, className: toneClass } = ALERTS[tone];
  return (
    <motion.div
      role={tone === "error" ? "alert" : "status"}
      initial={{ opacity: 0, y: -4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25, ease: EASE }}
      className={cx("flex gap-2.5 rounded-xl border px-3.5 py-3 text-sm", toneClass, className)}
    >
      <Icon className="mt-0.5 size-4 shrink-0" />
      <div className="min-w-0 break-words">{children}</div>
    </motion.div>
  );
}

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 text-sm text-subtle">
      <LoaderCircle className="size-4 animate-spin text-brand" />
      {label}
    </div>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden className={cx("skeleton", className)} />;
}

export function EmptyState({ icon: Icon, title, children }: { icon: LucideIcon; title: string; children?: ReactNode }) {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.98 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.4, ease: EASE }}
      className="relative flex flex-col items-center overflow-hidden rounded-2xl border border-dashed border-line bg-card/70 px-6 py-14 text-center"
    >
      <div className="pointer-events-none absolute inset-x-0 -top-24 mx-auto size-64 rounded-full bg-brand/10 blur-3xl" />
      <div className="relative mb-4 rounded-2xl bg-brand-gradient p-3.5 text-white shadow-glow">
        <Icon className="size-6" />
      </div>
      <h3 className="relative text-base font-semibold">{title}</h3>
      {children && <div className="relative mt-1.5 max-w-md text-sm text-subtle">{children}</div>}
    </motion.div>
  );
}

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow?: string;
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: EASE }}
      className="mb-7 flex flex-wrap items-end justify-between gap-4"
    >
      <div className="min-w-0">
        {eyebrow && <div className="mb-1.5 text-xs font-semibold tracking-[0.14em] text-brand uppercase">{eyebrow}</div>}
        <h1 className="text-[26px] leading-tight font-semibold tracking-tight sm:text-3xl">{title}</h1>
        {description && <p className="mt-1.5 max-w-2xl text-[15px] text-subtle">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </motion.div>
  );
}

export function Stat({ label, value, icon, tone = "brand" }: { label: string; value: number; icon: LucideIcon; tone?: Tone }) {
  return (
    <div className="group flex items-center gap-3.5 rounded-2xl border border-line bg-card p-4 shadow-card transition duration-300 hover:-translate-y-0.5 hover:shadow-lift">
      <IconTile icon={icon} tone={tone} size="lg" />
      <div>
        <div className="text-2xl leading-none font-semibold tabular-nums">
          <AnimatedNumber value={value} />
        </div>
        <div className="mt-1 text-xs font-medium text-subtle">{label}</div>
      </div>
    </div>
  );
}
