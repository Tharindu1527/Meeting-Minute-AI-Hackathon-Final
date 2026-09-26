import { CircleHelp, FileText, Gavel, ListChecks, MessageSquareText, Pencil, Plus, Save, Trash2, Users, X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useState } from "react";
import { cx } from "../lib/format";
import { EASE, Stagger, StaggerItem } from "../lib/motion";
import { PRIORITIES, STATUSES, type ActionItem, type AgendaItem, type Attendee, type Decision, type Minutes } from "../lib/types";
import { Alert, Button, Card, Field, inputClass } from "./ui";

type Column<Row> = {
  key: keyof Row & string;
  label: string;
  type?: "text" | "textarea" | "date" | "select";
  options?: string[];
  wide?: boolean;
};

let rowSeq = 0;
const rowKey = () => ++rowSeq;

/** Editable list of records (attendees, decisions, ...) with animated add and remove */
function RowsEditor<Row extends object>({
  rows,
  columns,
  onChange,
  newRow,
  addLabel,
}: {
  rows: Row[];
  columns: Column<Row>[];
  onChange: (rows: Row[]) => void;
  newRow: () => Row;
  addLabel: string;
}) {
  // Stable keys so removing a row animates that row, not the last one
  const [keys, setKeys] = useState(() => rows.map(rowKey));

  const update = (index: number, key: keyof Row, value: string) =>
    onChange(rows.map((row, i) => (i === index ? { ...row, [key]: value === "" && key !== columns[0].key ? null : value } : row)));
  const add = () => {
    setKeys([...keys, rowKey()]);
    onChange([...rows, newRow()]);
  };
  const remove = (index: number) => {
    setKeys(keys.filter((_, i) => i !== index));
    onChange(rows.filter((_, i) => i !== index));
  };

  return (
    <div className="space-y-3">
      <AnimatePresence initial={false}>
        {rows.map((row, index) => (
          <motion.div
            key={keys[index]}
            layout
            initial={{ opacity: 0, y: -8, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, scale: 0.96, transition: { duration: 0.18 } }}
            transition={{ duration: 0.3, ease: EASE }}
            className="relative rounded-xl border border-line bg-sunken/40 p-4 pr-12"
          >
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              {columns.map((column) => {
                const value = (row[column.key] as string | null) ?? "";
                const props = {
                  value,
                  "aria-label": column.label,
                  className: inputClass,
                  onChange: (e: { target: { value: string } }) => update(index, column.key, e.target.value),
                };
                return (
                  <Field key={column.key} label={column.label} className={cx(column.wide && "sm:col-span-2")}>
                    {column.type === "textarea" ? (
                      <textarea rows={3} {...props} />
                    ) : column.type === "select" ? (
                      <select {...props}>
                        {column.options?.map((option) => (
                          <option key={option}>{option}</option>
                        ))}
                      </select>
                    ) : (
                      <input type={column.type === "date" ? "date" : "text"} {...props} />
                    )}
                  </Field>
                );
              })}
            </div>
            <button
              type="button"
              aria-label="Remove"
              title="Remove"
              onClick={() => remove(index)}
              className="absolute top-3 right-3 rounded-lg p-1.5 text-subtle transition hover:bg-bad-soft hover:text-bad"
            >
              <Trash2 className="size-4" />
            </button>
          </motion.div>
        ))}
      </AnimatePresence>
      <Button size="sm" icon={Plus} onClick={add}>
        {addLabel}
      </Button>
    </div>
  );
}

const lines = (text: string) =>
  text
    .split("\n")
    .map((line) => line.replace(/^[\s\-•*]+/, "").trim())
    .filter(Boolean);

const filled = <Row,>(rows: Row[], key: keyof Row) => rows.filter((row) => String(row[key] ?? "").trim());

