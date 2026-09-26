import { FilePlus2, Files, Headphones, ListChecks, LogOut, Menu, MessagesSquare, NotebookPen, ShieldCheck, X, type LucideIcon } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useState, type ReactNode } from "react";
import { NavLink } from "react-router";
import { cx } from "../lib/format";
import { useModel } from "../lib/hooks";
import { EASE } from "../lib/motion";
import type { AppStatus } from "../lib/types";

const NAV: { to: string; label: string; icon: LucideIcon }[] = [
  { to: "/new", label: "New meeting", icon: FilePlus2 },
  { to: "/meetings", label: "Meetings", icon: Files },
  { to: "/action-items", label: "Action items", icon: ListChecks },
  { to: "/chat", label: "Chat", icon: MessagesSquare },
  { to: "/listen", label: "Listen", icon: Headphones },
  { to: "/fact-check", label: "Fact check", icon: ShieldCheck },
];

const SERVICE_LABELS: [keyof AppStatus["services"], string][] = [
  ["database", "Database"],
  ["transcription", "Transcription"],
  ["search", "Chat search"],
  ["email", "Email"],
];

export function Logo() {
  return (
    <div className="flex items-center gap-2.5 px-2">
      <span className="flex size-9 items-center justify-center rounded-xl bg-brand-gradient text-white shadow-glow">
        <NotebookPen className="size-[18px]" />
      </span>
      <div className="leading-tight">
        <div className="text-[15px] font-semibold tracking-tight">Meeting Minutes</div>
        <div className="text-[11px] font-medium text-subtle">AI agents · Gemini</div>
      </div>
    </div>
  );
}

function Sidebar({ status, idPrefix, onNavigate, onSignOut }: { status: AppStatus; idPrefix: string; onNavigate?: () => void; onSignOut?: () => void }) {
  const { model, setModel } = useModel();
  return (
    <div className="flex h-full flex-col gap-7 p-4">
      <div className="pt-1">
        <Logo />
      </div>

      <nav className="flex flex-col gap-0.5" aria-label="Main">
        {NAV.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            onClick={onNavigate}
            className={({ isActive }) =>
              cx(
                "group relative flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-colors duration-200",
                isActive ? "text-brand" : "text-subtle hover:text-ink",
              )
            }
          >
            {({ isActive }) => (
              <>
                {isActive && (
                  <motion.span
                    layoutId={`${idPrefix}-nav-active`}
                    className="absolute inset-0 rounded-xl bg-brand-soft"
                    transition={{ type: "spring", stiffness: 420, damping: 36 }}
                  />
                )}
                {!isActive && <span className="absolute inset-0 rounded-xl bg-sunken opacity-0 transition-opacity duration-200 group-hover:opacity-100" />}
                <Icon className="relative size-[18px] transition-transform duration-200 group-hover:scale-110" />
                <span className="relative">{label}</span>
              </>
            )}
          </NavLink>
        ))}
      </nav>

      <div className="mt-auto flex flex-col gap-5">
        <label className="block px-1">
          <span className="mb-1.5 block px-1 text-[11px] font-semibold tracking-[0.12em] text-subtle uppercase">AI model</span>
          <select
            value={model}
            onChange={(e) => setModel(e.target.value)}
            className="w-full rounded-xl border border-line bg-card px-3 py-2 text-sm shadow-card transition hover:border-brand/30 focus:border-brand focus:ring-4 focus:ring-brand/12 focus:outline-none"
          >
            {status.models.map((m) => (
              <option key={m}>{m}</option>
            ))}
          </select>
        </label>

        <div className="rounded-2xl border border-line bg-card/60 p-3.5">
          <div className="mb-2.5 text-[11px] font-semibold tracking-[0.12em] text-subtle uppercase">Services</div>
          <ul className="space-y-2 text-[13px]">
            {SERVICE_LABELS.map(([key, label]) => {
              const service = status.services[key];
              return (
                <li key={key} className="flex items-center gap-2.5" title={service.detail}>
                  <span className="relative flex size-2 shrink-0">
                    {service.ok && <span className="absolute inline-flex size-full animate-ping rounded-full bg-good opacity-40" />}
                    <span className={cx("relative inline-flex size-2 rounded-full", service.ok ? "bg-good" : "bg-line")} />
                  </span>
                  <span className="min-w-0 truncate">
                    <span className="font-medium">{label}</span> <span className="text-subtle">· {service.detail}</span>
                  </span>
                </li>
              );
            })}
          </ul>
          {!status.auth_required && (
            <p className="mt-3 border-t border-line pt-3 text-[11px] leading-relaxed text-subtle">
              No password set: anyone with the link can open this app. Set APP_PASSWORD to protect it.
            </p>
          )}
        </div>

        <div className="flex items-center justify-between px-1">
          <span className="text-[11px] text-subtle">Version {status.version}</span>
          {onSignOut && (
            <button
              type="button"
              onClick={onSignOut}
              className="flex items-center gap-1.5 rounded-lg px-2 py-1 text-xs font-medium text-subtle transition hover:bg-sunken hover:text-ink"
            >
              <LogOut className="size-3.5" /> Sign out
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

export function Layout({ status, onSignOut, children }: { status: AppStatus; onSignOut?: () => void; children: ReactNode }) {
  const [menuOpen, setMenuOpen] = useState(false);
  return (
    <div className="flex min-h-screen">
      <aside className="glass sticky top-0 hidden h-screen w-[268px] shrink-0 overflow-y-auto border-r border-line md:block">
        <Sidebar status={status} idPrefix="desktop" onSignOut={onSignOut} />
      </aside>

      <AnimatePresence>
        {menuOpen && (
          <div className="fixed inset-0 z-40 md:hidden">
            <motion.div
              className="absolute inset-0 bg-black/40 backdrop-blur-sm"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setMenuOpen(false)}
            />
            <motion.aside
              className="absolute inset-y-0 left-0 w-72 max-w-[85%] overflow-y-auto bg-card shadow-pop"
              initial={{ x: "-100%" }}
              animate={{ x: 0 }}
              exit={{ x: "-100%" }}
              transition={{ duration: 0.35, ease: EASE }}
            >
              <button
                type="button"
                aria-label="Close menu"
                onClick={() => setMenuOpen(false)}
                className="absolute top-5 right-3 z-10 rounded-lg p-1.5 text-subtle transition hover:bg-sunken hover:text-ink"
              >
                <X className="size-5" />
              </button>
              <Sidebar status={status} idPrefix="mobile" onNavigate={() => setMenuOpen(false)} onSignOut={onSignOut} />
            </motion.aside>
          </div>
        )}
      </AnimatePresence>

      <div className="min-w-0 flex-1">
        <header className="glass sticky top-0 z-30 flex items-center gap-3 border-b border-line px-4 py-3 md:hidden">
          <button
            type="button"
            aria-label="Open menu"
            onClick={() => setMenuOpen(true)}
            className="rounded-lg p-1.5 transition hover:bg-sunken"
          >
            <Menu className="size-5" />
          </button>
          <Logo />
        </header>
        <main className="mx-auto w-full max-w-5xl px-4 py-7 sm:px-8 lg:py-10">{children}</main>
      </div>
    </div>
  );
}
