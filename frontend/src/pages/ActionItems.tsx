import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlarmClock, CheckCheck, CircleDot, ListChecks } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useState } from "react";
import { Link } from "react-router";
import { Avatar } from "../components/MinutesView";
import { useToast } from "../components/Toaster";
import { Alert, Badge, EmptyState, PageHeader, Skeleton, Stat, inputClass } from "../components/ui";
import { api } from "../lib/api";
import { cx, formatDate } from "../lib/format";
import { EASE } from "../lib/motion";
import { PRIORITIES, STATUSES, type Status, type TrackedActionItem } from "../lib/types";

type Update = Partial<Pick<TrackedActionItem, "owner" | "due_date" | "priority" | "status">>;

const cellInput =
  "w-full rounded-lg border border-transparent bg-transparent px-2 py-1.5 text-sm transition hover:border-line hover:bg-card focus:border-brand focus:bg-card focus:ring-4 focus:ring-brand/12 focus:outline-none";

function OwnerCell({ item, onSave }: { item: TrackedActionItem; onSave: (update: Update) => void }) {
  const [value, setValue] = useState(item.owner ?? "");
  const commit = () => {
    const owner = value.trim() || null;
    if (owner !== item.owner) onSave({ owner });
  };
  return (
    <div className="flex items-center gap-2">
      {item.owner && <Avatar name={item.owner} size="sm" />}
      <input
        aria-label={`Owner of ${item.task}`}
        className={cellInput}
        value={value}
        placeholder="Unassigned"
        onChange={(e) => setValue(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()}
      />
    </div>
  );
}

export function ActionItems() {
  const queryClient = useQueryClient();
  const toast = useToast();
  const items = useQuery({ queryKey: ["action-items"], queryFn: api.actionItems });
  const [statuses, setStatuses] = useState<Status[]>(["Open", "In progress"]);
  const [owner, setOwner] = useState("");

  const update = useMutation({
    mutationFn: ({ item, fields }: { item: TrackedActionItem; fields: Update }) => api.updateActionItem(item.meeting_id, item.id, fields),
    // Update the table immediately; roll back if the server rejects the change
    onMutate: async ({ item, fields }) => {
      await queryClient.cancelQueries({ queryKey: ["action-items"] });
      const previous = queryClient.getQueryData<TrackedActionItem[]>(["action-items"]);
      queryClient.setQueryData<TrackedActionItem[]>(["action-items"], (current) =>
        current?.map((i) => (i.id === item.id && i.meeting_id === item.meeting_id ? { ...i, ...fields } : i)),
      );
      return { previous };
    },
    onSuccess: (_data, { fields }) => {
      if (fields.status === "Done") toast("success", "Nice work!", "Action item marked as done");
      else toast("success", "Saved");
    },
    onError: (error, _vars, context) => {
      queryClient.setQueryData(["action-items"], context?.previous);
      toast("error", "Could not save", error.message);
    },
    onSettled: (_data, _error, { item }) => {
      queryClient.invalidateQueries({ queryKey: ["action-items"] });
      queryClient.invalidateQueries({ queryKey: ["meeting", item.meeting_id] });
      queryClient.invalidateQueries({ queryKey: ["meetings"] });
    },
  });

  if (items.isPending)
    return (
      <div className="space-y-5">
        <Skeleton className="h-9 w-56" />
        <div className="grid grid-cols-3 gap-3">
          <Skeleton className="h-20 rounded-2xl" />
          <Skeleton className="h-20 rounded-2xl" />
          <Skeleton className="h-20 rounded-2xl" />
        </div>
        <Skeleton className="h-64 rounded-2xl" />
      </div>
    );
  if (items.isError) return <Alert tone="error">{items.error.message}</Alert>;

  const all = items.data;
  const owners = [...new Set(all.map((i) => i.owner).filter((o): o is string => Boolean(o)))].sort();
  const visible = all
    .filter((i) => statuses.includes(i.status) && (!owner || i.owner === owner))
    .sort((a, b) => Number(b.overdue) - Number(a.overdue) || (a.due_date ?? "9999").localeCompare(b.due_date ?? "9999"));
  const save = (item: TrackedActionItem, fields: Update) => update.mutate({ item, fields });

  return (
    <div>
      <PageHeader eyebrow="Follow-up" title="Action items" description="Every commitment from every meeting. Changes save as you make them." />

      {all.length === 0 ? (
        <EmptyState icon={ListChecks} title="No action items yet">
          They appear here once meetings have been analysed.
        </EmptyState>
      ) : (
        <>
          <div className="mb-6 grid grid-cols-1 gap-3 sm:grid-cols-3">
            <Stat label="Open" value={all.filter((i) => i.status !== "Done").length} icon={CircleDot} />
            <Stat label="Overdue" value={all.filter((i) => i.overdue).length} icon={AlarmClock} tone={all.some((i) => i.overdue) ? "bad" : "neutral"} />
            <Stat label="Done" value={all.filter((i) => i.status === "Done").length} icon={CheckCheck} tone="good" />
          </div>

          <div className="mb-5 flex flex-wrap items-end gap-4">
            <div>
              <div className="mb-1.5 text-sm font-medium">Status</div>
              <div className="inline-flex gap-1 rounded-xl bg-sunken p-1">
                {STATUSES.map((s) => {
                  const on = statuses.includes(s);
                  return (
                    <button
                      key={s}
                      type="button"
                      aria-pressed={on}
                      onClick={() => setStatuses(on ? statuses.filter((x) => x !== s) : [...statuses, s])}
                      className={cx(
                        "rounded-lg px-3.5 py-1.5 text-sm font-medium transition duration-200",
                        on ? "bg-card text-ink shadow-card" : "text-subtle hover:text-ink",
                      )}
                    >
                      {s}
                    </button>
                  );
                })}
              </div>
            </div>
            <label className="block w-52">
              <span className="mb-1.5 block text-sm font-medium">Owner</span>
              <select className={inputClass} value={owner} onChange={(e) => setOwner(e.target.value)}>
                <option value="">Everyone</option>
                {owners.map((o) => (
                  <option key={o}>{o}</option>
                ))}
              </select>
            </label>
          </div>

          {visible.length === 0 ? (
            <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="rounded-2xl border border-dashed border-line p-8 text-center text-sm text-subtle">
              No action items match these filters.
            </motion.p>
          ) : (
            <div className="overflow-x-auto rounded-2xl border border-line bg-card shadow-card">
              <table className="w-full min-w-[860px] text-sm">
                <thead>
                  <tr className="border-b border-line bg-sunken/60 text-left text-[11px] font-semibold tracking-[0.1em] text-subtle uppercase">
                    <th className="px-5 py-3">Task</th>
                    <th className="w-48 px-2 py-3">Owner</th>
                    <th className="w-40 px-2 py-3">Due</th>
                    <th className="w-32 px-2 py-3">Priority</th>
                    <th className="w-36 px-2 py-3">Status</th>
                  </tr>
                </thead>
                <tbody>
                  <AnimatePresence initial={false}>
                    {visible.map((item) => (
                      <motion.tr
                        key={`${item.meeting_id}:${item.id}`}
                        layout
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0, transition: { duration: 0.15 } }}
                        transition={{ duration: 0.3, ease: EASE }}
                        className={cx("border-b border-line transition-colors last:border-0 hover:bg-sunken/40", item.overdue && "bg-bad-soft/40")}
                      >
                        <td className="px-5 py-3">
                          <div className={cx("font-medium", item.status === "Done" && "text-subtle line-through decoration-subtle/40")}>{item.task}</div>
                          <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-subtle">
                            <Link to={`/meetings/${item.meeting_id}`} className="transition hover:text-brand hover:underline">
                              {item.meeting_title} · {formatDate(item.meeting_date)}
                            </Link>
                            {item.overdue && (
                              <Badge tone="bad" dot>
                                Overdue
                              </Badge>
                            )}
                          </div>
                        </td>
                        <td className="px-2 py-3">
                          <OwnerCell key={item.owner ?? ""} item={item} onSave={(fields) => save(item, fields)} />
                        </td>
                        <td className="px-2 py-3">
                          <input
                            type="date"
                            aria-label={`Due date of ${item.task}`}
                            className={cellInput}
                            value={item.due_date ?? ""}
                            onChange={(e) => save(item, { due_date: e.target.value || null })}
                          />
                        </td>
                        <td className="px-2 py-3">
                          <select
                            aria-label={`Priority of ${item.task}`}
                            className={cellInput}
                            value={item.priority}
                            onChange={(e) => save(item, { priority: e.target.value as TrackedActionItem["priority"] })}
                          >
                            {PRIORITIES.map((p) => (
                              <option key={p}>{p}</option>
                            ))}
                          </select>
                        </td>
                        <td className="px-2 py-3">
                          <select
                            aria-label={`Status of ${item.task}`}
                            className={cellInput}
                            value={item.status}
                            onChange={(e) => save(item, { status: e.target.value as Status })}
                          >
                            {STATUSES.map((s) => (
                              <option key={s}>{s}</option>
                            ))}
                          </select>
                        </td>
                      </motion.tr>
                    ))}
                  </AnimatePresence>
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  );
}
