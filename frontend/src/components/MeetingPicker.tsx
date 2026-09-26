import { useQuery } from "@tanstack/react-query";
import { CalendarDays, Files } from "lucide-react";
import { useEffect, type ReactNode } from "react";
import { Link, useSearchParams } from "react-router";
import { api } from "../lib/api";
import { formatDate } from "../lib/format";
import type { MeetingSummary } from "../lib/types";
import { Alert, EmptyState, Field, Skeleton, inputClass } from "./ui";

/**
 * Meeting selector kept in the URL (?meeting=<id>) so pages can link to each other
 */
export function useSelectedMeeting() {
  const meetings = useQuery({ queryKey: ["meetings"], queryFn: api.meetings });
  const [params, setParams] = useSearchParams();
  const requested = params.get("meeting");
  const list = meetings.data ?? [];
  const selected = list.find((m) => m.id === requested) ?? list[0] ?? null;

  useEffect(() => {
    if (selected && selected.id !== requested) setParams({ meeting: selected.id }, { replace: true });
  }, [selected, requested, setParams]);

  return {
    meetings,
    selected,
    select: (id: string) => setParams({ meeting: id }),
  };
}

export function MeetingPicker({
  meetings,
  selected,
  onSelect,
  label = "Meeting",
}: {
  meetings: MeetingSummary[];
  selected: MeetingSummary | null;
  onSelect: (id: string) => void;
  label?: string;
}) {
  return (
    <Field label={label} className="max-w-xl">
      <div className="relative">
        <CalendarDays className="pointer-events-none absolute top-1/2 left-3.5 size-4 -translate-y-1/2 text-subtle" />
        <select className={`${inputClass} pl-10`} value={selected?.id ?? ""} onChange={(e) => onSelect(e.target.value)}>
          {meetings.map((m) => (
            <option key={m.id} value={m.id}>
              {m.title} · {formatDate(m.meeting_date)}
            </option>
          ))}
        </select>
      </div>
    </Field>
  );
}

/** Loading/error/empty handling shared by pages that need at least one meeting */
export function MeetingsGate({ query, children }: { query: ReturnType<typeof useSelectedMeeting>["meetings"]; children: ReactNode }) {
  if (query.isPending)
    return (
      <div className="space-y-4">
        <Skeleton className="h-11 max-w-xl" />
        <Skeleton className="h-40" />
      </div>
    );
  if (query.isError) return <Alert tone="error">{query.error.message}</Alert>;
  if (!query.data.length)
    return (
      <EmptyState icon={Files} title="No meetings yet">
        <Link to="/new" className="font-medium text-brand hover:underline">
          Create your first meeting
        </Link>{" "}
        to get started.
      </EmptyState>
    );
  return <>{children}</>;
}
