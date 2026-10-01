import { ChevronDown, RefreshCw, Server, Settings2 } from "lucide-react";
import { motion } from "motion/react";
import { useState, type ReactNode } from "react";
import { Button, IconTile } from "../components/ui";
import { Collapse, EASE } from "../lib/motion";
import type { AppStatus } from "../lib/types";

/** Full-screen backdrop with soft brand glows and a card that scales in */
function Centered({ children, className = "max-w-sm" }: { children: ReactNode; className?: string }) {
  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden px-4 py-10">
      <motion.div
        aria-hidden
        className="pointer-events-none absolute -top-40 left-1/2 size-[520px] -translate-x-1/2 rounded-full bg-brand/20 blur-3xl"
        animate={{ scale: [1, 1.08, 1], opacity: [0.8, 1, 0.8] }}
        transition={{ duration: 8, repeat: Infinity, ease: "easeInOut" }}
      />
      <div aria-hidden className="pointer-events-none absolute -right-32 -bottom-40 size-[420px] rounded-full bg-brand-2/15 blur-3xl" />
      <motion.div
        initial={{ opacity: 0, y: 16, scale: 0.97 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.5, ease: EASE }}
        className={`glass relative w-full rounded-3xl border border-line p-7 shadow-pop sm:p-8 ${className}`}
      >
        {children}
      </motion.div>
    </div>
  );
}

export function SetupRequired({ status }: { status: AppStatus }) {
  const [showOptional, setShowOptional] = useState(false);
  return (
    <Centered className="max-w-xl">
      <div className="flex items-start gap-4">
        <IconTile icon={Settings2} tone="warn" size="lg" />
        <div>
          <h1 className="text-lg font-semibold tracking-tight">The app isn't configured yet</h1>
          <p className="mt-1 text-sm text-subtle">Add these to your .env file and restart the server.</p>
        </div>
      </div>
      <ul className="mt-6 space-y-2">
        {status.missing_config.map((item, i) => (
          <motion.li
            key={item.name}
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.2 + i * 0.06, duration: 0.35, ease: EASE }}
            className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-xl border border-line bg-card p-3"
          >
            <code className="rounded-md bg-warn-soft px-2 py-0.5 text-sm font-semibold text-warn">{item.name}</code>
            <span className="text-sm text-subtle">needed for {item.purpose}</span>
          </motion.li>
        ))}
      </ul>
      {status.optional_config.length > 0 && (
        <div className="mt-5">
          <button type="button" onClick={() => setShowOptional(!showOptional)} className="flex items-center gap-1.5 text-sm font-medium transition hover:text-brand">
            <motion.span animate={{ rotate: showOptional ? 180 : 0 }} transition={{ duration: 0.25 }}>
              <ChevronDown className="size-4" />
            </motion.span>
            Optional settings
          </button>
          <Collapse open={showOptional}>
            <ul className="mt-3 space-y-1.5 text-sm">
              {status.optional_config.map((item) => (
                <li key={item.name}>
                  <code className="text-xs font-semibold">{item.name}</code> <span className="text-subtle">— {item.purpose}</span>
                </li>
              ))}
            </ul>
          </Collapse>
        </div>
      )}
      <p className="mt-6 border-t border-line pt-4 text-xs text-subtle">See README.md and .env.example for details.</p>
    </Centered>
  );
}

export function ServerUnreachable({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <Centered className="max-w-md">
      <div className="flex items-start gap-4">
        <motion.div animate={{ scale: [1, 1.06, 1] }} transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}>
          <IconTile icon={Server} tone="bad" size="lg" />
        </motion.div>
        <div className="min-w-0">
          <h1 className="text-lg font-semibold tracking-tight">Can't reach the API server</h1>
          <p className="mt-1 text-sm break-words text-subtle">{message}</p>
        </div>
      </div>
      <div className="mt-5 rounded-xl bg-sunken p-3.5 text-sm">
        <div className="mb-1.5 text-xs font-medium text-subtle">Start it with</div>
        <code className="block overflow-x-auto font-mono text-[13px] whitespace-nowrap">uvicorn server.main:app --port 8000</code>
      </div>
      <Button className="mt-5 w-full" variant="primary" icon={RefreshCw} onClick={onRetry}>
        Try again
      </Button>
    </Centered>
  );
}
