import { BookOpen, ChevronDown, ExternalLink, Globe, ScrollText, ShieldCheck, Smile, type LucideIcon } from "lucide-react";
import { motion } from "motion/react";
import { useState, type ReactNode } from "react";
import { cx, formatTimestamp, titleCase } from "../lib/format";
import { Collapse, EASE, Stagger, StaggerItem } from "../lib/motion";
import type { CheckedClaim, Meeting } from "../lib/types";
import { Avatar } from "./MinutesView";
import { Badge, CLAIM_TONE, IconTile } from "./ui";

function Section({ title, icon, badge, children }: { title: string; icon: LucideIcon; badge?: ReactNode; children: ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <div className={cx("rounded-2xl border bg-card shadow-card transition-colors duration-300", open ? "border-brand/30" : "border-line")}>
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen(!open)}
        className="flex w-full items-center gap-3 rounded-2xl px-5 py-4 text-left transition hover:bg-sunken/40 sm:px-6"
      >
        <IconTile icon={icon} />
        <span className="flex min-w-0 flex-1 flex-wrap items-center gap-x-3 gap-y-1">
          <span className="font-semibold">{title}</span>
          {badge}
        </span>
        <motion.span className="shrink-0 text-subtle"animate={{ rotate: open ? 180 : 0 }} transition={{ duration: 0.3, ease: EASE }}>
          <ChevronDown className="size-5" />
        </motion.span>
      </button>
      <Collapse open={open}>
        <div className="border-t border-line px-5 py-5 sm:px-6">{children}</div>
      </Collapse>
    </div>
  );
}

function Sources({ sources }: { sources: string[] }) {
  if (!sources.length) return null;
  return (
    <div className="mt-2 flex flex-wrap gap-2 text-xs">
      {sources.map((source) =>
        source.startsWith("http") ? (
          <a
            key={source}
            href={source}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1 rounded-full bg-sunken px-2.5 py-1 text-brand transition hover:bg-brand-soft"
          >
            {decodeURIComponent(source.replace(/^https?:\/\/(www\.)?/, "")).slice(0, 48)}
            <ExternalLink className="size-3" />
          </a>
        ) : (
          <span key={source} className="rounded-full bg-sunken px-2.5 py-1 text-subtle">
            {source}
          </span>
        ),
      )}
    </div>
  );
}

export function ClaimList({ claims }: { claims: CheckedClaim[] }) {
  if (!claims.length) return <p className="text-sm text-subtle">No claims have been checked yet.</p>;
  return (
    <Stagger as="ul" className="space-y-3">
      {claims.map((claim, i) => (
        <StaggerItem as="li" key={`${i}-${claim.claim}`}>
          <div className="rounded-xl border border-line bg-sunken/40 p-4">
            <div className="flex flex-wrap items-start gap-2">
              <Badge tone={CLAIM_TONE[claim.status]} dot>
                {claim.status}
              </Badge>
              <span className="font-medium">{claim.claim}</span>
            </div>
            {claim.speaker && <div className="mt-1 text-xs text-subtle">Said by {claim.speaker}</div>}
            <p className="mt-2 text-sm leading-relaxed text-subtle">{claim.explanation}</p>
            <Sources sources={claim.sources} />
          </div>
        </StaggerItem>
      ))}
    </Stagger>
  );
}

function Translations({ translations }: { translations: Meeting["translations"] }) {
  const languages = Object.keys(translations);
  const [active, setActive] = useState(languages[0]);
  const content = translations[active];
  return (
    <div>
      <div className="mb-4 inline-flex flex-wrap gap-1 rounded-xl bg-sunken p-1">
        {languages.map((language) => (
          <button
            key={language}
            type="button"
            onClick={() => setActive(language)}
            className={cx("relative rounded-lg px-3.5 py-1.5 text-sm font-medium transition", language === active ? "text-ink" : "text-subtle hover:text-ink")}
          >
            {language === active && (
              <motion.span layoutId="translation-tab" className="absolute inset-0 rounded-lg bg-card shadow-card" transition={{ type: "spring", stiffness: 420, damping: 34 }} />
            )}
            <span className="relative">{titleCase(language)}</span>
          </button>
        ))}
      </div>
      {content && (
        <motion.div key={active} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3, ease: EASE }} className="space-y-4">
          <p className="leading-relaxed">{content.summary}</p>
          {content.decisions.length > 0 && (
            <div>
              <div className="mb-1 text-sm font-semibold">Decisions</div>
              <ul className="list-disc space-y-1 pl-5">{content.decisions.map((d, i) => <li key={i}>{d}</li>)}</ul>
            </div>
          )}
          {content.action_items.length > 0 && (
            <div>
              <div className="mb-1 text-sm font-semibold">Action items</div>
              <ul className="list-disc space-y-1 pl-5">{content.action_items.map((a, i) => <li key={i}>{a}</li>)}</ul>
            </div>
          )}
        </motion.div>
      )}
    </div>
  );
}

