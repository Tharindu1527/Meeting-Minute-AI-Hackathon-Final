import { useMutation } from "@tanstack/react-query";
import { Code2, FileText, FileType2, LoaderCircle, Mail, Send, Share2, type LucideIcon } from "lucide-react";
import { useState } from "react";
import { api } from "../lib/api";
import { downloadBlob, fileSlug } from "../lib/format";
import type { ExportFormat, Meeting } from "../lib/types";
import { useToast } from "./Toaster";
import { Alert, Button, Card, Field, inputClass } from "./ui";

const FORMATS: { format: ExportFormat; label: string; hint: string; icon: LucideIcon }[] = [
  { format: "docx", label: "Word", hint: ".docx", icon: FileType2 },
  { format: "md", label: "Markdown", hint: ".md", icon: FileText },
  { format: "html", label: "HTML", hint: "print to PDF", icon: Code2 },
];

export function SharePanel({ meeting, emailEnabled }: { meeting: Meeting; emailEnabled: boolean }) {
  const toast = useToast();
  const [recipients, setRecipients] = useState("");
  const [exporting, setExporting] = useState<ExportFormat | null>(null);

  const email = useMutation({
    mutationFn: () => api.email(meeting.id, recipients),
    onSuccess: ({ results }) => {
      const sent = results.filter((r) => r.ok);
      if (sent.length) toast("success", "Minutes sent", sent.map((r) => r.recipient).join(", "));
      if (sent.length === results.length) setRecipients("");
    },
    onError: (e) => toast("error", "Could not send the minutes", e.message),
  });

  const download = async (format: ExportFormat) => {
    setExporting(format);
    try {
      downloadBlob(await api.exportMeeting(meeting.id, format), `${fileSlug(meeting.title, meeting.meeting_date)}.${format}`);
      toast("success", "Download started");
    } catch (e) {
      toast("error", "Export failed", (e as Error).message);
    } finally {
      setExporting(null);
    }
  };

  const failed = email.data?.results.filter((r) => !r.ok) ?? [];

  return (
    <Card title="Share" icon={Share2} description="Download the minutes or send them to the team.">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        {FORMATS.map(({ format, label, hint, icon: Icon }) => (
          <button
            key={format}
            type="button"
            onClick={() => download(format)}
            disabled={exporting !== null}
            className="group flex items-center gap-3 rounded-xl border border-line bg-card p-3.5 text-left transition duration-200 hover:-translate-y-0.5 hover:border-brand/40 hover:shadow-lift active:scale-[0.98] disabled:opacity-60"
          >
            <span className="flex size-10 items-center justify-center rounded-lg bg-sunken text-subtle transition group-hover:bg-brand-soft group-hover:text-brand">
              {exporting === format ? <LoaderCircle className="size-5 animate-spin" /> : <Icon className="size-5" />}
            </span>
            <span>
              <span className="block text-sm font-semibold">{label}</span>
              <span className="block text-xs text-subtle">{hint}</span>
            </span>
          </button>
        ))}
      </div>

      <div className="mt-6 border-t border-line pt-6">
        {emailEnabled ? (
          <form
            className="space-y-3"
            onSubmit={(e) => {
              e.preventDefault();
              email.mutate();
            }}
          >
            <Field label="Email the minutes" hint="One address per line, or separated by commas">
              <div className="relative">
                <Mail className="pointer-events-none absolute top-3 left-3.5 size-4 text-subtle" />
                <textarea
                  rows={2}
                  className={`${inputClass} pl-10`}
                  value={recipients}
                  onChange={(e) => setRecipients(e.target.value)}
                  placeholder="board@company.com"
                />
              </div>
            </Field>
            <Button type="submit" variant="primary" icon={Send} loading={email.isPending} disabled={!recipients.trim()}>
              Send minutes
            </Button>
            {failed.map((r) => (
              <Alert key={r.recipient} tone="error">
                Could not send to {r.recipient}: {r.error}
              </Alert>
            ))}
          </form>
        ) : (
          <p className="text-sm text-subtle">Email isn't configured. Add SMTP settings or COMPOSIO_API_KEY to your .env file.</p>
        )}
      </div>
    </Card>
  );
}
