---
title: Meeting Minutes AI
emoji: 📝
colorFrom: indigo
colorTo: purple
sdk: docker
app_port: 8000
short_description: Multi-agent AI that turns meetings into minutes
pinned: false
---

# Meeting Minutes AI

Turn a meeting recording or transcript into structured minutes — attendees, agenda and discussion, **decisions**, **action items with owners and due dates**, open issues — using a crew of CrewAI agents running on Google Gemini (free tier). Review and edit the minutes, export them to Word/Markdown/PDF, email them, track action items across meetings, and chat with your meeting history.

The app is a **React + Vite** frontend (TypeScript, Tailwind CSS, TanStack Query) talking to a **FastAPI** backend that runs the agents. In production the backend also serves the built frontend, so everything runs on one port.

## Features

| Page | What it does |
|---|---|
| 📝 **New meeting** | Upload audio/video (mp3, wav, m4a, mp4, mov, webm…), give a recording URL, upload a transcript (.txt, .vtt, .srt — Zoom and Teams exports keep speaker names) or paste text. Transcription includes speaker labels, timestamps, language detection and optional PII redaction. |
| 📚 **Meetings** | Browse past meetings; view or edit the minutes; export to Word, Markdown or HTML (print to PDF); email them; delete. |
| ✅ **Action items** | Every action item across all meetings: filter by status/owner, see what's overdue, update status, owner, due date and priority. |
| 💬 **Chat** | Ask questions about one meeting or all of them. Answers cite the transcript with timestamps. |
| 🔊 **Listen** | Audio version of the minutes (summary, decisions, action items), in the original language or a translation. |
| 🔎 **Fact check** | Find factual claims in a meeting and verify the ones you pick against Wikipedia. |

### The agent crew

Each agent returns typed data (Pydantic models in [`models/minutes.py`](models/minutes.py)), and each task receives exactly the inputs it needs through CrewAI `context`:

```
Meeting Secretary ──► attendees (speaker label → name, role)
        │
        ├──► Meeting Analyst ──► agenda items, decisions, key topics, open issues
        │           │
        │           ├──► Executive Summarizer ──► summary, key takeaways
        │           └──► Action Item Tracker ──► tasks with owner, due date, priority
        └──► Meeting Dynamics Analyst ──► tone, per-speaker sentiment, agreement/disagreement

Optional:  Fact Checker (Wikipedia tool)  ·  Background Researcher (Wikipedia tool)  ·  Translator
```

## Setup

Requires Python 3.10–3.12 and Node.js 20.19+ (or 22.12+).

```bash
python -m venv venv
venv\Scripts\activate          # Windows  (macOS/Linux: source venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env         # macOS/Linux: cp .env.example .env
npm --prefix frontend install
```

Fill in `.env`:

