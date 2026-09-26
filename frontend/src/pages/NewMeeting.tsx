import { useMutation, useQueryClient } from "@tanstack/react-query";
import { BookOpen, ClipboardPaste, FileText, Languages, Link as LinkIcon, Mic, ShieldCheck, Sparkles, Upload, type LucideIcon } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { useNavigate } from "react-router";
import { JobProgress } from "../components/JobProgress";
import { useToast } from "../components/Toaster";
import { Alert, Button, Card, Field, PageHeader, inputClass } from "../components/ui";
import { api } from "../lib/api";
import { cx, todayIso } from "../lib/format";
import { useJob, useModel } from "../lib/hooks";
import { Collapse, EASE, Stagger, StaggerItem } from "../lib/motion";
import type { AppStatus } from "../lib/types";

type Source = "recording" | "url" | "transcript_file" | "text";

const SOURCES: { id: Source; label: string; hint: string; icon: LucideIcon; needsTranscription?: boolean }[] = [
  { id: "recording", label: "Recording", hint: "Audio or video file", icon: Mic, needsTranscription: true },
  { id: "url", label: "Link", hint: "Public recording URL", icon: LinkIcon, needsTranscription: true },
  { id: "transcript_file", label: "Transcript file", hint: "TXT, VTT or SRT", icon: FileText },
  { id: "text", label: "Paste text", hint: "Type or paste", icon: ClipboardPaste },
];

const RECORDING_TYPES = ".mp3,.wav,.m4a,.mp4,.mov,.webm,.ogg,.flac,.aac,.mkv";
const TRANSCRIPT_TYPES = ".txt,.vtt,.srt,.md";

function StepCard({ step, title, description, children }: { step: number; title: string; description?: string; children: ReactNode }) {
  return (
    <Card>
      <div className="mb-5 flex items-start gap-3.5">
        <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-deep-gradient text-sm font-semibold text-white shadow-glow">
          {step}
        </span>
        <div>
          <h2 className="text-[15px] font-semibold tracking-tight">{title}</h2>
          {description && <p className="mt-0.5 text-sm text-subtle">{description}</p>}
        </div>
      </div>
      {children}
    </Card>
  );
}

function FileDrop({ file, accept, onFile, hint }: { file: File | null; accept: string; onFile: (file: File | null) => void; hint: string }) {
  const [dragging, setDragging] = useState(false);
  return (
    <motion.label
      animate={{ scale: dragging ? 1.015 : 1 }}
      transition={{ duration: 0.2 }}
      onDragOver={(e) => {
        e.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragging(false);
        onFile(e.dataTransfer.files[0] ?? null);
      }}
      className={cx(
        "group flex cursor-pointer flex-col items-center justify-center gap-3 rounded-2xl border-2 border-dashed px-6 py-10 text-center transition-colors duration-200",
        dragging ? "border-brand bg-brand-soft" : "border-line bg-sunken/40 hover:border-brand/50 hover:bg-brand-soft/40",
      )}
    >
      <motion.span
        animate={{ y: dragging ? -4 : 0 }}
        className={cx(
          "flex size-12 items-center justify-center rounded-2xl transition-colors",
          file ? "bg-good-soft text-good" : "bg-card text-brand shadow-card group-hover:shadow-glow",
        )}
      >
        {file ? <FileText className="size-6" /> : <Upload className="size-6" />}
      </motion.span>
      <AnimatePresence mode="wait">
        {file ? (
          <motion.span key="file" initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="font-medium break-all">
            {file.name} <span className="font-normal text-subtle">· {(file.size / 1024 / 1024).toFixed(1)} MB</span>
          </motion.span>
        ) : (
          <motion.span key="empty" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="text-sm">
            <span className="font-semibold text-brand">Choose a file</span> or drag it here
          </motion.span>
        )}
      </AnimatePresence>
      <span className="text-xs text-subtle">{hint}</span>
      <input type="file" accept={accept} className="sr-only" onChange={(e) => onFile(e.target.files?.[0] ?? null)} />
    </motion.label>
  );
}