export function MeetingExtras({ meeting }: { meeting: Meeting }) {
  const sentiment = meeting.minutes.sentiment;
  const claims = meeting.fact_check?.claims ?? [];
  const insights = meeting.research?.insights ?? [];
  const translations = meeting.translations ?? {};
  const transcript = meeting.transcript;

  return (
    <div className="space-y-3">
      {sentiment && (
        <Section title="Tone & dynamics" icon={Smile} badge={<Badge tone="brand"><span className="truncate">{sentiment.overall_tone}</span></Badge>}>
          <p className="leading-relaxed">{sentiment.summary}</p>
          {sentiment.per_speaker.length > 0 && (
            <ul className="mt-5 grid grid-cols-1 gap-3 sm:grid-cols-2">
              {sentiment.per_speaker.map((s, i) => (
                <li key={i} className="flex gap-3 rounded-xl border border-line p-3">
                  <Avatar name={s.speaker} />
                  <div className="min-w-0 text-sm">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-medium">{s.speaker}</span>
                      <Badge>{s.tone}</Badge>
                    </div>
                    <div className="mt-1 text-subtle">{s.notes}</div>
                  </div>
                </li>
              ))}
            </ul>
          )}
          <div className="mt-5 grid grid-cols-1 gap-4 sm:grid-cols-2">
            {sentiment.agreements.length > 0 && (
              <div className="rounded-xl bg-good-soft/60 p-4">
                <div className="mb-1.5 text-sm font-semibold text-good">Agreement</div>
                <ul className="list-disc space-y-1 pl-5 text-sm">{sentiment.agreements.map((a, i) => <li key={i}>{a}</li>)}</ul>
              </div>
            )}
            {sentiment.disagreements.length > 0 && (
              <div className="rounded-xl bg-bad-soft/60 p-4">
                <div className="mb-1.5 text-sm font-semibold text-bad">Disagreement</div>
                <ul className="list-disc space-y-1 pl-5 text-sm">{sentiment.disagreements.map((d, i) => <li key={i}>{d}</li>)}</ul>
              </div>
            )}
          </div>
        </Section>
      )}

      {claims.length > 0 && (
        <Section title="Fact check" icon={ShieldCheck} badge={<Badge>{claims.length}</Badge>}>
          <ClaimList claims={claims} />
        </Section>
      )}

      {insights.length > 0 && (
        <Section title="Background research" icon={BookOpen} badge={<Badge>{insights.length}</Badge>}>
          <ul className="space-y-5">
            {insights.map((insight, i) => (
              <li key={i}>
                <div className="font-semibold">{insight.topic}</div>
                <p className="mt-1 text-sm leading-relaxed">{insight.background}</p>
                <p className="mt-1.5 text-sm text-subtle">
                  <span className="font-medium text-ink">Why it matters:</span> {insight.relevance}
                </p>
                <Sources sources={insight.sources} />
              </li>
            ))}
          </ul>
        </Section>
      )}

      {Object.keys(translations).length > 0 && (
        <Section title="Translations" icon={Globe} badge={<Badge>{Object.keys(translations).length}</Badge>}>
          <Translations translations={translations} />
        </Section>
      )}

      {transcript?.utterances?.length > 0 && (
        <Section title="Transcript" icon={ScrollText} badge={<Badge>{transcript.utterances.length} lines</Badge>}>
          {transcript.truncated && (
            <p className="mb-3 text-sm text-warn">This transcript was longer than the AI's input limit; only the first part was analysed.</p>
          )}
          <div className="max-h-[30rem] space-y-3 overflow-y-auto pr-2 text-sm">
            {transcript.utterances.map((u, i) => (
              <div key={i} className="flex gap-3">
                {u.start_ms != null && (
                  <span className="mt-0.5 w-12 shrink-0 font-mono text-[11px] text-subtle tabular-nums">{formatTimestamp(u.start_ms)}</span>
                )}
                <p className="leading-relaxed">
                  {u.speaker && <span className="mr-1.5 font-semibold text-brand">{u.speaker}</span>}
                  {u.text}
                </p>
              </div>
            ))}
          </div>
        </Section>
      )}
    </div>
  );
}
