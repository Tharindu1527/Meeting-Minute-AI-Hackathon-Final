import { useMutation, useQuery } from "@tanstack/react-query";
import { AudioLines, Download, FileText, Headphones, Languages, Mic2 } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useState } from "react";
import { MeetingPicker, MeetingsGate, useSelectedMeeting } from "../components/MeetingPicker";
import { useToast } from "../components/Toaster";
import { Alert, Card, Field, PageHeader, Skeleton, inputClass } from "../components/ui";
import { api } from "../lib/api";
import { cx, downloadBlob, fileSlug, titleCase } from "../lib/format";
import { useObjectUrl } from "../lib/hooks";
import { EASE, Reveal } from "../lib/motion";
import type { AppStatus, MeetingSummary } from "../lib/types";

const BARS = [0.45, 0.8, 0.55, 1, 0.7, 0.4, 0.9, 0.6, 0.75, 0.5, 0.95, 0.65, 0.35, 0.85, 0.55, 0.7, 0.45, 0.9, 0.6, 0.4];

/** Decorative equaliser that moves while audio is playing or being generated */
function Waveform({ active }: { active: boolean }) {
  return (
    <div aria-hidden className="flex h-14 items-center gap-[3px]">
      {BARS.map((height, i) => (
        <motion.span
          key={i}
          className="w-1.5 rounded-full bg-white/80"
          style={{ height: `${height * 100}%`, originY: 0.5 }}
          animate={active ? { scaleY: [height, 0.25, 1, height * 0.6, height] } : { scaleY: 0.25 + height * 0.25 }}
          transition={active ? { duration: 1.1 + (i % 4) * 0.15, repeat: Infinity, ease: "easeInOut", delay: i * 0.04 } : { duration: 0.4, ease: EASE }}
        />
      ))}
    </div>
  );
}

