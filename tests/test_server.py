"""API tests: the FastAPI backend with MongoDB swapped for mongomock and the AI crews faked"""
import copy
import time

import pytest
from fastapi.testclient import TestClient

import server.main
import server.routes.status
from crews.fact_check_crew import FactCheckCrew
from crews.meeting_crew import MeetingCrew
from models import CheckedClaim, Claim


@pytest.fixture
def client(mongo):
    server.routes.status._db_status.update(checked_at=time.time(), ok=True, error=None)
    return TestClient(server.main.create_app())


@pytest.fixture
def fake_crew(monkeypatch, sample_meeting):
    calls = {}

    def run_analysis(self, transcript, meeting_info, language_code=None, progress=None):
        calls.update(transcript=transcript, meeting_info=meeting_info, model=self.model)
        progress(1, 2, "Identified attendees")
        progress(2, 2, "Extracted action items")
        result = {key: copy.deepcopy(sample_meeting[key]) for key in ("minutes", "fact_check", "research", "translations")}
        return dict(result, warnings=[])

    monkeypatch.setattr(MeetingCrew, "run_analysis", run_analysis)
    return calls


def wait_for_job(client, job_id, timeout=10):
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] != "running":
            return job
        time.sleep(0.05)
    raise AssertionError("job did not finish")


def create_meeting(client, **overrides):
    form = {"title": "Q3 budget review", "meeting_date": "2026-09-24", "source": "text",
            "text": "[00:05] Priya: Welcome.\n[00:40] Ravi: Marketing overspent by 10%.", "model": "gemini-3.6-flash"}
    form.update(overrides)
    response = client.post("/api/meetings", data=form)
    assert response.status_code == 202, response.text
    job = wait_for_job(client, response.json()["job_id"])
    assert job["status"] == "done", job
    return job["result"]["meeting_id"], job


def test_status_is_public_and_describes_services(client):
    body = client.get("/api/status").json()
    assert body["auth_required"] is False and body["missing_config"] == []
    assert body["services"]["database"] == {"ok": True, "detail": "connected"}
    assert body["services"]["transcription"]["ok"] is False
    assert "gemini-3.8-flash" in body["models"] and "Spanish" in body["languages"] and "Kore" in body["voices"]


def test_password_protects_the_api(client, monkeypatch):
    monkeypatch.setenv("APP_PASSWORD", "s3cret")
    assert client.get("/api/meetings").status_code == 401
    assert client.post("/api/auth/login", json={"password": "wrong"}).status_code == 401
    token = client.post("/api/auth/login", json={"password": "s3cret"}).json()["token"]
    assert client.get("/api/meetings", headers={"Authorization": f"Bearer {token}"}).status_code == 200
    assert client.get("/api/meetings", headers={"Authorization": "Bearer 9999999999.forged"}).status_code == 401
    assert client.get("/api/status").json()["auth_required"] is True


def test_generate_meeting_runs_as_a_job(client, fake_crew, mongo):
    meeting_id, job = create_meeting(client)

    messages = [step["message"] for step in job["steps"]]
    assert messages[0].startswith("Transcript ready (") and "2 speakers" in messages[0]
    assert "Identified attendees" in messages and messages[-1] == "Saved the minutes"
    assert (job["done"], job["total"]) == (2, 2)
    assert fake_crew["model"] == "gemini-3.6-flash"
    assert "Title: Q3 budget review" in fake_crew["meeting_info"] and "Meeting date: 2026-09-24" in fake_crew["meeting_info"]

    meeting = client.get(f"/api/meetings/{meeting_id}").json()
    assert meeting["title"] == "Q3 budget review" and meeting["source"]["type"] == "text"
    assert [u["start_ms"] for u in meeting["transcript"]["utterances"]] == [5000, 40000]
    listed = client.get("/api/meetings").json()
    assert listed[0]["id"] == meeting_id and listed[0]["action_item_count"] == 2
    assert listed[0]["open_action_item_count"] == 1 and listed[0]["summary"].startswith("The team reviewed")


