import { useQuery } from "@tanstack/react-query";
import {
  CornerDownLeft,
  FilePlus2,
  FileText,
  Files,
  Headphones,
  ListChecks,
  LogOut,
  MessagesSquare,
  Monitor,
  Moon,
  Search,
  ShieldCheck,
  Sun,
  UserCog,
  type LucideIcon,
} from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type KeyboardEvent as ReactKeyboardEvent, type ReactNode } from "react";
import { useNavigate } from "react-router";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { cx, formatDate } from "../lib/format";
import { EASE } from "../lib/motion";
import { useTheme } from "../lib/theme";

interface Command {
  id: string;
  group: string;
  label: string;
  hint?: string;
  icon: LucideIcon;
  keywords?: string;
  run: () => void;
}

const PaletteContext = createContext<() => void>(() => {});

/** Opens the command palette (also bound to Ctrl+K / ⌘K) */
export const useCommandPalette = () => useContext(PaletteContext);

export const SHORTCUT_LABEL = typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform) ? "⌘K" : "Ctrl K";

const PAGES: { to: string; label: string; icon: LucideIcon; keywords: string }[] = [
  { to: "/new", label: "New meeting", icon: FilePlus2, keywords: "create upload record transcript generate" },
  { to: "/meetings", label: "Meetings", icon: Files, keywords: "dashboard home list minutes" },
  { to: "/action-items", label: "Action items", icon: ListChecks, keywords: "tasks todo owners due" },
  { to: "/chat", label: "Chat", icon: MessagesSquare, keywords: "ask question assistant" },
  { to: "/listen", label: "Listen", icon: Headphones, keywords: "audio speech podcast" },
  { to: "/fact-check", label: "Fact check", icon: ShieldCheck, keywords: "claims verify wikipedia" },
  { to: "/account", label: "Account settings", icon: UserCog, keywords: "profile password theme sign out delete" },
];

