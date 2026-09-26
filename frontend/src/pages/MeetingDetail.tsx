import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, CalendarDays, CircleHelp, Clock, Gavel, Globe, Headphones, ListChecks, MessagesSquare, Pencil, ShieldCheck, Trash2, Users } from "lucide-react";
import { motion } from "motion/react";
import { useState, type ReactNode } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { ConfirmDialog } from "../components/Dialog";
import { MeetingExtras } from "../components/MeetingExtras";
import { MinutesEditor } from "../components/MinutesEditor";
import { MinutesView } from "../components/MinutesView";
import { SharePanel } from "../components/SharePanel";
import { useToast } from "../components/Toaster";
import { Alert, Button, Card, Skeleton, Stat } from "../components/ui";
import { api } from "../lib/api";
import { formatDate, formatDuration, plural } from "../lib/format";
import { EASE, Reveal } from "../lib/motion";
import type { AppStatus, Minutes } from "../lib/types";

function MetaChip({ icon: Icon, children }: { icon: typeof Clock; children: ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-line bg-card/70 px-3 py-1 text-xs font-medium text-subtle">
      <Icon className="size-3.5" />
      {children}
    </span>
  );
}

function DetailSkeleton() {
  return (
    <div className="space-y-5">
      <Skeleton className="h-4 w-24" />
      <Skeleton className="h-9 w-2/3" />
      <div className="grid grid-cols-3 gap-3">
        <Skeleton className="h-20 rounded-2xl" />
        <Skeleton className="h-20 rounded-2xl" />
        <Skeleton className="h-20 rounded-2xl" />
      </div>
      <Skeleton className="h-56 rounded-2xl" />
      <Skeleton className="h-40 rounded-2xl" />
    </div>
  );
}

export function MeetingDetail({ status }: { status: AppStatus }) {
  const { meetingId = "" } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const toast = useToast();
  const [editing, setEditing] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const meeting = useQuery({ queryKey: ["meeting", meetingId], queryFn: () => api.meeting(meetingId) });

  const refreshLists = () => {
    queryClient.invalidateQueries({ queryKey: ["meetings"] });
    queryClient.invalidateQueries({ queryKey: ["action-items"] });
  };

  const save = useMutation({
    mutationFn: (minutes: Minutes) => api.saveMinutes(meetingId, minutes),
    onSuccess: (updated) => {
      queryClient.setQueryData(["meeting", meetingId], updated);
      refreshLists();
      setEditing(false);
      toast("success", "Minutes saved");
      window.scrollTo({ top: 0, behavior: "smooth" });
    },
  });

  const remove = useMutation({
    mutationFn: () => api.deleteMeeting(meetingId),
    onSuccess: (result) => {
      queryClient.removeQueries({ queryKey: ["meeting", meetingId] });
      refreshLists();
      toast("success", "Meeting deleted", result.warning ?? undefined);
      navigate("/meetings");
    },
    onError: (e) => toast("error", "Could not delete the meeting", e.message),
  });

  if (meeting.isPending) return <DetailSkeleton />;
  if (meeting.isError)
    return (
      <div className="space-y-4">
        <Alert tone="error">{meeting.error.message}</Alert>
        <Link to="/meetings" className="text-sm font-medium text-brand hover:underline">
          Back to meetings
        </Link>
      </div>
    );

  const m = meeting.data;
  const minutes = m.minutes;
  const duration = formatDuration(m.transcript?.duration_seconds);
  const openItems = minutes.action_items.filter((item) => item.status !== "Done").length;

  return (
    <div className="space-y-6">
      <div className="relative overflow-hidden rounded-3xl border border-line bg-card p-6 shadow-card sm:p-8">
        <div className="pointer-events-none absolute -top-24 -right-16 size-72 rounded-full bg-brand/15 blur-3xl" />
        <div className="pointer-events-none absolute inset-x-0 top-0 h-1 bg-brand-gradient" />
        <Link to="/meetings" className="relative mb-4 inline-flex items-center gap-1.5 text-sm text-subtle transition hover:text-ink">
          <ArrowLeft className="size-4" /> All meetings
        </Link>
        <div className="relative flex flex-wrap items-start justify-between gap-4">
          <motion.div className="min-w-0" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, ease: EASE }}>
            <h1 className="text-[26px] leading-tight font-semibold tracking-tight sm:text-3xl">{m.title}</h1>
            <div className="mt-3 flex flex-wrap gap-2">
              <MetaChip icon={CalendarDays}>{formatDate(m.meeting_date)}</MetaChip>
              {duration && <MetaChip icon={Clock}>{duration}</MetaChip>}
              <MetaChip icon={Users}>{plural(minutes.attendees.length, "attendee")}</MetaChip>
              {m.transcript?.language && <MetaChip icon={Globe}>{m.transcript.language.toUpperCase()}</MetaChip>}
            </div>
          </motion.div>
          {!editing && (
            <Button variant="primary" icon={Pencil} onClick={() => setEditing(true)}>
              Edit minutes
            </Button>
          )}
        </div>
        {!editing && (
          <div className="relative mt-6 flex flex-wrap gap-2 border-t border-line pt-5">
            <Button size="sm" icon={MessagesSquare} onClick={() => navigate(`/chat?meeting=${m.id}`)}>
              Ask about this meeting
            </Button>
            <Button size="sm" icon={Headphones} onClick={() => navigate(`/listen?meeting=${m.id}`)}>
              Listen
            </Button>
            <Button size="sm" icon={ShieldCheck} onClick={() => navigate(`/fact-check?meeting=${m.id}`)}>
              Fact check
            </Button>
          </div>
        )}
      </div>

      {m.warnings?.map((warning, i) => (
        <Alert key={i} tone="warning">
          {warning}
        </Alert>
      ))}

      {editing ? (
        <MinutesEditor
          minutes={minutes}
          saving={save.isPending}
          error={save.isError ? save.error.message : null}
          onSave={(updated) => save.mutate(updated)}
          onCancel={() => setEditing(false)}
        />
      ) : (
        <>
          <Reveal className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <Stat label="Decisions" value={minutes.decisions.length} icon={Gavel} tone="good" />
            <Stat label="Open actions" value={openItems} icon={ListChecks} tone="brand" />
            <Stat label="Open issues" value={minutes.open_issues.length} icon={CircleHelp} tone="warn" />
          </Reveal>
          <MinutesView minutes={minutes} />
          <MeetingExtras meeting={m} />
          <SharePanel meeting={m} emailEnabled={status.services.email.ok} />
          <Card title="Danger zone" description="Permanently remove the minutes, transcript and search index for this meeting.">
            <Button icon={Trash2} onClick={() => setConfirmDelete(true)} className="hover:border-bad/40 hover:text-bad">
              Delete meeting
            </Button>
          </Card>
        </>
      )}

      <ConfirmDialog
        open={confirmDelete}
        title={`Delete “${m.title}”?`}
        confirmLabel="Delete meeting"
        loading={remove.isPending}
        onConfirm={() => remove.mutate()}
        onCancel={() => setConfirmDelete(false)}
      >
        This permanently removes the minutes, transcript and chat search data. It can't be undone.
      </ConfirmDialog>
    </div>
  );
}