def test_generate_meeting_rejects_bad_input(client):
    base = {"title": "T", "meeting_date": "2026-09-24"}
    assert client.post("/api/meetings", data=dict(base, source="text", text="  ")).json()["detail"] == "Paste the transcript text."
    assert "ASSEMBLYAI_API_KEY" in client.post("/api/meetings", data=dict(base, source="url", url="https://x/a.mp3")).json()["detail"]
    assert client.post("/api/meetings", data=dict(base, title=" ", source="text", text="hi")).status_code == 400
    empty = client.post("/api/meetings", data=dict(base, source="transcript_file"),
                        files={"file": ("empty.vtt", b"WEBVTT\n\n", "text/vtt")})
    assert empty.json()["detail"] == "The transcript file is empty."


def test_generation_failure_is_reported_on_the_job(client, monkeypatch):
    from crews import AnalysisError

    def fail(self, *args, **kwargs):
        raise AnalysisError("All Gemini models are unavailable right now: gemini-3.8-flash (overloaded)")

    monkeypatch.setattr(MeetingCrew, "run_analysis", fail)
    response = client.post("/api/meetings", data={"title": "T", "meeting_date": "2026-09-24", "source": "text", "text": "A: hi"})
    job = wait_for_job(client, response.json()["job_id"])
    assert job["status"] == "error" and "gemini-3.8-flash (overloaded)" in job["error"]


def test_edit_minutes_and_export(client, fake_crew):
    meeting_id, _ = create_meeting(client)
    minutes = client.get(f"/api/meetings/{meeting_id}").json()["minutes"]
    minutes["summary"] = "Edited summary."
    minutes["action_items"].append({"task": "New task", "priority": "HIGH", "status": "completed", "id": None})

    updated = client.put(f"/api/meetings/{meeting_id}/minutes", json=minutes).json()["minutes"]
    assert updated["summary"] == "Edited summary."
    new_item = updated["action_items"][-1]
    assert (new_item["priority"], new_item["status"]) == ("High", "Done") and new_item["id"]

    docx = client.get(f"/api/meetings/{meeting_id}/export/docx")
    assert docx.headers["content-type"].startswith("application/vnd.openxmlformats")
    assert 'filename="Q3-budget-review-2026-09-24.docx"' in docx.headers["content-disposition"]
    assert "Edited summary." in client.get(f"/api/meetings/{meeting_id}/export/md").text
    assert "&lt;freeze&gt;" not in client.get(f"/api/meetings/{meeting_id}/export/html").text  # summary replaced
    assert client.get(f"/api/meetings/{meeting_id}/export/pdf").status_code == 400


def test_action_item_tracker(client, fake_crew):
    meeting_id, _ = create_meeting(client)
    items = client.get("/api/action-items").json()
    by_id = {item["id"]: item for item in items}
    assert by_id["a1"]["overdue"] is False or by_id["a1"]["due_date"] < "2026-09-25"
    assert by_id["a1"]["meeting_title"] == "Q3 budget review"

    url = f"/api/meetings/{meeting_id}/action-items/a1"
    assert client.patch(url, json={"status": "Done", "due_date": "2026-10-09"}).status_code == 200
    assert client.patch(url, json={"owner": "  ", "due_date": None}).status_code == 200
    item = {i["id"]: i for i in client.get(f"/api/meetings/{meeting_id}").json()["minutes"]["action_items"]}["a1"]
    assert (item["status"], item["owner"], item["due_date"]) == ("Done", None, None)
    assert client.patch(url, json={"status": "Finished"}).status_code == 422
    assert client.patch(f"/api/meetings/{meeting_id}/action-items/nope", json={"status": "Done"}).status_code == 404