function Switch({ checked, onChange, label, hint, icon: Icon }: { checked: boolean; onChange: (v: boolean) => void; label: string; hint?: string; icon?: LucideIcon }) {
  return (
    <label
      className={cx(
        "flex cursor-pointer items-center gap-3.5 rounded-xl border p-3.5 transition-colors duration-200",
        checked ? "border-brand/40 bg-brand-soft/60" : "border-line hover:bg-sunken/60",
      )}
    >
      {Icon && (
        <span className={cx("flex size-9 shrink-0 items-center justify-center rounded-lg transition-colors", checked ? "bg-brand text-brand-ink" : "bg-sunken text-subtle")}>
          <Icon className="size-[18px]" />
        </span>
      )}
      <span className="min-w-0 flex-1">
        <span className="block text-sm font-medium">{label}</span>
        {hint && <span className="block text-xs text-subtle">{hint}</span>}
      </span>
      <input type="checkbox" role="switch" checked={checked} onChange={(e) => onChange(e.target.checked)} className="peer sr-only" />
      <span
        aria-hidden
        className={cx(
          "relative h-6 w-11 shrink-0 rounded-full transition-colors duration-200 peer-focus-visible:ring-4 peer-focus-visible:ring-brand/20",
          checked ? "bg-brand" : "bg-line",
        )}
      >
        <motion.span
          className="absolute top-0.5 left-0.5 size-5 rounded-full bg-white shadow"
          animate={{ x: checked ? 20 : 0 }}
          transition={{ type: "spring", stiffness: 500, damping: 32 }}
        />
      </span>
    </label>
  );
}