function ListenPanel({ summary, voices }: { summary: MeetingSummary; voices: string[] }) {
  const toast = useToast();
  const meeting = useQuery({ queryKey: ["meeting", summary.id], queryFn: () => api.meeting(summary.id) });
  const [language, setLanguage] = useState("");
  const [voice, setVoice] = useState(voices[0]);
  const [playing, setPlaying] = useState(false);
  const script = useQuery({
    queryKey: ["speech-script", summary.id, language],
    queryFn: () => api.speechScript(summary.id, language || null),
  });
  const speak = useMutation({
    mutationFn: () => api.speech(summary.id, language || null, voice),
    onSuccess: () => toast("success", "Audio ready", "Press play to listen"),
    onError: (e) => toast("error", "Could not generate audio", e.message),
  });
  const audioUrl = useObjectUrl(speak.data ?? null);

  const translations = Object.keys(meeting.data?.translations ?? {});
  const paragraphs = script.data?.script.split(/\n\s*\n/) ?? [];
  const words = script.data?.script.split(/\s+/).filter(Boolean).length ?? 0;
  const reset = () => {
    speak.reset();
    setPlaying(false);
  };

  return (
    <div className="space-y-5">
      <Reveal>
        <div className="relative overflow-hidden rounded-3xl bg-deep-gradient p-6 text-white shadow-glow sm:p-8">
          <div className="pointer-events-none absolute -top-20 -right-10 size-64 rounded-full bg-white/15 blur-3xl" />
          <div className="pointer-events-none absolute -bottom-24 -left-10 size-64 rounded-full bg-black/10 blur-3xl" />
          <div className="relative flex flex-wrap items-center justify-between gap-6">
            <div className="min-w-0">
              <div className="flex items-center gap-2 text-xs font-semibold tracking-[0.14em] text-white/75 uppercase">
                <AudioLines className="size-4" /> Audio briefing
              </div>
              <h2 className="mt-2 text-xl font-semibold tracking-tight sm:text-2xl">{summary.title}</h2>
              <p className="mt-1 text-sm text-white/75">
                {language ? titleCase(language) : "Original language"} · {voice}
                {words > 0 && ` · about ${Math.max(1, Math.round(words / 150))} min`}
              </p>
            </div>
            <Waveform active={playing || speak.isPending} />
          </div>

          <div className="relative mt-6">
            <AnimatePresence mode="wait" initial={false}>
              {audioUrl && speak.data ? (
                <motion.div
                  key="player"
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -8 }}
                  transition={{ duration: 0.3, ease: EASE }}
                  className="flex flex-wrap items-center gap-3"
                >
                  <audio
                    controls
                    src={audioUrl}
                    className="h-11 min-w-0 flex-1 rounded-full"
                    onPlay={() => setPlaying(true)}
                    onPause={() => setPlaying(false)}
                    onEnded={() => setPlaying(false)}
                  />
                  <button
                    type="button"
                    onClick={() => downloadBlob(speak.data, `${fileSlug(summary.title, summary.meeting_date)}-${language || "original"}.wav`)}
                    className="inline-flex h-10 items-center gap-2 rounded-xl bg-white/15 px-4 text-sm font-medium backdrop-blur transition hover:bg-white/25 active:scale-[0.97]"
                  >
                    <Download className="size-4" /> Download .wav
                  </button>
                </motion.div>
              ) : (
                <motion.div
                  key="generate"
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -8 }}
                  transition={{ duration: 0.3, ease: EASE }}
                  className="flex flex-wrap items-center gap-3"
                >
                  <button
                    type="button"
                    disabled={!script.data || speak.isPending}
                    onClick={() => speak.mutate()}
                    className="inline-flex h-11 items-center gap-2 rounded-xl bg-white px-5 text-sm font-semibold text-[#4f46e5] shadow-lg transition hover:bg-white/90 active:scale-[0.97] disabled:opacity-60"
                  >
                    <Headphones className={cx("size-4", speak.isPending && "animate-pulse")} />
                    {speak.isPending ? "Generating speech…" : "Generate audio"}
                  </button>
                  {speak.isPending && <span className="text-sm text-white/80">Longer minutes take a little while.</span>}
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>
      </Reveal>

      {speak.isError && <Alert tone="error">{speak.error.message}</Alert>}

      <Reveal delay={0.05}>
        <Card title="Voice & language" icon={Mic2} description="Changing either one clears the current audio.">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Field label="Language">
              <select
                className={inputClass}
                value={language}
                onChange={(e) => {
                  setLanguage(e.target.value);
                  reset();
                }}
              >
                <option value="">Original</option>
                {translations.map((t) => (
                  <option key={t} value={t}>
                    {titleCase(t)}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Voice">
              <select
                className={inputClass}
                value={voice}
                onChange={(e) => {
                  setVoice(e.target.value);
                  reset();
                }}
              >
                {voices.map((v) => (
                  <option key={v}>{v}</option>
                ))}
              </select>
            </Field>
          </div>
          {translations.length === 0 && meeting.isSuccess && (
            <p className="mt-3 flex items-center gap-1.5 text-xs text-subtle">
              <Languages className="size-3.5" /> Translate the minutes when creating a meeting to listen in other languages.
            </p>
          )}
        </Card>
      </Reveal>

      <Reveal delay={0.1}>
        <Card title="What will be read" icon={FileText}>
          {script.isPending ? (
            <div className="space-y-2.5">
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-11/12" />
              <Skeleton className="h-4 w-4/5" />
              <Skeleton className="h-4 w-2/3" />
            </div>
          ) : script.isError ? (
            <Alert tone="error">{script.error.message}</Alert>
          ) : (
            <motion.div
              key={language}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.3 }}
              className="relative max-h-72 space-y-3 overflow-y-auto pr-1 text-sm leading-relaxed"
            >
              {paragraphs.map((p, i) => (
                <p key={i} className={cx(i === 0 && "font-medium")}>
                  {p}
                </p>
              ))}
            </motion.div>
          )}
        </Card>
      </Reveal>
    </div>
  );
}

export function Listen({ status }: { status: AppStatus }) {
  const { meetings, selected, select } = useSelectedMeeting();
  return (
    <div>
      <PageHeader eyebrow="Audio" title="Listen to the minutes" description="An audio version of the summary, decisions and action items." />
      <MeetingsGate query={meetings}>
        <div className="mb-6">
          <MeetingPicker meetings={meetings.data ?? []} selected={selected} onSelect={select} />
        </div>
        {selected && <ListenPanel key={selected.id} summary={selected} voices={status.voices} />}
      </MeetingsGate>
    </div>
  );
}