def test_email_validation(client, fake_crew, monkeypatch):
    meeting_id, _ = create_meeting(client)
    assert "isn't configured" in client.post(f"/api/meetings/{meeting_id}/email", json={"recipients": "a@x.com"}).json()["detail"]

    import api.email_service

    monkeypatch.setenv("COMPOSIO_API_KEY", "ck")
    monkeypatch.setattr(api.email_service, "_send_composio",
                        lambda settings, recipients, subject, body: [{"recipient": r, "ok": True, "error": None} for r in recipients])
    bad = client.post(f"/api/meetings/{meeting_id}/email", json={"recipients": "a@x.com, nope"})
    assert bad.status_code == 400 and "nope" in bad.json()["detail"]
    sent = client.post(f"/api/meetings/{meeting_id}/email", json={"recipients": "a@x.com"}).json()
    assert sent == {"provider": "composio", "results": [{"recipient": "a@x.com", "ok": True, "error": None}]}


def test_chat_and_speech(client, fake_crew, monkeypatch):
    import app.chatbot
    import server.routes.assistant as assistant

    meeting_id, _ = create_meeting(client)
    monkeypatch.setattr(app.chatbot, "chat", lambda messages, model=None: "Ravi reported the overspend [@ 00:40].")
    answer = client.post("/api/chat", json={"question": "Who said marketing overspent?", "meeting_id": meeting_id,
                                            "history": [{"role": "user", "content": "hi"}]}).json()
    assert answer["answer"].startswith("Ravi") and answer["sources"][0]["start_ms"] == 5000

    script = client.get(f"/api/meetings/{meeting_id}/speech-script").json()["script"]
    assert script.startswith("Minutes of Q3 budget review") and "Send revised budget, owned by Ravi" in script
    assert client.get(f"/api/meetings/{meeting_id}/speech-script", params={"language": "klingon"}).status_code == 404

    monkeypatch.setattr(assistant, "text_to_speech", lambda text, voice: b"RIFF-fake-" + voice.encode())
    audio = client.post(f"/api/meetings/{meeting_id}/speech", json={"voice": "Puck"})
    assert audio.headers["content-type"] == "audio/wav" and audio.content == b"RIFF-fake-Puck"


def test_fact_check_jobs(client, fake_crew, monkeypatch):
    meeting_id, _ = create_meeting(client)
    monkeypatch.setattr(FactCheckCrew, "extract_claims", lambda self, transcript: [Claim(claim="Paris is in France", speaker="Ravi")])
    monkeypatch.setattr(FactCheckCrew, "verify_claim", lambda self, claim: CheckedClaim(
        claim=claim.claim, speaker=claim.speaker, status="Verified", explanation="Yes.", sources=[]))

    found = wait_for_job(client, client.post(f"/api/meetings/{meeting_id}/fact-check/claims", json={}).json()["job_id"])
    assert found["result"]["claims"] == [{"claim": "Paris is in France", "speaker": "Ravi"}]

    verified = wait_for_job(client, client.post(f"/api/meetings/{meeting_id}/fact-check/verify",
                                                json={"claims": found["result"]["claims"]}).json()["job_id"])
    assert verified["status"] == "done" and verified["steps"][0]["message"].startswith("Checking claim 1 of 1")
    saved = client.get(f"/api/meetings/{meeting_id}").json()["fact_check"]["claims"]
    assert [(c["claim"], c["status"]) for c in saved] == [("Paris is in France", "Verified")]


def test_delete_meeting(client, fake_crew):
    meeting_id, _ = create_meeting(client)
    assert client.delete(f"/api/meetings/{meeting_id}").json() == {"deleted": True, "warning": None}
    assert client.get(f"/api/meetings/{meeting_id}").status_code == 404
    assert client.get("/api/meetings/not-an-id").status_code == 503  # invalid ids are reported, not crashed on


def test_serves_the_built_frontend(mongo, monkeypatch, tmp_path):
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<div id=root></div>")
    (tmp_path / "assets" / "app.js").write_text("console.log(1)")
    monkeypatch.setattr(server.main, "FRONTEND_DIST", tmp_path)
    client = TestClient(server.main.create_app())

    assert client.get("/meetings/abc").text == "<div id=root></div>"  # client-side route
    assert client.get("/assets/app.js").text == "console.log(1)"
    assert client.get("/api/nope").status_code == 404
