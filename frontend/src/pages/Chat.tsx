import { useMutation, useQuery } from "@tanstack/react-query";
import { ArrowUp, Bot, Files, MessagesSquare, Quote, Trash2, User, Volume2 } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { Link, useSearchParams } from "react-router";
import { Alert, Button, EmptyState, Field, PageHeader, Skeleton, inputClass } from "../components/ui";
import { api } from "../lib/api";
import { cx, formatDate, formatTimestamp } from "../lib/format";
import { useModel } from "../lib/hooks";
import { Collapse, EASE } from "../lib/motion";
import type { AppStatus, ChatMessage } from "../lib/types";

const ALL = "all";

const SUGGESTIONS = [
  "What did we decide, and why?",
  "Who owns which action items, and when are they due?",
  "What questions are still open?",
  "Summarise the disagreements.",
];

function AssistantAudio({ text, voice }: { text: string; voice: string }) {
  const [url, setUrl] = useState<string | null>(null);
  const speak = useMutation({
    mutationFn: () => api.tts(text, voice),
    onSuccess: (blob) => setUrl(URL.createObjectURL(blob)),
  });
  useEffect(
    () => () => {
      if (url) URL.revokeObjectURL(url);
    },
    [url],
  );

  if (url) return <motion.audio initial={{ opacity: 0 }} animate={{ opacity: 1 }} controls autoPlay src={url} className="mt-3 h-9 w-full max-w-sm" />;
  return (
    <div className="mt-2">
      <Button size="sm" variant="ghost" icon={Volume2} loading={speak.isPending} onClick={() => speak.mutate()} className="-ml-2">
        Listen
      </Button>
      {speak.isError && <p className="mt-1 text-xs text-bad">{speak.error.message}</p>}
    </div>
  );
}

function Sources({ sources }: { sources: NonNullable<ChatMessage["sources"]> }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="mt-3 border-t border-line pt-2.5">
      <button type="button" onClick={() => setOpen(!open)} className="flex items-center gap-1.5 text-xs font-medium text-subtle transition hover:text-brand">
        <Quote className="size-3.5" />
        {open ? "Hide" : "Show"} {sources.length} transcript excerpt{sources.length === 1 ? "" : "s"}
      </button>
      <Collapse open={open}>
        <ul className="mt-2.5 space-y-2">
          {sources.map((source, i) => (
            <li key={i} className="rounded-xl bg-sunken p-3">
              <div className="text-[11px] font-semibold text-brand">
                {source.title}
                {source.start_ms != null && ` · ${formatTimestamp(source.start_ms)}`}
              </div>
              <p className="mt-1 line-clamp-4 text-xs leading-relaxed whitespace-pre-wrap text-subtle">{source.text}</p>
            </li>
          ))}
        </ul>
      </Collapse>
    </div>
  );
}

/** `**bold**` and `code` inside a line of an answer */
function Inline({ text }: { text: string }) {
  return (
    <>
      {text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g).map((part, i) =>
        part.startsWith("**") && part.endsWith("**") && part.length > 4 ? (
          <strong key={i} className="font-semibold">
            {part.slice(2, -2)}
          </strong>
        ) : part.startsWith("`") && part.endsWith("`") && part.length > 2 ? (
          <code key={i} className="rounded bg-sunken px-1 py-0.5 text-[0.9em]">
            {part.slice(1, -1)}
          </code>
        ) : (
          part
        ),
      )}
    </>
  );
}

