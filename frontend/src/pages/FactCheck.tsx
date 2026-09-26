import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, ClipboardCheck, Search, SearchX, ShieldCheck } from "lucide-react";
import { motion } from "motion/react";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { JobProgress } from "../components/JobProgress";
import { ClaimList } from "../components/MeetingExtras";
import { MeetingPicker, MeetingsGate, useSelectedMeeting } from "../components/MeetingPicker";
import { useToast } from "../components/Toaster";
import { Alert, Badge, Button, CLAIM_TONE, PageHeader, Skeleton } from "../components/ui";
import { api } from "../lib/api";
import { cx, plural } from "../lib/format";
import { useJob, useModel } from "../lib/hooks";
import { EASE, Reveal } from "../lib/motion";
import type { CheckedClaim, Claim, ClaimStatus, MeetingSummary } from "../lib/types";

const CLAIM_STATUSES: ClaimStatus[] = ["Verified", "Partially verified", "Refuted", "Unverifiable"];

function StepCard({ step, title, description, actions, children }: { step: number; title: string; description: string; actions?: ReactNode; children?: ReactNode }) {
  return (
    <section className="rounded-2xl border border-line bg-card p-5 shadow-card sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex min-w-0 items-start gap-3.5">
          <span className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-deep-gradient text-sm font-semibold text-white shadow-glow">{step}</span>
          <div className="min-w-0">
            <h2 className="text-[15px] font-semibold tracking-tight">{title}</h2>
            <p className="mt-0.5 text-sm text-subtle">{description}</p>
          </div>
        </div>
        {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
      </div>
      {children && <div className="mt-5 space-y-4 empty:hidden">{children}</div>}
    </section>
  );
}

function ClaimOption({ claim, index, checked, onToggle }: { claim: Claim; index: number; checked: boolean; onToggle: () => void }) {
  return (
    <motion.li initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35, delay: index * 0.05, ease: EASE }}>
      <label
        className={cx(
          "flex cursor-pointer items-start gap-3 rounded-xl border p-3.5 transition duration-200",
          checked ? "border-brand/40 bg-brand-soft/60 shadow-card" : "border-line hover:border-brand/25 hover:bg-sunken/50",
        )}
      >
        <input type="checkbox" className="peer sr-only" checked={checked} onChange={onToggle} />
        <span
          className={cx(
            "mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-md border transition duration-200 peer-focus-visible:ring-4 peer-focus-visible:ring-brand/20",
            checked ? "border-transparent bg-brand-gradient text-white" : "border-subtle/50 bg-card",
          )}
        >
          <motion.span initial={false} animate={{ scale: checked ? 1 : 0, opacity: checked ? 1 : 0 }} transition={{ type: "spring", stiffness: 500, damping: 28 }}>
            <Check className="size-3.5" strokeWidth={3} />
          </motion.span>
        </span>
        <span className="min-w-0 text-sm leading-relaxed">
          {claim.claim}
          {claim.speaker && <span className="mt-0.5 block text-xs text-subtle">Said by {claim.speaker}</span>}
        </span>
      </label>
    </motion.li>
  );
}

function ResultsSummary({ claims }: { claims: CheckedClaim[] }) {
  const counts = CLAIM_STATUSES.map((status) => [status, claims.filter((c) => c.status === status).length] as const).filter(([, n]) => n > 0);
  if (!counts.length) return null;
  return (
    <div className="mb-4 flex flex-wrap gap-2">
      {counts.map(([status, n]) => (
        <Badge key={status} tone={CLAIM_TONE[status]} dot>
          {n} {status.toLowerCase()}
        </Badge>
      ))}
    </div>
  );
}

