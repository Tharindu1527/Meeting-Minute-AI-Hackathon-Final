import { CalendarClock, CircleHelp, FileText, Gavel, ListChecks, MessageSquareText, Sparkles, Users } from "lucide-react";
import { formatDate } from "../lib/format";
import { Stagger, StaggerItem } from "../lib/motion";
import type { Minutes } from "../lib/types";
import { Badge, Card, PRIORITY_TONE, STATUS_TONE } from "./ui";

function Paragraphs({ text }: { text: string }) {
  return (
    <div className="space-y-3 text-[15px] leading-relaxed">
      {text
        .split(/\n\s*\n/)
        .filter((p) => p.trim())
        .map((p, i) => (
          <p key={i}>{p}</p>
        ))}
    </div>
  );
}

function Empty({ children }: { children: string }) {
  return <p className="text-sm text-subtle">{children}</p>;
}

const AVATAR_COLOURS = [
  "from-indigo-500 to-violet-500",
  "from-sky-500 to-cyan-500",
  "from-emerald-500 to-teal-500",
  "from-amber-500 to-orange-500",
  "from-rose-500 to-pink-500",
  "from-fuchsia-500 to-purple-500",
];

export function initials(name: string) {
  const parts = name.trim().split(/\s+/);
  return ((parts[0]?.[0] ?? "") + (parts.length > 1 ? parts[parts.length - 1][0] : "")).toUpperCase() || "?";
}

/** Same person, same colour: pick the gradient from a hash of the name */
function avatarColour(name: string) {
  let hash = 0;
  for (const char of name.trim().toLowerCase()) hash = (hash * 31 + char.charCodeAt(0)) >>> 0;
  return AVATAR_COLOURS[hash % AVATAR_COLOURS.length];
}

export function Avatar({ name, size = "md" }: { name: string; size?: "sm" | "md" }) {
  return (
    <span
      className={`inline-flex shrink-0 items-center justify-center rounded-full bg-linear-to-br font-semibold text-white ${avatarColour(name)} ${
        size === "sm" ? "size-7 text-[11px]" : "size-9 text-xs"
      }`}
    >
      {initials(name)}
    </span>
  );
}

