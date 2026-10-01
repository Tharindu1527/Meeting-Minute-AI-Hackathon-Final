// Shapes returned by the FastAPI backend (see models/minutes.py and server/routes)

export type Priority = "High" | "Medium" | "Low";
export type Status = "Open" | "In progress" | "Done";
export type ClaimStatus = "Verified" | "Partially verified" | "Refuted" | "Unverifiable";

export const PRIORITIES: Priority[] = ["High", "Medium", "Low"];
export const STATUSES: Status[] = ["Open", "In progress", "Done"];

export interface Attendee {
  name: string;
  role: string | null;
  speaker_label: string | null;
}

export interface AgendaItem {
  title: string;
  discussion: string;
  outcome: string | null;
}

export interface Decision {
  decision: string;
  decided_by: string | null;
  rationale: string | null;
}

export interface ActionItem {
  id: string;
  task: string;
  owner: string | null;
  due_date: string | null;
  priority: Priority;
  status: Status;
  context: string | null;
}

export interface SpeakerSentiment {
  speaker: string;
  tone: string;
  notes: string;
}

export interface Sentiment {
  overall_tone: string;
  summary: string;
  per_speaker: SpeakerSentiment[];
  agreements: string[];
  disagreements: string[];
}

export interface Minutes {
  summary: string;
  highlights: string[];
  key_topics: string[];
  attendees: Attendee[];
  agenda_items: AgendaItem[];
  decisions: Decision[];
  action_items: ActionItem[];
  open_issues: string[];
  next_meeting: string | null;
  sentiment: Sentiment | null;
}

export interface Claim {
  claim: string;
  speaker: string | null;
}

export interface CheckedClaim extends Claim {
  status: ClaimStatus;
  explanation: string;
  sources: string[];
}

export interface ResearchInsight {
  topic: string;
  background: string;
  relevance: string;
  sources: string[];
}

export interface Translation {
  language: string;
  summary: string;
  decisions: string[];
  action_items: string[];
}

export interface Utterance {
  speaker: string | null;
  start_ms: number | null;
  end_ms: number | null;
  text: string;
}

export interface Transcript {
  text: string;
  utterances: Utterance[];
  language: string | null;
  duration_seconds: number | null;
  truncated?: boolean;
}

export interface Meeting {
  id: string;
  title: string;
  meeting_date: string | null;
  created_at: string;
  updated_at: string;
  minutes: Minutes;
  fact_check: { claims: CheckedClaim[] } | null;
  research: { insights: ResearchInsight[] } | null;
  translations: Record<string, Translation>;
  transcript: Transcript;
  warnings: string[];
  source?: { type: string; name: string | null };
}

export interface MeetingSummary {
  id: string;
  title: string;
  meeting_date: string | null;
  created_at: string;
  summary: string;
  decision_count: number;
  action_item_count: number;
  open_action_item_count: number;
}

export interface TrackedActionItem extends ActionItem {
  meeting_id: string;
  meeting_title: string;
  meeting_date: string | null;
  overdue: boolean;
}

export interface JobStep {
  message: string;
  at: number;
}

export interface Job<T> {
  id: string;
  kind: string;
  status: "running" | "done" | "error";
  steps: JobStep[];
  done: number;
  total: number | null;
  result: T | null;
  error: string | null;
}

export interface ServiceStatus {
  ok: boolean;
  detail: string;
}

export interface ConfigItem {
  name: string;
  purpose: string;
}

export interface AuthOptions {
  /** New accounts can be created (the first account always can) */
  signup_open: boolean;
  /** New accounts need the invite code (SIGNUP_CODE) */
  invite_code_required: boolean;
  /** Email is configured, so "forgot password" can send reset links */
  password_reset: boolean;
}

export interface User {
  id: string;
  email: string;
  name: string;
  created_at: string;
}

export interface Session {
  token: string;
  /** Unix seconds */
  expires_at: number;
  user: User;
}

export interface AppStatus {
  version: string;
  auth: AuthOptions;
  missing_config: ConfigItem[];
  optional_config: ConfigItem[];
  services: {
    database: ServiceStatus;
    transcription: ServiceStatus;
    search: ServiceStatus;
    email: ServiceStatus;
  };
  models: string[];
  default_model: string;
  languages: string[];
  voices: string[];
}

export interface ChatSource {
  title: string;
  text: string;
  start_ms: number | null;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  sources?: ChatSource[];
}

export interface EmailResult {
  recipient: string;
  ok: boolean;
  error: string | null;
}

export type ExportFormat = "docx" | "md" | "html";
