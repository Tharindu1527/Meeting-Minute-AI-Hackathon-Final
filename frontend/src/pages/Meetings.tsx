import { useQuery } from "@tanstack/react-query";
import { ArrowUpRight, CircleDot, FilePlus2, Files, Gavel, ListChecks, Search } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useState } from "react";
import { Link, useNavigate } from "react-router";
import { Alert, Badge, Button, EmptyState, PageHeader, Skeleton, Stat, inputClass } from "../components/ui";
import { api } from "../lib/api";
import { firstName, useUser } from "../lib/auth";
import { plural } from "../lib/format";
import { EASE } from "../lib/motion";
import type { MeetingSummary } from "../lib/types";

function DateTile({ iso }: { iso: string | null }) {
  const date = iso ? new Date(`${iso.slice(0, 10)}T00:00:00Z`) : null;
  return (
    <div className="flex w-14 shrink-0 flex-col items-center overflow-hidden rounded-xl border border-line bg-card text-center shadow-card">
      <div className="w-full bg-deep-gradient py-0.5 text-[10px] font-semibold tracking-wider text-white uppercase">
        {date ? date.toLocaleDateString(undefined, { month: "short", timeZone: "UTC" }) : "—"}
      </div>
      <div className="py-1.5 text-lg leading-none font-semibold">{date ? date.getUTCDate() : "?"}</div>
    </div>
  );
}

function MeetingCard({ meeting, index }: { meeting: MeetingSummary; index: number }) {
  return (
    <motion.li
      layout
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.98 }}
      transition={{ duration: 0.4, ease: EASE, delay: Math.min(index, 8) * 0.05 }}
    >
      <Link
        to={`/meetings/${meeting.id}`}
        className="group flex gap-4 rounded-2xl border border-line bg-card p-5 shadow-card transition duration-300 hover:-translate-y-0.5 hover:border-brand/30 hover:shadow-lift"
      >
        <DateTile iso={meeting.meeting_date} />
        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-3">
            <h2 className="font-semibold tracking-tight transition-colors group-hover:text-brand">{meeting.title}</h2>
            <ArrowUpRight className="size-5 shrink-0 text-subtle transition duration-300 group-hover:translate-x-0.5 group-hover:-translate-y-0.5 group-hover:text-brand" />
          </div>
          {meeting.summary && <p className="mt-1.5 line-clamp-2 text-sm leading-relaxed text-subtle">{meeting.summary}</p>}
          <div className="mt-3 flex flex-wrap gap-2">
            <Badge>
              <Gavel className="size-3" /> {plural(meeting.decision_count, "decision")}
            </Badge>
            <Badge tone={meeting.open_action_item_count ? "brand" : "good"}>
              <CircleDot className="size-3" />
              {meeting.open_action_item_count ? `${meeting.open_action_item_count} open of ${meeting.action_item_count}` : "All actions done"}
            </Badge>
          </div>
        </div>
      </Link>
    </motion.li>
  );
}

function ListSkeleton() {
  return (
    <div className="space-y-3">
      {[0, 1, 2].map((i) => (
        <div key={i} className="flex gap-4 rounded-2xl border border-line bg-card p-5">
          <Skeleton className="h-14 w-14 rounded-xl" />
          <div className="flex-1 space-y-2.5">
            <Skeleton className="h-4 w-1/3" />
            <Skeleton className="h-3 w-5/6" />
            <Skeleton className="h-3 w-2/3" />
          </div>
        </div>
      ))}
    </div>
  );
}

function greeting() {
  const hour = new Date().getHours();
  return hour < 5 ? "Working late" : hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";
}

export function Meetings() {
  const user = useUser();
  const navigate = useNavigate();
  const meetings = useQuery({ queryKey: ["meetings"], queryFn: api.meetings });
  const [search, setSearch] = useState("");

  const all = meetings.data ?? [];
  const term = search.trim().toLowerCase();
  const visible = all.filter((m) => !term || m.title.toLowerCase().includes(term) || m.summary.toLowerCase().includes(term));

  return (
    <div>
      <PageHeader
        eyebrow="Your meetings"
        title={
          <>
            {greeting()}, <span className="text-brand-gradient">{firstName(user)}</span>
          </>
        }
        description="Every meeting you've turned into minutes, newest first. Only you can see them."
        actions={
          <Button variant="primary" icon={FilePlus2} onClick={() => navigate("/new")}>
            New meeting
          </Button>
        }
      />

      {meetings.isPending && <ListSkeleton />}
      {meetings.isError && <Alert tone="error">{meetings.error.message}</Alert>}
      {meetings.data?.length === 0 && (
        <EmptyState icon={Files} title="No meetings yet">
          Upload a recording or paste a transcript on the{" "}
          <Link to="/new" className="font-medium text-brand hover:underline">
            New meeting
          </Link>{" "}
          page and your minutes will appear here.
        </EmptyState>
      )}

      {all.length > 0 && (
        <>
          <div className="mb-6 grid grid-cols-1 gap-3 sm:grid-cols-3">
            <Stat label="Meetings" value={all.length} icon={Files} />
            <Stat label="Decisions recorded" value={all.reduce((n, m) => n + m.decision_count, 0)} icon={Gavel} tone="good" />
            <Stat label="Open action items" value={all.reduce((n, m) => n + m.open_action_item_count, 0)} icon={ListChecks} tone="warn" />
          </div>

          <div className="relative mb-4 max-w-md">
            <Search className="pointer-events-none absolute top-1/2 left-3.5 size-4 -translate-y-1/2 text-subtle" />
            <input
              className={`${inputClass} pl-10`}
              placeholder="Search titles and summaries"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              aria-label="Search meetings"
            />
          </div>

          {visible.length === 0 && <p className="text-sm text-subtle">No meetings match “{search}”.</p>}
          <ul className="grid grid-cols-1 gap-3">
            <AnimatePresence initial={true} mode="popLayout">
              {visible.map((m, i) => (
                <MeetingCard key={m.id} meeting={m} index={i} />
              ))}
            </AnimatePresence>
          </ul>
        </>
      )}
    </div>
  );
}
