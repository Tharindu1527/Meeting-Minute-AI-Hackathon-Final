import type {
  ActionItem,
  AppStatus,
  ChatMessage,
  ChatSource,
  Claim,
  EmailResult,
  ExportFormat,
  Job,
  Meeting,
  MeetingSummary,
  Minutes,
  TrackedActionItem,
} from "./types";

const TOKEN_KEY = "meeting-minutes-token";

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string | null) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    // Storage unavailable (private mode): the token only lives for this page load
  }
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

let onUnauthorized: (() => void) | null = null;

/** Called when the API rejects the token, so the app can show the sign-in screen */
export function setUnauthorizedHandler(handler: (() => void) | null) {
  onUnauthorized = handler;
}

function describeDetail(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    // FastAPI validation errors: [{loc, msg}, ...]
    return detail.map((d) => (typeof d?.msg === "string" ? d.msg : JSON.stringify(d))).join("; ");
  }
  return "Something went wrong";
}

type RequestOptions = Omit<RequestInit, "body"> & { json?: unknown; body?: BodyInit };

async function request<T>(path: string, options: RequestOptions = {}, as: "json" | "blob" = "json"): Promise<T> {
  const { json, ...init } = options;
  const headers = new Headers(init.headers);
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  let body = init.body;
  if (json !== undefined) {
    headers.set("Content-Type", "application/json");
    body = JSON.stringify(json);
  }

  let response: Response;
  try {
    response = await fetch(`/api${path}`, { ...init, headers, body });
  } catch {
    throw new ApiError(0, "Can't reach the server. Is the API running?");
  }
  if (!response.ok) {
    let message = response.statusText || `Request failed (${response.status})`;
    try {
      message = describeDetail((await response.json()).detail);
    } catch {
      // Not JSON (e.g. a proxy error page): keep the status text
    }
    if (response.status === 401 && path !== "/auth/login") {
      setToken(null);
      onUnauthorized?.();
    }
    throw new ApiError(response.status, message);
  }
  return (as === "blob" ? await response.blob() : await response.json()) as T;
}

export const api = {
  status: () => request<AppStatus>("/status"),
  login: (password: string) => request<{ token: string | null }>("/auth/login", { method: "POST", json: { password } }),

  meetings: () => request<MeetingSummary[]>("/meetings"),
  meeting: (id: string) => request<Meeting>(`/meetings/${id}`),
  createMeeting: (form: FormData) => request<{ job_id: string }>("/meetings", { method: "POST", body: form }),
  job: <T>(id: string) => request<Job<T>>(`/jobs/${id}`),
  saveMinutes: (id: string, minutes: Minutes) => request<Meeting>(`/meetings/${id}/minutes`, { method: "PUT", json: minutes }),
  deleteMeeting: (id: string) => request<{ deleted: boolean; warning: string | null }>(`/meetings/${id}`, { method: "DELETE" }),
  exportMeeting: (id: string, format: ExportFormat) => request<Blob>(`/meetings/${id}/export/${format}`, {}, "blob"),
  email: (id: string, recipients: string) =>
    request<{ provider: string; results: EmailResult[] }>(`/meetings/${id}/email`, { method: "POST", json: { recipients } }),

  actionItems: () => request<TrackedActionItem[]>("/action-items"),
  updateActionItem: (meetingId: string, itemId: string, fields: Partial<Pick<ActionItem, "owner" | "due_date" | "priority" | "status">>) =>
    request<{ updated: object }>(`/meetings/${meetingId}/action-items/${itemId}`, { method: "PATCH", json: fields }),

  chat: (question: string, history: ChatMessage[], meetingId: string | null, model: string) =>
    request<{ answer: string; sources: ChatSource[] }>("/chat", {
      method: "POST",
      json: {
        question,
        meeting_id: meetingId,
        model,
        history: history.map(({ role, content }) => ({ role, content })),
      },
    }),
  tts: (text: string, voice: string) => request<Blob>("/tts", { method: "POST", json: { text, voice } }, "blob"),
  speechScript: (id: string, language: string | null) =>
    request<{ script: string }>(`/meetings/${id}/speech-script${language ? `?language=${encodeURIComponent(language)}` : ""}`),
  speech: (id: string, language: string | null, voice: string) =>
    request<Blob>(`/meetings/${id}/speech`, { method: "POST", json: { language, voice } }, "blob"),

  findClaims: (id: string, model: string) =>
    request<{ job_id: string }>(`/meetings/${id}/fact-check/claims`, { method: "POST", json: { model } }),
  verifyClaims: (id: string, claims: Claim[], model: string) =>
    request<{ job_id: string }>(`/meetings/${id}/fact-check/verify`, { method: "POST", json: { claims, model } }),
};