/** The small subset of Markdown the model uses in answers: paragraphs, bullet and numbered lists, bold */
function RichText({ text }: { text: string }) {
  const blocks: { type: "p" | "ul" | "ol"; lines: string[] }[] = [];
  for (const raw of text.split("\n")) {
    const line = raw.trim();
    const bullet = line.match(/^[*\-•]\s+(.*)$/);
    const numbered = line.match(/^\d+[.)]\s+(.*)$/);
    const type = bullet ? "ul" : numbered ? "ol" : "p";
    const content = bullet?.[1] ?? numbered?.[1] ?? line.replace(/^#{1,6}\s+/, "");
    const last = blocks[blocks.length - 1];
    if (!line) blocks.push({ type: "p", lines: [] });
    else if (last && last.type === type && (type !== "p" || last.lines.length)) last.lines.push(content);
    else blocks.push({ type, lines: [content] });
  }
  return (
    <div className="space-y-2.5 leading-relaxed">
      {blocks
        .filter((block) => block.lines.length)
        .map((block, i) =>
          block.type === "p" ? (
            <p key={i}>
              {block.lines.map((line, j) => (
                <span key={j}>
                  {j > 0 && <br />}
                  <Inline text={line} />
                </span>
              ))}
            </p>
          ) : (
            <Dynamic key={i} as={block.type} className={cx("space-y-1.5 pl-5", block.type === "ul" ? "list-disc" : "list-decimal")}>
              {block.lines.map((line, j) => (
                <li key={j} className="pl-1 marker:text-brand">
                  <Inline text={line} />
                </li>
              ))}
            </Dynamic>
          ),
        )}
    </div>
  );
}

function Dynamic({ as: Tag, className, children }: { as: "ul" | "ol"; className: string; children: ReactNode }) {
  return <Tag className={className}>{children}</Tag>;
}

function Message({ message, voice }: { message: ChatMessage; voice: string }) {
  const isUser = message.role === "user";
  return (
    <motion.div
      initial={{ opacity: 0, y: 12, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.35, ease: EASE }}
      className={cx("flex gap-3", isUser && "flex-row-reverse")}
    >
      <div
        className={cx(
          "mt-1 flex size-8 shrink-0 items-center justify-center rounded-full",
          isUser ? "bg-sunken text-subtle" : "bg-brand-gradient text-white shadow-glow",
        )}
      >
        {isUser ? <User className="size-4" /> : <Bot className="size-4" />}
      </div>
      <div
        className={cx(
          "max-w-[85%] rounded-2xl px-4 py-3",
          isUser ? "rounded-tr-md bg-deep-gradient text-white shadow-glow" : "rounded-tl-md border border-line bg-card shadow-card",
        )}
      >
        {isUser ? <p className="leading-relaxed whitespace-pre-wrap">{message.content}</p> : <RichText text={message.content} />}
        {!isUser && message.sources && message.sources.length > 0 && <Sources sources={message.sources} />}
        {!isUser && <AssistantAudio text={message.content} voice={voice} />}
      </div>
    </motion.div>
  );
}

function Typing() {
  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="flex gap-3">
      <div className="mt-1 flex size-8 shrink-0 items-center justify-center rounded-full bg-brand-gradient text-white shadow-glow">
        <Bot className="size-4" />
      </div>
      <div className="flex items-center gap-1.5 rounded-2xl rounded-tl-md border border-line bg-card px-4 py-3.5 shadow-card">
        {[0, 1, 2].map((i) => (
          <motion.span
            key={i}
            className="size-2 rounded-full bg-brand"
            animate={{ y: [0, -5, 0], opacity: [0.4, 1, 0.4] }}
            transition={{ duration: 0.9, repeat: Infinity, delay: i * 0.15, ease: "easeInOut" }}
          />
        ))}
        <span className="ml-2 text-xs text-subtle">Searching the meetings…</span>
      </div>
    </motion.div>
  );
}