function Palette({ onClose }: { onClose: () => void }) {
  const navigate = useNavigate();
  const { signOut } = useAuth();
  const { setChoice } = useTheme();
  const meetings = useQuery({ queryKey: ["meetings"], queryFn: api.meetings });
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const listRef = useRef<HTMLDivElement>(null);

  const commands = useMemo<Command[]>(() => {
    const center = { x: window.innerWidth / 2, y: window.innerHeight / 2 };
    const go = (to: string) => () => navigate(to);
    return [
      ...PAGES.map((page) => ({ id: page.to, group: "Go to", label: page.label, icon: page.icon, keywords: page.keywords, run: go(page.to) })),
      ...(meetings.data ?? []).map((meeting) => ({
        id: `meeting-${meeting.id}`,
        group: "Meetings",
        label: meeting.title,
        hint: formatDate(meeting.meeting_date),
        icon: FileText,
        keywords: meeting.summary,
        run: go(`/meetings/${meeting.id}`),
      })),
      { id: "theme-light", group: "Theme", label: "Light theme", icon: Sun, keywords: "appearance colour", run: () => setChoice("light", center) },
      { id: "theme-dark", group: "Theme", label: "Dark theme", icon: Moon, keywords: "appearance colour night", run: () => setChoice("dark", center) },
      { id: "theme-system", group: "Theme", label: "Match my device", icon: Monitor, keywords: "appearance system auto", run: () => setChoice("system", center) },
      { id: "sign-out", group: "Account", label: "Sign out", icon: LogOut, keywords: "log out leave", run: signOut },
    ];
  }, [meetings.data, navigate, setChoice, signOut]);

  const results = useMemo(() => {
    const terms = query.toLowerCase().split(/\s+/).filter(Boolean);
    const matching = commands.filter((command) => {
      const text = `${command.label} ${command.group} ${command.keywords ?? ""}`.toLowerCase();
      return terms.every((term) => text.includes(term));
    });
    // Without a search, show a few recent meetings rather than all of them
    let shownMeetings = 0;
    return matching.filter((command) => command.group !== "Meetings" || ++shownMeetings <= (terms.length ? 8 : 4));
  }, [commands, query]);

  useEffect(() => setActive(0), [query]);
  // Give focus back to whatever had it before the palette opened
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    return () => previous?.focus?.();
  }, []);
  useEffect(() => {
    listRef.current?.querySelector(`[data-index="${active}"]`)?.scrollIntoView({ block: "nearest" });
  }, [active]);

  const run = (command: Command | undefined) => {
    if (!command) return;
    onClose();
    command.run();
  };

  const onKeyDown = (event: ReactKeyboardEvent) => {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      const step = event.key === "ArrowDown" ? 1 : -1;
      setActive((index) => (results.length ? (index + step + results.length) % results.length : 0));
    } else if (event.key === "Enter") {
      event.preventDefault();
      run(results[active]);
    } else if (event.key === "Escape") {
      onClose();
    }
  };

  let lastGroup = "";
  return (
    <motion.div className="fixed inset-0 z-50 flex items-start justify-center px-4 pt-[12vh]" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={onClose} />
      <motion.div
        role="dialog"
        aria-modal="true"
        aria-label="Search and commands"
        initial={{ opacity: 0, scale: 0.96, y: -10 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.97, y: -6, transition: { duration: 0.12 } }}
        transition={{ duration: 0.25, ease: EASE }}
        className="relative w-full max-w-xl overflow-hidden rounded-2xl border border-line bg-card shadow-pop"
        onKeyDown={onKeyDown}
      >
        <div className="flex items-center gap-3 border-b border-line px-4">
          <Search className="size-[18px] shrink-0 text-brand" />
          <input
            autoFocus
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search pages, meetings and actions…"
            aria-label="Search"
            role="combobox"
            aria-expanded="true"
            aria-controls="palette-results"
            aria-activedescendant={results[active] ? `palette-${results[active].id}` : undefined}
            className="h-14 flex-1 bg-transparent text-[15px] outline-none placeholder:text-subtle/70"
          />
          <kbd className="rounded-md border border-line bg-sunken px-1.5 py-0.5 text-[11px] font-medium text-subtle">Esc</kbd>
        </div>
        <div ref={listRef} id="palette-results" role="listbox" className="max-h-[55vh] overflow-y-auto p-2">
          {results.length === 0 && (
            <div className="px-3 py-10 text-center text-sm text-subtle">
              Nothing matches <span className="font-semibold text-ink">“{query}”</span>
            </div>
          )}
          {results.map((command, index) => {
            const heading = command.group !== lastGroup ? command.group : null;
            lastGroup = command.group;
            const Icon = command.icon;
            const isActive = index === active;
            return (
              <div key={command.id}>
                {heading && <div className="px-3 pt-3 pb-1.5 text-[11px] font-semibold tracking-[0.12em] text-subtle uppercase">{heading}</div>}
                <div
                  id={`palette-${command.id}`}
                  role="option"
                  aria-selected={isActive}
                  data-index={index}
                  onMouseMove={() => setActive(index)}
                  onClick={() => run(command)}
                  className={cx("relative flex cursor-pointer items-center gap-3 rounded-xl px-3 py-2.5 text-sm", isActive ? "text-ink" : "text-subtle")}
                >
                  {isActive && (
                    <motion.span layoutId="palette-active" className="absolute inset-0 rounded-xl bg-brand-soft" transition={{ type: "spring", stiffness: 600, damping: 40 }} />
                  )}
                  <Icon className={cx("relative size-4 shrink-0", isActive && "text-brand")} />
                  <span className="relative min-w-0 flex-1 truncate font-medium">{command.label}</span>
                  {command.hint && <span className="relative shrink-0 text-xs text-subtle">{command.hint}</span>}
                  {isActive && <CornerDownLeft className="relative size-3.5 shrink-0 text-brand" />}
                </div>
              </div>
            );
          })}
        </div>
        <div className="flex items-center gap-4 border-t border-line bg-sunken/50 px-4 py-2.5 text-[11px] text-subtle">
          <span>
            <kbd className="font-sans font-semibold">↑↓</kbd> to move
          </span>
          <span>
            <kbd className="font-sans font-semibold">↵</kbd> to open
          </span>
          <span className="ml-auto">{SHORTCUT_LABEL} anywhere</span>
        </div>
      </motion.div>
    </motion.div>
  );
}

export function CommandPaletteProvider({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const show = useCallback(() => setOpen(true), []);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setOpen((value) => !value);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <PaletteContext.Provider value={show}>
      {children}
      <AnimatePresence>{open && <Palette onClose={() => setOpen(false)} />}</AnimatePresence>
    </PaletteContext.Provider>
  );
}
