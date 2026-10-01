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
  Session,
  TrackedActionItem,
  User,
} from "./types";

const TOKEN_KEY = "meeting-minutes-token";
// Used when storage is unavailable (some private windows): the session lasts for this page load
let memoryToken: string | null = null;

function storage(kind: "local" | "session"): Storage | null {
  try {
    return kind === "local" ? window.localStorage : window.sessionStorage;
  } catch {
    return null;
  }
}

export function getToken(): string | null {
  try {
    return storage("local")?.getItem(TOKEN_KEY) ?? storage("session")?.getItem(TOKEN_KEY) ?? memoryToken;
  } catch {
    return memoryToken;
  }
}

/** Whether the current session was started with "Keep me signed in" (kept across browser restarts) */
export function isRemembered(): boolean {
  try {
    return Boolean(storage("local")?.getItem(TOKEN_KEY));
  } catch {
    return false;
  }
}

/** Store the sign-in token: in localStorage when remembered, otherwise only for this browser session */
export function setToken(token: string | null, remember = true) {
  memoryToken = token;
  try {
    storage("local")?.removeItem(TOKEN_KEY);
    storage("session")?.removeItem(TOKEN_KEY);
    if (token) storage(remember ? "local" : "session")?.setItem(TOKEN_KEY, token);
  } catch {
    // Storage unavailable: memoryToken keeps the session for this page load
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
    // A rejected token means the session ended; wrong passwords on the sign-in forms don't
    if (response.status === 401 && token && !path.startsWith("/auth/login")) {
      setToken(null);
      onUnauthorized?.();
    }
    throw new ApiError(response.status, message);
  }
  return (as === "blob" ? await response.blob() : await response.json()) as T;
}

export const api = {
  status: () => request<AppStatus>("/status"),

  register: (body: { name: string; email: string; password: string; invite_code?: string; remember: boolean }) =>
    request<Session>("/auth/register", { method: "POST", json: body }),
  login: (body: { email: string; password: string; remember: boolean }) => request<Session>("/auth/login", { method: "POST", json: body }),
  me: () => request<User>("/auth/me"),
  updateProfile: (name: string) => request<User>("/auth/me", { method: "PATCH", json: { name } }),
  changePassword: (currentPassword: string, newPassword: string) =>
    request<Session>("/auth/change-password", {
      method: "POST",
      json: { current_password: currentPassword, new_password: newPassword, remember: isRemembered() },
    }),
  signOutOthers: () => request<Session>("/auth/sign-out-others", { method: "POST", json: { remember: isRemembered() } }),
  deleteAccount: (password: string) =>
    request<{ deleted: boolean; meetings_deleted: number }>("/auth/delete-account", { method: "POST", json: { password } }),
  forgotPassword: (email: string) => request<{ sent: boolean }>("/auth/forgot-password", { method: "POST", json: { email } }),
  checkResetToken: (token: string) => request<{ email: string }>("/auth/reset-password/check", { method: "POST", json: { token } }),
  resetPassword: (token: string, password: string) =>
    request<Session>("/auth/reset-password", { method: "POST", json: { token, password } }),

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