export function Chat({ status }: { status: AppStatus }) {
  const { model } = useModel();
  const meetings = useQuery({ queryKey: ["meetings"], queryFn: api.meetings });
  const [params, setParams] = useSearchParams();
  const scope = params.get("meeting") ?? ALL;
  const [histories, setHistories] = useState<Record<string, ChatMessage[]>>({});
  const [question, setQuestion] = useState("");
  const bottom = useRef<HTMLDivElement>(null);
  const history = histories[scope] ?? [];

  const ask = useMutation({
    mutationFn: (q: string) => api.chat(q, history, scope === ALL ? null : scope, model),
    onMutate: (q) => setHistories((h) => ({ ...h, [scope]: [...(h[scope] ?? []), { role: "user", content: q }] })),
    onSuccess: (reply) =>
      setHistories((h) => ({
        ...h,
        [scope]: [...(h[scope] ?? []), { role: "assistant", content: reply.answer, sources: reply.sources }],
      })),
  });

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [history.length, ask.isPending]);

  const send = (text = question) => {
    const q = text.trim();
    if (!q || ask.isPending) return;
    setQuestion("");
    ask.mutate(q);
  };

  if (meetings.isPending)
    return (
      <div className="space-y-4">
        <Skeleton className="h-9 w-72" />
        <Skeleton className="h-11 max-w-xl" />
        <Skeleton className="h-48 rounded-2xl" />
      </div>
    );
  if (meetings.isError) return <Alert tone="error">{meetings.error.message}</Alert>;
  if (!meetings.data.length)
    return (
      <EmptyState icon={Files} title="No meetings to ask about yet">
        <Link to="/new" className="font-medium text-brand hover:underline">
          Create a meeting
        </Link>{" "}
        first.
      </EmptyState>
    );

  return (
    <div className="flex min-h-[calc(100vh-9rem)] flex-col">
      <PageHeader
        eyebrow="Assistant"
        title="Ask about your meetings"
        description={
          status.services.search.ok
            ? "Answers are grounded in the transcripts and cite timestamps."
            : "Semantic search is off (QDRANT_URI not set), so answers use keyword search over transcripts."
        }
        actions={
          history.length > 0 && (
            <Button size="sm" variant="ghost" icon={Trash2} onClick={() => setHistories((h) => ({ ...h, [scope]: [] }))}>
              Clear conversation
            </Button>
          )
        }
      />

      <Field label="Ask about" className="mb-6 max-w-xl">
        <select className={inputClass} value={scope} onChange={(e) => setParams(e.target.value === ALL ? {} : { meeting: e.target.value })}>
          <option value={ALL}>All meetings</option>
          {meetings.data.map((m) => (
            <option key={m.id} value={m.id}>
              {m.title} · {formatDate(m.meeting_date)}
            </option>
          ))}
        </select>
      </Field>

      <div className="flex-1 space-y-5">
        {history.length === 0 && (
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, ease: EASE }} className="py-6 text-center">
            <div className="mx-auto mb-4 flex size-14 items-center justify-center rounded-2xl bg-brand-gradient text-white shadow-glow">
              <MessagesSquare className="size-6" />
            </div>
            <h2 className="font-semibold">What would you like to know?</h2>
            <p className="mt-1 text-sm text-subtle">Try one of these, or ask your own question.</p>
            <div className="mx-auto mt-5 grid max-w-2xl grid-cols-1 gap-2 sm:grid-cols-2">
              {SUGGESTIONS.map((suggestion, i) => (
                <motion.button
                  key={suggestion}
                  type="button"
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.1 + i * 0.06, duration: 0.35, ease: EASE }}
                  onClick={() => send(suggestion)}
                  className="rounded-xl border border-line bg-card px-4 py-3 text-left text-sm shadow-card transition duration-200 hover:-translate-y-0.5 hover:border-brand/40 hover:shadow-lift"
                >
                  {suggestion}
                </motion.button>
              ))}
            </div>
          </motion.div>
        )}
        {history.map((message, i) => (
          <Message key={i} message={message} voice={status.voices[0]} />
        ))}
        <AnimatePresence>{ask.isPending && <Typing />}</AnimatePresence>
        {ask.isError && <Alert tone="error">{ask.error.message}</Alert>}
        <div ref={bottom} />
      </div>

      <form
        className="glass sticky bottom-4 mt-8 flex items-end gap-2 rounded-2xl border border-line p-2 shadow-pop transition focus-within:border-brand/50 focus-within:ring-4 focus-within:ring-brand/10"
        onSubmit={(e) => {
          e.preventDefault();
          send();
        }}
      >
        <textarea
          rows={1}
          aria-label="Your question"
          className="max-h-40 min-h-10 flex-1 resize-none bg-transparent px-3 py-2.5 text-sm focus:outline-none"
          placeholder="Ask a question… (Enter to send, Shift+Enter for a new line)"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              send();
            }
          }}
        />
        <Button type="submit" variant="primary" icon={ArrowUp} disabled={!question.trim()} loading={ask.isPending} aria-label="Send" className="size-10 px-0" />
      </form>
    </div>
  );
}