| Variable | Required | Purpose |
|---|---|---|
| `GEMINI_API_KEY` | yes | Agents, chat, embeddings, text-to-speech. Free key from [Google AI Studio](https://aistudio.google.com/apikey) |
| `MONGODB_URI` | yes | Stores meetings (MongoDB Atlas free tier works) |
| `ASSEMBLYAI_API_KEY` | for recordings | Speech-to-text with speaker labels |
| `QDRANT_URI` | no | Semantic chat search. A folder path such as `./qdrant_data` needs no server; empty = keyword search |
| `APP_PASSWORD` | recommended | Password-protects the app |
| `SMTP_*` / `EMAIL_FROM` | no | Email via SMTP (e.g. Gmail with an [app password](https://myaccount.google.com/apppasswords)) |
| `COMPOSIO_API_KEY` | no | Email via Composio's Gmail integration (connect Gmail in the Composio dashboard first) |

### Run in development

Two terminals: the API with auto-reload, and the Vite dev server (hot reload; it forwards `/api` to the API).

```bash
uvicorn server.main:app --reload --port 8000
npm --prefix frontend run dev
```

Open http://localhost:5173. The API's interactive docs are at http://localhost:8000/docs.

### Run in production

Build the frontend once; the API then serves it:

```bash
npm --prefix frontend run build
uvicorn server.main:app --host 0.0.0.0 --port 8000
```

Open http://localhost:8000.

### Docker

The Dockerfile builds the frontend and runs the API in one image:

```bash
docker build -t meeting-minutes .
docker run -p 8000:8000 --env-file .env meeting-minutes
```

The container runs as an unprivileged user and listens on `$PORT` (default 8000), so it also works on hosts that assign the port.

### Deploy to Hugging Face Spaces

The block at the top of this README configures a [Docker Space](https://huggingface.co/docs/hub/spaces-sdks-docker) (free CPU hardware is enough).

1. Create a Space with the **Docker** SDK and upload this repository to it (the Space builds the Dockerfile).
2. In the Space's **Settings → Variables and secrets**, add every variable from your `.env` as a **secret**. Set `APP_PASSWORD`, because a public Space's URL is open to everyone.
3. MongoDB Atlas must accept connections from the Space: under **Network Access**, allow `0.0.0.0/0` (Spaces have no fixed IP address) and keep a strong database password.
4. Uploads are processed in the container, but everything that must last (meetings, search index) lives in MongoDB Atlas and Qdrant Cloud, so restarts lose nothing except jobs that were running.

### How it fits together

- Slow work (generating minutes, fact checking) runs as a **background job**: the API returns a job id straight away and the page polls `GET /api/jobs/{id}` for progress.
- With `APP_PASSWORD` set, `POST /api/auth/login` returns a signed token that the frontend sends with every request; changing the password signs everyone out.
- `GET /api/status` is public and tells the frontend which services are configured, which models to offer, and whether sign-in is needed.

### Gemini free tier

The free tier is tight: for `gemini-3.8-flash` we observed **5 requests per minute and 20 requests per day** (September 2026), and popular models sometimes return "high demand" errors. One analysis uses 5–8 requests. The app copes automatically:

- paces each model to the per-minute limit Gemini reports (or a fixed `GEMINI_REQUESTS_PER_MINUTE`),
- waits as long as Gemini asks when briefly rate-limited,
- falls back to `GEMINI_FALLBACK_MODELS` (each model has its own quota) when a model is overloaded, stalls, or has used its daily quota, and skips that model for a while afterwards (longer if it keeps failing),
- asks the model once to repair an answer that doesn't match the expected JSON, instead of losing that section.

A full analysis therefore takes a few minutes. Check your live limits at [AI Studio](https://aistudio.google.com/rate-limit); enabling billing on the key's Google Cloud project removes these limits.

## Tests

```bash
pip install -r requirements-dev.txt
pytest
npm --prefix frontend run typecheck
```

Tests run offline: MongoDB is replaced by `mongomock`, the API is exercised with FastAPI's `TestClient`, and the crew tests swap the LLM for a scripted fake (or a local fake Gemini server) so the full CrewAI pipeline is exercised without API calls.

## Project layout

```
frontend/               React + Vite + TypeScript app
  src/pages/            New meeting, Meetings, Meeting detail, Action items, Chat, Listen, Fact check, sign-in
  src/components/       Layout, minutes view/editor, job progress, share panel, UI primitives
  src/lib/              Typed API client, types, hooks, formatting
server/                 FastAPI backend: routes, background jobs, optional password auth
app/pipeline.py         Source -> transcript -> AI crew -> saved + indexed meeting
app/chatbot.py          Retrieval + answer generation for chat
app/export.py           Markdown / HTML / Word / speech-script rendering (HTML is also the email body)
agents/                 Agent definitions, tasks, registry, Wikipedia tool
crews/                  MeetingCrew (minutes) and FactCheckCrew (on-demand checks)
models/minutes.py       Pydantic schemas for every agent output and the stored minutes
api/                    AssemblyAI, Gemini (chat, embeddings, TTS), Wikipedia, email
database/               MongoDB (meetings) and Qdrant (transcript search)
utils/                  Config and transcript parsing/chunking
```

## Privacy notes

- Meeting transcripts are sent to Google Gemini and (for recordings) AssemblyAI. Enable **PII redaction** in the transcription options to mask phone numbers, emails and card/ID numbers.
- **Gemini free tier:** Google states that content sent on the free tier is used to improve its products. For confidential meetings, enable billing on the Google Cloud project behind your API key (paid-tier content is not used this way).
- Set `APP_PASSWORD` before deploying anywhere public: without it, anyone with the link can read every meeting.
- CrewAI sends anonymous usage telemetry by default; set `OTEL_SDK_DISABLED=true` to turn it off.
