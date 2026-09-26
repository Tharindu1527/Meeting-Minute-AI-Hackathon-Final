import { TriangleAlert } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useRef, type ReactNode } from "react";
import { EASE } from "../lib/motion";
import { Button, IconTile } from "./ui";

/** Modal asking the user to confirm a destructive action */
export function ConfirmDialog({
  open,
  title,
  children,
  confirmLabel,
  loading = false,
  onConfirm,
  onCancel,
}: {
  open: boolean;
  title: string;
  children?: ReactNode;
  confirmLabel: string;
  loading?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const cancelButton = useRef<HTMLButtonElement>(null);
  // Latest props for the key handler, so the effect below only runs when the dialog opens or closes
  const latest = useRef({ loading, onCancel });
  latest.current = { loading, onCancel };

  useEffect(() => {
    if (!open) return;
    const previous = document.activeElement as HTMLElement | null;
    cancelButton.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !latest.current.loading) latest.current.onCancel();
    };
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
      previous?.focus();
    };
  }, [open]);

  return (
    <AnimatePresence>
      {open && (
        <motion.div className="fixed inset-0 z-50 flex items-center justify-center p-4" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
          <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={() => !loading && onCancel()} />
          <motion.div
            role="alertdialog"
            aria-modal="true"
            aria-labelledby="confirm-title"
            initial={{ opacity: 0, scale: 0.95, y: 12 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.97, y: 6 }}
            transition={{ duration: 0.25, ease: EASE }}
            className="relative w-full max-w-md rounded-2xl border border-line bg-card p-6 shadow-pop"
          >
            <div className="flex gap-4">
              <IconTile icon={TriangleAlert} tone="bad" size="lg" />
              <div className="min-w-0">
                <h2 id="confirm-title" className="text-base font-semibold">
                  {title}
                </h2>
                {children && <div className="mt-1.5 text-sm text-subtle">{children}</div>}
              </div>
            </div>
            <div className="mt-6 flex justify-end gap-2">
              <Button ref={cancelButton} onClick={onCancel} disabled={loading}>
                Cancel
              </Button>
              <Button variant="danger" loading={loading} onClick={onConfirm}>
                {confirmLabel}
              </Button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
