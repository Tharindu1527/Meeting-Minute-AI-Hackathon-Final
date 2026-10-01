import { Check, FileText, Gavel, ListChecks, LoaderCircle, MessagesSquare, NotebookPen, ShieldCheck, Smile, Sparkles, Users, type LucideIcon } from "lucide-react";
import { AnimatePresence, motion, useMotionTemplate, useMotionValue, useReducedMotion, useSpring } from "motion/react";
import { useEffect, useState, type PointerEvent, type ReactNode } from "react";
import { cx } from "../lib/format";
import { EASE } from "../lib/motion";
import { ThemeSwitcher } from "./ThemeSwitcher";

const AGENTS: { icon: LucideIcon; label: string }[] = [
  { icon: FileText, label: "Reading the transcript" },
  { icon: Users, label: "Identifying attendees" },
  { icon: Gavel, label: "Capturing decisions" },
  { icon: ListChecks, label: "Assigning action items" },
  { icon: Sparkles, label: "Writing the summary" },
];

const FEATURES: { icon: LucideIcon; title: string; text: string }[] = [
  { icon: ShieldCheck, title: "Private by default", text: "Your meetings are visible only to your account." },
  { icon: Sparkles, title: "A crew of AI agents", text: "Gemini-powered agents split the work like a real team." },
  { icon: MessagesSquare, title: "Ask your meetings", text: "Chat answers cite who said what, and when." },
];