export function MinutesEditor({
  minutes,
  saving,
  error,
  onSave,
  onCancel,
}: {
  minutes: Minutes;
  saving: boolean;
  error?: string | null;
  onSave: (minutes: Minutes) => void;
  onCancel: () => void;
}) {
  const [summary, setSummary] = useState(minutes.summary);
  const [highlights, setHighlights] = useState(minutes.highlights.join("\n"));
  const [topics, setTopics] = useState(minutes.key_topics.join(", "));
  const [attendees, setAttendees] = useState<Attendee[]>(minutes.attendees);
  const [decisions, setDecisions] = useState<Decision[]>(minutes.decisions);
  const [actions, setActions] = useState<ActionItem[]>(minutes.action_items);
  const [agenda, setAgenda] = useState<AgendaItem[]>(minutes.agenda_items);
  const [openIssues, setOpenIssues] = useState(minutes.open_issues.join("\n"));
  const [nextMeeting, setNextMeeting] = useState(minutes.next_meeting ?? "");

  const save = () =>
    onSave({
      ...minutes,
      summary: summary.trim(),
      highlights: lines(highlights),
      key_topics: topics.split(",").map((t) => t.trim()).filter(Boolean),
      attendees: filled(attendees, "name"),
      decisions: filled(decisions, "decision"),
      action_items: filled(actions, "task"),
      agenda_items: filled(agenda, "title").map((a) => ({ ...a, discussion: a.discussion ?? "" })),
      open_issues: lines(openIssues),
      next_meeting: nextMeeting.trim() || null,
    });

  return (
    <div className="space-y-5">
      <motion.div
        initial={{ opacity: 0, y: -6 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-center gap-2.5 rounded-xl border border-brand/25 bg-brand-soft px-4 py-3 text-sm text-brand"
      >
        <Pencil className="size-4" /> Editing the minutes. Changes are saved when you press <b>Save changes</b>.
      </motion.div>

      <Stagger className="space-y-5">
        <StaggerItem>
          <Card title="Summary" icon={FileText}>
            <div className="space-y-4">
              <Field label="Executive summary">
                <textarea rows={7} className={inputClass} value={summary} onChange={(e) => setSummary(e.target.value)} />
              </Field>
              <Field label="Key takeaways" hint="One per line">
                <textarea rows={4} className={inputClass} value={highlights} onChange={(e) => setHighlights(e.target.value)} />
              </Field>
              <Field label="Topics" hint="Comma separated">
                <input className={inputClass} value={topics} onChange={(e) => setTopics(e.target.value)} />
              </Field>
            </div>
          </Card>
        </StaggerItem>

        <StaggerItem>
          <Card title="Attendees" icon={Users}>
            <RowsEditor
              rows={attendees}
              onChange={setAttendees}
              addLabel="Add attendee"
              newRow={() => ({ name: "", role: null, speaker_label: null })}
              columns={[
                { key: "name", label: "Name" },
                { key: "role", label: "Role" },
                { key: "speaker_label", label: "Transcript label" },
              ]}
            />
          </Card>
        </StaggerItem>

        <StaggerItem>
          <Card title="Decisions" icon={Gavel}>
            <RowsEditor
              rows={decisions}
              onChange={setDecisions}
              addLabel="Add decision"
              newRow={() => ({ decision: "", decided_by: null, rationale: null })}
              columns={[
                { key: "decision", label: "Decision", wide: true },
                { key: "decided_by", label: "Decided by" },
                { key: "rationale", label: "Rationale" },
              ]}
            />
          </Card>
        </StaggerItem>

        <StaggerItem>
          <Card title="Action items" icon={ListChecks}>
            <RowsEditor
              rows={actions}
              onChange={setActions}
              addLabel="Add action item"
              newRow={(): ActionItem => ({ id: "", task: "", owner: null, due_date: null, priority: "Medium", status: "Open", context: null })}
              columns={[
                { key: "task", label: "Task", wide: true },
                { key: "owner", label: "Owner" },
                { key: "due_date", label: "Due date", type: "date" },
                { key: "priority", label: "Priority", type: "select", options: PRIORITIES },
                { key: "status", label: "Status", type: "select", options: STATUSES },
                { key: "context", label: "Context", wide: true },
              ]}
            />
          </Card>
        </StaggerItem>

        <StaggerItem>
          <Card title="Discussion" icon={MessageSquareText}>
            <RowsEditor
              rows={agenda}
              onChange={setAgenda}
              addLabel="Add agenda item"
              newRow={() => ({ title: "", discussion: "", outcome: null })}
              columns={[
                { key: "title", label: "Agenda item", wide: true },
                { key: "discussion", label: "Discussion", type: "textarea", wide: true },
                { key: "outcome", label: "Outcome", wide: true },
              ]}
            />
          </Card>
        </StaggerItem>

        <StaggerItem>
          <Card title="Open issues & next steps" icon={CircleHelp}>
            <div className="space-y-4">
              <Field label="Open issues" hint="One per line">
                <textarea rows={3} className={inputClass} value={openIssues} onChange={(e) => setOpenIssues(e.target.value)} />
              </Field>
              <Field label="Next meeting">
                <input className={inputClass} value={nextMeeting} onChange={(e) => setNextMeeting(e.target.value)} />
              </Field>
            </div>
          </Card>
        </StaggerItem>
      </Stagger>

      {error && <Alert tone="error">{error}</Alert>}
      <motion.div
        initial={{ opacity: 0, y: 24 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: EASE, delay: 0.2 }}
        className="glass sticky bottom-4 z-10 flex items-center justify-between gap-2 rounded-2xl border border-line p-3 pl-5 shadow-pop"
      >
        <span className="hidden text-sm text-subtle sm:block">Unsaved changes stay here until you save or cancel.</span>
        <div className="ml-auto flex gap-2">
          <Button icon={X} onClick={onCancel} disabled={saving}>
            Cancel
          </Button>
          <Button variant="primary" icon={Save} onClick={save} loading={saving}>
            Save changes
          </Button>
        </div>
      </motion.div>
    </div>
  );
}