export function NewMeeting({ status }: { status: AppStatus }) {
  const { model } = useModel();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const toast = useToast();
  const canTranscribe = status.services.transcription.ok;

  const [title, setTitle] = useState("");
  const [date, setDate] = useState(todayIso());
  const [source, setSource] = useState<Source>(canTranscribe ? "recording" : "text");
  const [file, setFile] = useState<File | null>(null);
  const [url, setUrl] = useState("");
  const [text, setText] = useState("");
  const [speakers, setSpeakers] = useState(0);
  const [detectLanguage, setDetectLanguage] = useState(true);
  const [redactPii, setRedactPii] = useState(false);
  const [showOptions, setShowOptions] = useState(false);
  const [factCheck, setFactCheck] = useState(false);
  const [research, setResearch] = useState(false);
  const [languages, setLanguages] = useState<string[]>([]);
  const [jobId, setJobId] = useState<string | null>(null);

  const start = useMutation({
    mutationFn: () => {
      const form = new FormData();
      Object.entries({
        title: title.trim(),
        meeting_date: date,
        source,
        url,
        text,
        speakers_expected: String(speakers),
        detect_language: String(detectLanguage),
        redact_pii: String(redactPii),
        fact_check: String(factCheck),
        research: String(research),
        languages: languages.join(","),
        model,
      }).forEach(([key, value]) => form.append(key, value));
      if (file && (source === "recording" || source === "transcript_file")) form.append("file", file);
      return api.createMeeting(form);
    },
    onSuccess: ({ job_id }) => {
      setJobId(job_id);
      window.scrollTo({ top: 0, behavior: "smooth" });
    },
  });

  const job = useJob<{ meeting_id: string }>(jobId);
  const meetingId = job.data?.status === "done" ? job.data.result?.meeting_id : null;
  useEffect(() => {
    if (meetingId) {
      queryClient.invalidateQueries({ queryKey: ["meetings"] });
      queryClient.invalidateQueries({ queryKey: ["action-items"] });
      toast("success", "Minutes ready", title);
      navigate(`/meetings/${meetingId}`);
    }
  }, [meetingId, navigate, queryClient, toast, title]);

  const steps = 5 + Number(factCheck) + Number(research) + languages.length;
  const isRecording = source === "recording" || source === "url";
  const inputMissing = source === "recording" || source === "transcript_file" ? !file : source === "url" ? !url.trim() : !text.trim();

  const submit = (e: FormEvent) => {
    e.preventDefault();
    start.mutate();
  };

  if (jobId) {
    const failed = job.data?.status === "error";
    return (
      <div className="mx-auto max-w-2xl">
        <PageHeader eyebrow="Working on it" title={title} description="The agents are reading your meeting. You can stay here and watch each step finish." />
        <JobProgress job={job.data} title="Generating minutes…" />
        {job.isError && <Alert tone="error" className="mt-4">{job.error.message}</Alert>}
        {(failed || job.isError) && (
          <Button className="mt-4" onClick={() => setJobId(null)}>
            Back to the form
          </Button>
        )}
      </div>
    );
  }

  return (
    <form onSubmit={submit} className="mx-auto max-w-3xl">
      <PageHeader eyebrow="Create" title="New meeting" description="Turn a recording or transcript into structured minutes in a few minutes." />

      <Stagger className="space-y-5">
        <StaggerItem>
          <StepCard step={1} title="Meeting details">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-[minmax(0,1fr)_13rem]">
              <Field label="Meeting title">
                <input required className={inputClass} value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Q3 budget review" />
              </Field>
              <Field label="Meeting date">
                <input required type="date" className={inputClass} value={date} onChange={(e) => setDate(e.target.value)} />
              </Field>
            </div>
          </StepCard>
        </StaggerItem>

        <StaggerItem>
          <StepCard step={2} title="Source" description="Where should the minutes come from?">
            <div className="mb-5 grid grid-cols-2 gap-2.5 sm:grid-cols-4" role="radiogroup" aria-label="Source">
              {SOURCES.map(({ id, label, hint, icon: Icon, needsTranscription }) => {
                const disabled = needsTranscription && !canTranscribe;
                const active = source === id;
                return (
                  <button
                    key={id}
                    type="button"
                    role="radio"
                    aria-checked={active}
                    disabled={disabled}
                    title={disabled ? "Needs ASSEMBLYAI_API_KEY" : undefined}
                    onClick={() => {
                      setSource(id);
                      setFile(null);
                    }}
                    className={cx(
                      "relative flex flex-col items-center gap-1.5 rounded-xl border px-3 py-4 text-center transition duration-200 disabled:cursor-not-allowed disabled:opacity-40",
                      active ? "border-brand/50 text-brand" : "border-line hover:-translate-y-0.5 hover:border-brand/30 hover:shadow-card",
                    )}
                  >
                    {active && (
                      <motion.span layoutId="source-active" className="absolute inset-0 rounded-xl bg-brand-soft" transition={{ type: "spring", stiffness: 420, damping: 34 }} />
                    )}
                    <Icon className="relative size-5" />
                    <span className="relative text-sm font-semibold">{label}</span>
                    <span className={cx("relative text-[11px]", active ? "text-brand/80" : "text-subtle")}>{hint}</span>
                  </button>
                );
              })}
            </div>

            <AnimatePresence mode="wait" initial={false}>
              <motion.div
                key={source}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.22, ease: EASE }}
              >
                {source === "recording" && <FileDrop file={file} accept={RECORDING_TYPES} onFile={setFile} hint="MP3, WAV, M4A, MP4, MOV, WEBM, OGG, FLAC and more" />}
                {source === "url" && (
                  <Field label="Public link to the recording" hint="A direct download link to an audio or video file">
                    <input type="url" className={inputClass} value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://…" />
                  </Field>
                )}
                {source === "transcript_file" && (
                  <FileDrop file={file} accept={TRANSCRIPT_TYPES} onFile={setFile} hint="Zoom and Teams .vtt exports keep speaker names" />
                )}
                {source === "text" && (
                  <Field label="Transcript" hint="Lines like “Priya: …” or “[00:12] Speaker A: …” keep speakers and timestamps">
                    <textarea
                      rows={10}
                      className={cx(inputClass, "font-mono text-[13px] leading-relaxed")}
                      value={text}
                      onChange={(e) => setText(e.target.value)}
                      placeholder={"Priya: Let's start with the budget...\nRavi: Sure, the numbers are..."}
                    />
                  </Field>
                )}
              </motion.div>
            </AnimatePresence>
            {!canTranscribe && <p className="mt-3 text-xs text-subtle">Recordings need ASSEMBLYAI_API_KEY; transcripts work without it.</p>}

            {isRecording && (
              <div className="mt-4 rounded-xl border border-line">
                <button
                  type="button"
                  onClick={() => setShowOptions(!showOptions)}
                  aria-expanded={showOptions}
                  className="flex w-full items-center justify-between px-4 py-3 text-sm font-medium"
                >
                  Transcription options
                  <motion.span animate={{ rotate: showOptions ? 45 : 0 }} className="text-lg leading-none text-subtle">
                    +
                  </motion.span>
                </button>
                <Collapse open={showOptions}>
                  <div className="space-y-3 border-t border-line p-4">
                    <Field label="Number of speakers" hint="0 = detect automatically" className="max-w-44">
                      <input type="number" min={0} max={30} className={inputClass} value={speakers} onChange={(e) => setSpeakers(Number(e.target.value))} />
                    </Field>
                    <Switch checked={detectLanguage} onChange={setDetectLanguage} label="Detect the spoken language" />
                    <Switch checked={redactPii} onChange={setRedactPii} label="Redact personal data" hint="Phone numbers, emails, card and ID numbers" />
                  </div>
                </Collapse>
              </div>
            )}
          </StepCard>
        </StaggerItem>

        <StaggerItem>
          <StepCard step={3} title="AI agents" description="The core minutes are always produced. Add extra agents if you need them.">
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <Switch checked={factCheck} onChange={setFactCheck} icon={ShieldCheck} label="Fact-checker" hint="Verify claims against Wikipedia" />
              <Switch checked={research} onChange={setResearch} icon={BookOpen} label="Researcher" hint="Sourced background on topics" />
            </div>
            <div className="mt-5">
              <div className="mb-2.5 flex items-center gap-2 text-sm font-medium">
                <Languages className="size-4 text-brand" /> Translator <span className="font-normal text-subtle">· also produce the minutes in</span>
              </div>
              <div className="flex flex-wrap gap-2">
                {status.languages.map((language) => {
                  const on = languages.includes(language);
                  return (
                    <motion.button
                      key={language}
                      type="button"
                      whileTap={{ scale: 0.94 }}
                      aria-pressed={on}
                      onClick={() => setLanguages(on ? languages.filter((l) => l !== language) : [...languages, language])}
                      className={cx(
                        "rounded-full border px-3.5 py-1.5 text-sm transition-colors duration-200",
                        on ? "border-transparent bg-deep-gradient text-white shadow-glow" : "border-line hover:border-brand/40 hover:bg-sunken",
                      )}
                    >
                      {language}
                    </motion.button>
                  );
                })}
              </div>
            </div>
          </StepCard>
        </StaggerItem>
      </Stagger>

      {start.isError && <Alert tone="error" className="mt-5">{start.error.message}</Alert>}

      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: EASE, delay: 0.25 }}
        className="glass sticky bottom-4 z-10 mt-6 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-line p-3 pl-5 shadow-pop"
      >
        <p className="text-sm text-subtle">
          <span className="font-semibold text-ink">{steps} AI steps</span> with {model} · usually a few minutes on the free tier
        </p>
        <Button type="submit" variant="primary" size="lg" icon={Sparkles} loading={start.isPending} disabled={!title.trim() || inputMissing}>
          Generate minutes
        </Button>
      </motion.div>
    </form>
  );
}