function FactCheckPanel({ summary }: { summary: MeetingSummary }) {
  const { model } = useModel();
  const toast = useToast();
  const queryClient = useQueryClient();
  const meeting = useQuery({ queryKey: ["meeting", summary.id], queryFn: () => api.meeting(summary.id) });
  const [findJobId, setFindJobId] = useState<string | null>(null);
  const [verifyJobId, setVerifyJobId] = useState<string | null>(null);
  const [selected, setSelected] = useState<Set<number>>(new Set());

  const find = useMutation({ mutationFn: () => api.findClaims(summary.id, model), onSuccess: ({ job_id }) => setFindJobId(job_id) });
  const findJob = useJob<{ claims: Claim[] }>(findJobId);
  const findResult = findJob.data?.status === "done" ? findJob.data.result : null;
  const claims = useMemo(() => (findResult ? findResult.claims ?? [] : null), [findResult]);

  useEffect(() => {
    if (claims) setSelected(new Set(claims.slice(0, 3).map((_, i) => i)));
  }, [claims]);

  const verify = useMutation({
    mutationFn: () => api.verifyClaims(summary.id, (claims ?? []).filter((_, i) => selected.has(i)), model),
    onSuccess: ({ job_id }) => setVerifyJobId(job_id),
  });
  const verifyJob = useJob<{ fact_check: { claims: unknown[] } }>(verifyJobId);
  const verifyDone = verifyJob.data?.status === "done";
  useEffect(() => {
    if (!verifyDone) return;
    queryClient.invalidateQueries({ queryKey: ["meeting", summary.id] });
    toast("success", "Fact check complete", "Results are saved with the meeting");
  }, [verifyDone, queryClient, summary.id, toast]);

  const toggle = (index: number) =>
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(index)) next.delete(index);
      else next.add(index);
      return next;
    });

  const findRunning = Boolean(find.isPending || findJob.data?.status === "running" || (findJobId && !findJob.data));
  const verifyRunning = Boolean(verify.isPending || verifyJob.data?.status === "running" || (verifyJobId && !verifyJob.data));
  const results = meeting.data?.fact_check?.claims ?? [];

  return (
    <div className="space-y-5">
      <Reveal>
        <StepCard
          step={1}
          title="Find factual claims"
          description="Reads the transcript for checkable statements: statistics, dates, public facts."
          actions={
            <Button variant={claims ? "secondary" : "primary"} icon={Search} loading={findRunning} onClick={() => find.mutate()} disabled={verifyRunning}>
              {claims ? "Find again" : "Find claims"}
            </Button>
          }
        >
          {find.isError && <Alert tone="error">{find.error.message}</Alert>}
          {findJobId && findJob.data?.status !== "done" && <JobProgress job={findJob.data} title="Finding claims…" />}
          {claims && claims.length === 0 && (
            <div className="flex items-center gap-3 rounded-xl bg-sunken p-4 text-sm text-subtle">
              <SearchX className="size-5 shrink-0" /> No checkable factual claims were found in this meeting.
            </div>
          )}
        </StepCard>
      </Reveal>

      {claims && claims.length > 0 && (
        <Reveal>
          <StepCard step={2} title="Choose what to verify" description={`${plural(claims.length, "claim")} found. Each one is checked against Wikipedia.`}>
            <fieldset>
              <legend className="sr-only">Claims to verify</legend>
              <div className="mb-3 flex gap-3 text-xs font-medium">
                <button type="button" className="text-brand hover:underline" onClick={() => setSelected(new Set(claims.map((_, i) => i)))}>
                  Select all
                </button>
                <button type="button" className="text-subtle hover:text-ink hover:underline" onClick={() => setSelected(new Set())}>
                  Clear
                </button>
              </div>
              <ul className="space-y-2">
                {claims.map((claim, index) => (
                  <ClaimOption key={index} claim={claim} index={index} checked={selected.has(index)} onToggle={() => toggle(index)} />
                ))}
              </ul>
              <Button className="mt-5" variant="primary" icon={ShieldCheck} loading={verifyRunning} disabled={selected.size === 0} onClick={() => verify.mutate()}>
                Verify {plural(selected.size, "claim")}
              </Button>
            </fieldset>
            {verify.isError && <Alert tone="error">{verify.error.message}</Alert>}
            {verifyJobId && <JobProgress job={verifyJob.data} title="Verifying claims against Wikipedia…" />}
          </StepCard>
        </Reveal>
      )}

      <Reveal delay={0.05}>
        <section className="rounded-2xl border border-line bg-card p-5 shadow-card sm:p-6">
          <div className="mb-5 flex items-center gap-3">
            <span className="flex size-9 items-center justify-center rounded-xl bg-good-soft text-good">
              <ClipboardCheck className="size-[18px]" />
            </span>
            <div>
              <h2 className="text-[15px] font-semibold tracking-tight">Results</h2>
              <p className="mt-0.5 text-sm text-subtle">Saved with the meeting and included in exports.</p>
            </div>
          </div>
          {meeting.isPending ? (
            <div className="space-y-3">
              <Skeleton className="h-24 rounded-xl" />
              <Skeleton className="h-24 rounded-xl" />
            </div>
          ) : meeting.isError ? (
            <Alert tone="error">{meeting.error.message}</Alert>
          ) : (
            <>
              <ResultsSummary claims={results} />
              <ClaimList claims={results} />
            </>
          )}
        </section>
      </Reveal>
    </div>
  );
}

export function FactCheck() {
  const { meetings, selected, select } = useSelectedMeeting();
  return (
    <div>
      <PageHeader eyebrow="Verification" title="Fact check" description="Find factual claims in a meeting and verify the ones you choose against Wikipedia." />
      <MeetingsGate query={meetings}>
        <div className="mb-6">
          <MeetingPicker meetings={meetings.data ?? []} selected={selected} onSelect={select} />
        </div>
        {selected && <FactCheckPanel key={selected.id} summary={selected} />}
      </MeetingsGate>
    </div>
  );
}