export function MinutesView({ minutes }: { minutes: Minutes }) {
  return (
    <Stagger className="space-y-5">
      <StaggerItem>
        <Card title="Summary" icon={FileText}>
          {minutes.summary ? <Paragraphs text={minutes.summary} /> : <Empty>No summary was produced.</Empty>}
          {minutes.highlights.length > 0 && (
            <div className="mt-5 rounded-xl bg-sunken/70 p-4">
              <div className="mb-2.5 flex items-center gap-2 text-xs font-semibold tracking-[0.12em] text-subtle uppercase">
                <Sparkles className="size-3.5 text-brand" /> Key takeaways
              </div>
              <ul className="space-y-2">
                {minutes.highlights.map((h, i) => (
                  <li key={i} className="flex gap-2.5 text-[15px]">
                    <span className="mt-2 size-1.5 shrink-0 rounded-full bg-brand-gradient" />
                    <span>{h}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {minutes.key_topics.length > 0 && (
            <div className="mt-4 flex flex-wrap gap-1.5">
              {minutes.key_topics.map((topic) => (
                <Badge key={topic} tone="brand">
                  # {topic}
                </Badge>
              ))}
            </div>
          )}
        </Card>
      </StaggerItem>

      <StaggerItem className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        <Card title="Attendees" icon={Users} description={minutes.attendees.length ? `${minutes.attendees.length} people` : undefined}>
          {minutes.attendees.length ? (
            <ul className="space-y-3">
              {minutes.attendees.map((a, i) => (
                <li key={i} className="flex items-center gap-3">
                  <Avatar name={a.name} />
                  <div className="min-w-0">
                    <div className="truncate font-medium">{a.name}</div>
                    {a.role && <div className="truncate text-sm text-subtle">{a.role}</div>}
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <Empty>No attendees were identified.</Empty>
          )}
        </Card>

        <Card title="Decisions" icon={Gavel} description={minutes.decisions.length ? `${minutes.decisions.length} agreed` : undefined}>
          {minutes.decisions.length ? (
            <ol className="space-y-3.5">
              {minutes.decisions.map((d, i) => (
                <li key={i} className="flex gap-3">
                  <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-good-soft text-xs font-semibold text-good">
                    {i + 1}
                  </span>
                  <div className="min-w-0">
                    <div className="font-medium">{d.decision}</div>
                    {(d.decided_by || d.rationale) && (
                      <div className="mt-0.5 text-sm text-subtle">{[d.decided_by, d.rationale].filter(Boolean).join(" · ")}</div>
                    )}
                  </div>
                </li>
              ))}
            </ol>
          ) : (
            <Empty>No decisions were recorded.</Empty>
          )}
        </Card>
      </StaggerItem>

      <StaggerItem>
        <Card title="Action items" icon={ListChecks} description={minutes.action_items.length ? `${minutes.action_items.length} commitments` : undefined}>
          {minutes.action_items.length ? (
            <div className="-mx-5 overflow-x-auto sm:-mx-6">
              <table className="w-full min-w-[600px] text-sm">
                <thead>
                  <tr className="border-y border-line bg-sunken/60 text-left text-[11px] font-semibold tracking-[0.1em] text-subtle uppercase">
                    <th className="px-5 py-2.5 sm:px-6">Task</th>
                    <th className="px-3 py-2.5">Owner</th>
                    <th className="px-3 py-2.5">Due</th>
                    <th className="px-3 py-2.5">Priority</th>
                    <th className="px-5 py-2.5 sm:px-6">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {minutes.action_items.map((item) => (
                    <tr key={item.id} className="border-b border-line transition-colors last:border-0 hover:bg-sunken/50">
                      <td className="px-5 py-3.5 sm:px-6">
                        <div className="font-medium">{item.task}</div>
                        {item.context && <div className="mt-0.5 text-xs text-subtle">{item.context}</div>}
                      </td>
                      <td className="px-3 py-3.5">
                        {item.owner ? (
                          <span className="flex items-center gap-2 whitespace-nowrap">
                            <Avatar name={item.owner} size="sm" />
                            {item.owner}
                          </span>
                        ) : (
                          <span className="text-subtle">Unassigned</span>
                        )}
                      </td>
                      <td className="px-3 py-3.5 whitespace-nowrap">
                        {item.due_date ? (
                          <span className="inline-flex items-center gap-1.5">
                            <CalendarClock className="size-3.5 text-subtle" />
                            {formatDate(item.due_date)}
                          </span>
                        ) : (
                          <span className="text-subtle">—</span>
                        )}
                      </td>
                      <td className="px-3 py-3.5">
                        <Badge tone={PRIORITY_TONE[item.priority]} dot>
                          {item.priority}
                        </Badge>
                      </td>
                      <td className="px-5 py-3.5 sm:px-6">
                        <Badge tone={STATUS_TONE[item.status]}>{item.status}</Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <Empty>No action items were recorded.</Empty>
          )}
        </Card>
      </StaggerItem>

      {minutes.agenda_items.length > 0 && (
        <StaggerItem>
          <Card title="Discussion" icon={MessageSquareText}>
            <ol className="relative space-y-6 border-l border-line pl-6">
              {minutes.agenda_items.map((item, i) => (
                <li key={i} className="relative">
                  <span className="absolute top-0.5 -left-[35px] flex size-[22px] items-center justify-center rounded-full bg-deep-gradient text-[11px] font-semibold text-white ring-4 ring-card">
                    {i + 1}
                  </span>
                  <div className="font-semibold">{item.title}</div>
                  <p className="mt-1 leading-relaxed text-subtle">{item.discussion}</p>
                  {item.outcome && (
                    <div className="mt-2 rounded-lg border-l-2 border-good bg-good-soft/60 px-3 py-2 text-sm">
                      <span className="font-medium">Outcome:</span> {item.outcome}
                    </div>
                  )}
                </li>
              ))}
            </ol>
          </Card>
        </StaggerItem>
      )}

      {(minutes.open_issues.length > 0 || minutes.next_meeting) && (
        <StaggerItem>
          <Card title="Open issues & next steps" icon={CircleHelp}>
            {minutes.open_issues.length > 0 && (
              <ul className="space-y-2">
                {minutes.open_issues.map((issue, i) => (
                  <li key={i} className="flex gap-2.5">
                    <span className="mt-2 size-1.5 shrink-0 rounded-full bg-warn" />
                    <span>{issue}</span>
                  </li>
                ))}
              </ul>
            )}
            {minutes.next_meeting && (
              <div className="mt-4 inline-flex items-center gap-2 rounded-xl bg-brand-soft px-3.5 py-2 text-sm text-brand">
                <CalendarClock className="size-4" />
                <span className="font-medium">Next meeting:</span> {minutes.next_meeting}
              </div>
            )}
          </Card>
        </StaggerItem>
      )}
    </Stagger>
  );
}