/** Agents finishing their steps one by one, then "Minutes ready", on a loop */
function AgentPipeline() {
  const reduced = useReducedMotion();
  const [step, setStep] = useState(reduced ? AGENTS.length : 0);
  useEffect(() => {
    if (reduced) return;
    const timer = setInterval(() => setStep((s) => (s >= AGENTS.length + 2 ? 0 : s + 1)), 1100);
    return () => clearInterval(timer);
  }, [reduced]);
  const done = Math.min(step, AGENTS.length);
  const finished = step >= AGENTS.length;

  return (
    <div className="relative rounded-2xl border border-white/15 bg-white/[0.07] p-5 shadow-[0_30px_80px_-30px_rgb(0_0_0/0.6)] backdrop-blur-xl">
      <div className="mb-4 flex items-center justify-between gap-3">
        <div>
          <div className="text-[11px] font-semibold tracking-[0.14em] text-indigo-200/80 uppercase">Live preview</div>
          <div className="mt-0.5 font-semibold">Sprint 42 retrospective</div>
        </div>
        <AnimatePresence mode="wait">
          {finished ? (
            <motion.span
              key="ready"
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.8 }}
              className="flex items-center gap-1.5 rounded-full bg-emerald-400/20 px-2.5 py-1 text-xs font-semibold text-emerald-200"
            >
              <Check className="size-3.5" /> Minutes ready
            </motion.span>
          ) : (
            <motion.span
              key="working"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="text-sm font-semibold text-indigo-100 tabular-nums"
            >
              {Math.round((done / AGENTS.length) * 100)}%
            </motion.span>
          )}
        </AnimatePresence>
      </div>
      <div className="mb-4 h-1.5 overflow-hidden rounded-full bg-white/10">
        <motion.div
          className="h-full rounded-full bg-gradient-to-r from-indigo-300 via-violet-300 to-fuchsia-300"
          animate={{ width: `${(done / AGENTS.length) * 100}%` }}
          transition={{ duration: 0.6, ease: EASE }}
        />
      </div>
      <ul className="space-y-1">
        {AGENTS.map(({ icon: Icon, label }, index) => {
          const state = index < done ? "done" : index === done && !finished ? "active" : "waiting";
          return (
            <li
              key={label}
              className={cx(
                "flex items-center gap-3 rounded-xl px-2.5 py-2 text-sm transition-colors duration-500",
                state === "active" && "bg-white/10",
                state === "waiting" && "text-white/45",
              )}
            >
              <span
                className={cx(
                  "flex size-7 shrink-0 items-center justify-center rounded-lg transition-colors duration-500",
                  state === "waiting" ? "bg-white/5" : "bg-white/15",
                )}
              >
                <Icon className="size-3.5" />
              </span>
              <span className="flex-1">{label}</span>
              <span className="flex size-5 items-center justify-center">
                {state === "done" && (
                  <motion.span
                    initial={{ scale: 0 }}
                    animate={{ scale: 1 }}
                    transition={{ type: "spring", stiffness: 500, damping: 22 }}
                    className="flex size-5 items-center justify-center rounded-full bg-emerald-400 text-indigo-950"
                  >
                    <Check className="size-3" strokeWidth={3.5} />
                  </motion.span>
                )}
                {state === "active" && <LoaderCircle className="size-4 animate-spin text-indigo-200" />}
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function FloatingChip({ icon: Icon, children, className, delay = 0 }: { icon: LucideIcon; children: ReactNode; className: string; delay?: number }) {
  const reduced = useReducedMotion();
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.85 }}
      animate={{ opacity: 1, scale: 1, y: reduced ? 0 : [0, -9, 0] }}
      transition={{
        opacity: { delay: 0.6 + delay, duration: 0.5 },
        scale: { delay: 0.6 + delay, duration: 0.5, ease: EASE },
        y: { delay: delay, duration: 4 + delay * 2, repeat: Infinity, ease: "easeInOut" },
      }}
      className={cx(
        "absolute hidden items-center gap-2 rounded-xl border border-white/15 bg-indigo-950/60 px-3 py-2 text-xs font-semibold shadow-xl backdrop-blur-md xl:flex",
        className,
      )}
    >
      <Icon className="size-3.5 text-indigo-200" />
      {children}
    </motion.div>
  );
}

/** The left half of the sign-in screens: brand, animated product preview and highlights */
function Showcase() {
  const x = useMotionValue(-500);
  const y = useMotionValue(-500);
  const smoothX = useSpring(x, { stiffness: 120, damping: 20 });
  const smoothY = useSpring(y, { stiffness: 120, damping: 20 });
  const spotlight = useMotionTemplate`radial-gradient(520px circle at ${smoothX}px ${smoothY}px, rgb(255 255 255 / 0.10), transparent 60%)`;

  const track = (event: PointerEvent<HTMLDivElement>) => {
    const rect = event.currentTarget.getBoundingClientRect();
    x.set(event.clientX - rect.left);
    y.set(event.clientY - rect.top);
  };

  return (
    <div
      onPointerMove={track}
      className="relative hidden w-[46%] shrink-0 flex-col overflow-hidden p-10 text-white lg:flex xl:w-1/2 xl:p-14"
      style={{ background: "linear-gradient(150deg, #1b1846 0%, #2e2a7c 48%, #4a1d8f 100%)" }}
    >
      {/* Grid, glows and the pointer spotlight */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 opacity-[0.15]"
        style={{
          backgroundImage: "linear-gradient(rgb(255 255 255 / 0.5) 1px, transparent 1px), linear-gradient(90deg, rgb(255 255 255 / 0.5) 1px, transparent 1px)",
          backgroundSize: "44px 44px",
          maskImage: "radial-gradient(ellipse 80% 70% at 50% 40%, black, transparent)",
        }}
      />
      <motion.div
        aria-hidden
        className="pointer-events-none absolute -top-32 -left-24 size-[460px] rounded-full bg-indigo-400/30 blur-3xl"
        animate={{ x: [0, 40, 0], y: [0, 30, 0] }}
        transition={{ duration: 14, repeat: Infinity, ease: "easeInOut" }}
      />
      <motion.div
        aria-hidden
        className="pointer-events-none absolute -right-32 bottom-0 size-[420px] rounded-full bg-fuchsia-500/25 blur-3xl"
        animate={{ x: [0, -30, 0], y: [0, -40, 0] }}
        transition={{ duration: 12, repeat: Infinity, ease: "easeInOut" }}
      />
      <motion.div aria-hidden className="pointer-events-none absolute inset-0" style={{ background: spotlight }} />

      <div className="relative flex items-center gap-2.5">
        <span className="flex size-10 items-center justify-center rounded-xl bg-white/15 ring-1 ring-white/20 backdrop-blur">
          <NotebookPen className="size-5" />
        </span>
        <div className="leading-tight">
          <div className="font-semibold tracking-tight">Meeting Minutes AI</div>
          <div className="text-xs text-indigo-200/80">AI agents · Gemini</div>
        </div>
      </div>

      <div className="relative my-auto py-10">
        <motion.h2
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: EASE, delay: 0.1 }}
          className="max-w-md text-4xl leading-[1.1] font-semibold tracking-tight xl:text-[44px]"
        >
          Meetings in.
          <br />
          <span className="bg-gradient-to-r from-indigo-200 via-violet-200 to-fuchsia-200 bg-clip-text text-transparent">Minutes out.</span>
        </motion.h2>
        <motion.p
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: EASE, delay: 0.2 }}
          className="mt-4 max-w-md text-[15px] leading-relaxed text-indigo-100/80"
        >
          Drop in a recording or transcript. A team of AI agents writes the summary, decisions and action items for you.
        </motion.p>

        <motion.div
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, ease: EASE, delay: 0.35 }}
          className="relative mt-10 max-w-md"
        >
          <AgentPipeline />
          <FloatingChip icon={Gavel} className="-top-5 -right-14" delay={0}>
            3 decisions
          </FloatingChip>
          <FloatingChip icon={ListChecks} className="top-1/2 -right-32" delay={0.4}>
            4 action items
          </FloatingChip>
          <FloatingChip icon={Smile} className="-bottom-5 -left-10" delay={0.8}>
            Tone · Collaborative
          </FloatingChip>
        </motion.div>
      </div>

      <ul className="relative grid grid-cols-3 gap-5">
        {FEATURES.map(({ icon: Icon, title, text }, index) => (
          <motion.li
            key={title}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, ease: EASE, delay: 0.5 + index * 0.08 }}
          >
            <Icon className="size-[18px] text-indigo-200" />
            <div className="mt-2 text-sm font-semibold">{title}</div>
            <div className="mt-0.5 text-xs leading-relaxed text-indigo-100/70">{text}</div>
          </motion.li>
        ))}
      </ul>
    </div>
  );
}

