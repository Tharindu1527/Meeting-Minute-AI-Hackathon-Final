import { CircleAlert, CircleCheck, Info, X, type LucideIcon } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from "react";
import { cx } from "../lib/format";
import { EASE } from "../lib/motion";

type Tone = "success" | "error" | "info";

interface Toast {
  id: number;
  tone: Tone;
  title: string;
  description?: string;
}

const ICONS: Record<Tone, { icon: LucideIcon; className: string }> = {
  success: { icon: CircleCheck, className: "text-good" },
  error: { icon: CircleAlert, className: "text-bad" },
  info: { icon: Info, className: "text-brand" },
};

type Notify = (tone: Tone, title: string, description?: string) => void;

const ToastContext = createContext<Notify>(() => {});

/** Show a short notification: const toast = useToast(); toast("success", "Saved") */
export const useToast = () => useContext(ToastContext);

export function Toaster({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const nextId = useRef(1);

  const dismiss = useCallback((id: number) => setToasts((current) => current.filter((t) => t.id !== id)), []);

  const notify = useCallback<Notify>(
    (tone, title, description) => {
      const id = nextId.current++;
      setToasts((current) => [...current.slice(-3), { id, tone, title, description }]);
      setTimeout(() => dismiss(id), tone === "error" ? 7000 : 3500);
    },
    [dismiss],
  );

  return (
    <ToastContext.Provider value={notify}>
      {children}
      <div aria-live="polite" className="pointer-events-none fixed right-4 bottom-4 z-[60] flex w-[min(24rem,calc(100vw-2rem))] flex-col gap-2">
        <AnimatePresence initial={false}>
          {toasts.map((toast) => {
            const { icon: Icon, className } = ICONS[toast.tone];
            return (
              <motion.div
                key={toast.id}
                layout
                initial={{ opacity: 0, y: 16, scale: 0.96 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, x: 40, transition: { duration: 0.2 } }}
                transition={{ duration: 0.35, ease: EASE }}
                className="glass pointer-events-auto flex items-start gap-3 rounded-2xl border border-line p-4 shadow-pop"
                role={toast.tone === "error" ? "alert" : "status"}
              >
                <Icon className={cx("mt-0.5 size-5 shrink-0", className)} />
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-semibold">{toast.title}</div>
                  {toast.description && <div className="mt-0.5 text-sm break-words text-subtle">{toast.description}</div>}
                </div>
                <button
                  type="button"
                  aria-label="Dismiss"
                  onClick={() => dismiss(toast.id)}
                  className="rounded-md p-0.5 text-subtle transition hover:bg-sunken hover:text-ink"
                >
                  <X className="size-4" />
                </button>
              </motion.div>
            );
          })}
        </AnimatePresence>
      </div>
    </ToastContext.Provider>
  );
}
