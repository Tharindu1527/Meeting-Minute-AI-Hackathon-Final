import { Check, CircleAlert, Sparkles } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { cx } from "../lib/format";
import { EASE } from "../lib/motion";
import type { Job } from "../lib/types";
import { Alert } from "./ui";

/** Live view of a background job: progress bar, completed steps and any error */
export function JobProgress<T>({ job, title }: { job: Job<T> | undefined; title: string }) {
  const running = !job || job.status === "running";
  const failed = job?.status === "error";
  const percent = job?.total ? Math.round((job.done / job.total) * 100) : null;

  return (
    <div className="relative overflow-hidden rounded-2xl border border-line bg-card p-6 shadow-card" aria-live="polite">
      {running && <div className="pointer-events-none absolute -top-20 -right-20 size-56 rounded-full bg-brand/10 blur-3xl" />}

      <div className="relative mb-5 flex items-center gap-3">
        <div className="relative flex size-11 items-center justify-center">
          {running && (
            <motion.span
              className="absolute inset-0 rounded-full border-2 border-brand/20 border-t-brand"
              animate={{ rotate: 360 }}
              transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
            />
          )}
          <AnimatePresence mode="wait">
            <motion.span
              key={running ? "running" : job?.status}
              initial={{ scale: 0.4, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ type: "spring", stiffness: 380, damping: 18 }}
              className={cx(
                "flex size-8 items-center justify-center rounded-full",
                running ? "text-brand" : failed ? "bg-bad-soft text-bad" : "bg-good text-white",
              )}
            >
              {running ? <Sparkles className="size-4" /> : failed ? <CircleAlert className="size-4" /> : <Check className="size-4" strokeWidth={3} />}
            </motion.span>
          </AnimatePresence>
        </div>
        <div>
          <div className="font-semibold">{running ? title : failed ? "Something went wrong" : "All done"}</div>
          <div className="text-sm text-subtle">
            {percent !== null ? `Step ${job?.done} of ${job?.total}` : running ? "Starting…" : `${job?.steps.length ?? 0} steps completed`}
          </div>
        </div>
        {percent !== null && <div className="ml-auto text-2xl font-semibold text-brand tabular-nums">{percent}%</div>}
      </div>

      <div className={cx("relative mb-5 h-2 overflow-hidden rounded-full bg-sunken", running && "shine")}>
        <motion.div
          className={cx("h-full rounded-full", failed ? "bg-bad" : "bg-brand-gradient")}
          initial={{ width: "4%" }}
          animate={{ width: `${Math.max(percent ?? (running ? 8 : 100), 4)}%` }}
          transition={{ duration: 0.7, ease: EASE }}
        />
      </div>

      <ol className="relative space-y-2.5 text-sm">
        <AnimatePresence initial={false}>
          {(job?.steps ?? []).map((step, index) => (
            <motion.li
              key={`${index}-${step.message}`}
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.35, ease: EASE }}
              className="flex gap-2.5"
            >
              <span className="mt-0.5 flex size-4 shrink-0 items-center justify-center rounded-full bg-good-soft text-good">
                <Check className="size-3" strokeWidth={3} />
              </span>
              <span>{step.message}</span>
            </motion.li>
          ))}
          {running && (
            <motion.li key="working" layout initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex items-center gap-2.5 text-subtle">
              <span className="relative flex size-4 shrink-0 items-center justify-center">
                <span className="absolute size-full animate-ping rounded-full bg-brand/30" />
                <span className="size-2 rounded-full bg-brand" />
              </span>
              <span>Working… busy free-tier AI models can take a few minutes.</span>
            </motion.li>
          )}
        </AnimatePresence>
      </ol>

      {failed && (
        <Alert tone="error" className="mt-5">
          {job?.error}
        </Alert>
      )}
    </div>
  );
}
