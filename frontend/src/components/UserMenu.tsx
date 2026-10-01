import { ChevronsUpDown, LogOut, Search, UserCog } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router";
import { useAuth, useUser } from "../lib/auth";
import { EASE } from "../lib/motion";
import { UserAvatar } from "./Avatar";
import { SHORTCUT_LABEL, useCommandPalette } from "./CommandPalette";
import { ThemeSwitcher } from "./ThemeSwitcher";

const itemClass =
  "flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-sm font-medium text-subtle transition-colors duration-150 hover:bg-sunken hover:text-ink";

/** The signed-in user at the bottom of the sidebar, opening a menu with settings, theme and sign out */
export function UserMenu({ version, onNavigate }: { version: string; onNavigate?: () => void }) {
  const user = useUser();
  const { signOut } = useAuth();
  const openPalette = useCommandPalette();
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onPointer = (event: PointerEvent) => {
      if (!root.current?.contains(event.target as Node)) setOpen(false);
    };
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && setOpen(false);
    window.addEventListener("pointerdown", onPointer);
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("pointerdown", onPointer);
      window.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const close = () => {
    setOpen(false);
    onNavigate?.();
  };

  return (
    <div ref={root} className="relative">
      <AnimatePresence>
        {open && (
          <motion.div
            role="menu"
            initial={{ opacity: 0, y: 8, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 6, scale: 0.98, transition: { duration: 0.12 } }}
            transition={{ duration: 0.2, ease: EASE }}
            className="absolute inset-x-0 bottom-full z-20 mb-2 origin-bottom rounded-2xl border border-line bg-card p-1.5 shadow-pop"
          >
            <div className="flex items-center gap-3 px-2.5 pt-2 pb-3">
              <UserAvatar user={user} size="md" />
              <div className="min-w-0">
                <div className="truncate text-sm font-semibold">{user.name}</div>
                <div className="truncate text-xs text-subtle">{user.email}</div>
              </div>
            </div>
            <div className="border-t border-line pt-1.5">
              <Link role="menuitem" to="/account" onClick={close} className={itemClass}>
                <UserCog className="size-4" /> Account settings
              </Link>
              <button
                role="menuitem"
                type="button"
                className={itemClass}
                onClick={() => {
                  close();
                  openPalette();
                }}
              >
                <Search className="size-4" /> Search
                <kbd className="ml-auto rounded-md border border-line bg-sunken px-1.5 py-0.5 text-[10px] font-semibold whitespace-nowrap">{SHORTCUT_LABEL}</kbd>
              </button>
              <div className="flex items-center justify-between gap-2 px-2.5 py-1.5">
                <span className="text-sm font-medium text-subtle">Theme</span>
                <ThemeSwitcher />
              </div>
            </div>
            <div className="mt-1 border-t border-line pt-1.5">
              <button role="menuitem" type="button" onClick={signOut} className={`${itemClass} hover:bg-bad-soft hover:text-bad`}>
                <LogOut className="size-4" /> Sign out
              </button>
              <div className="px-2.5 pt-1 pb-1 text-[10px] text-subtle/80">Meeting Minutes AI · version {version}</div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
      <button
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen(!open)}
        className="flex w-full items-center gap-3 rounded-2xl border border-line bg-card/60 p-2.5 text-left transition duration-200 hover:border-brand/30 hover:bg-card hover:shadow-card"
      >
        <UserAvatar user={user} />
        <div className="min-w-0 flex-1 leading-tight">
          <div className="truncate text-sm font-semibold">{user.name}</div>
          <div className="truncate text-xs text-subtle">{user.email}</div>
        </div>
        <ChevronsUpDown className="size-4 shrink-0 text-subtle" />
      </button>
    </div>
  );
}