/** Split screen for sign-in, sign-up and password reset: showcase on the left (wide screens), form on the right */
export function AuthShell({ children, screenKey }: { children: ReactNode; screenKey: string }) {
  return (
    <div className="flex min-h-screen">
      <Showcase />
      <div className="relative flex min-w-0 flex-1 flex-col overflow-hidden">
        <div aria-hidden className="pointer-events-none absolute -top-40 -right-40 size-[480px] rounded-full bg-brand/10 blur-3xl" />
        <header className="relative flex items-center justify-between gap-3 p-5 sm:p-6">
          <div className="flex items-center gap-2.5 lg:invisible">
            <span className="flex size-9 items-center justify-center rounded-xl bg-brand-gradient text-white shadow-glow">
              <NotebookPen className="size-[18px]" />
            </span>
            <span className="text-[15px] font-semibold tracking-tight">Meeting Minutes AI</span>
          </div>
          <ThemeSwitcher />
        </header>
        <main className="relative flex flex-1 items-center justify-center px-5 pt-4 pb-14 sm:px-8">
          <AnimatePresence mode="wait" initial={false}>
            <motion.div
              key={screenKey}
              initial={{ opacity: 0, x: 18 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -18, transition: { duration: 0.15 } }}
              transition={{ duration: 0.35, ease: EASE }}
              className="w-full max-w-[400px]"
            >
              {children}
            </motion.div>
          </AnimatePresence>
        </main>
      </div>
    </div>
  );
}
