# server/routes/fact_check.py
"""On-demand fact checking: find claims in a meeting, then verify the chosen ones (both as background jobs)"""
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from crews import FactCheckCrew
from database import mongodb
from models import Claim
from server.jobs import jobs
from server.routes.meetings import load_meeting

router = APIRouter(tags=["fact check"])


def _transcript(meeting):
    text = (meeting.get("transcript") or {}).get("text", "")
    if not text:
        raise HTTPException(status_code=400, detail="This meeting has no transcript to check.")
    return text


class ModelRequest(BaseModel):
    model: Optional[str] = None


@router.post("/meetings/{meeting_id}/fact-check/claims", status_code=202)
def find_claims(meeting_id: str, body: ModelRequest):
    transcript = _transcript(load_meeting(meeting_id))

    def run(job):
        job.report("Reading the transcript for checkable claims...")
        claims = FactCheckCrew(body.model or None).extract_claims(transcript)
        job.report(f"Found {len(claims)} claim{'s' if len(claims) != 1 else ''}")
        return {"claims": [claim.model_dump() for claim in claims]}

    return {"job_id": jobs.start("find_claims", run).id}


class VerifyRequest(BaseModel):
    claims: List[Claim] = Field(min_length=1)
    model: Optional[str] = None


@router.post("/meetings/{meeting_id}/fact-check/verify", status_code=202)
def verify_claims(meeting_id: str, body: VerifyRequest):
    load_meeting(meeting_id)

    def run(job):
        crew = FactCheckCrew(body.model or None)
        checked = []
        for index, claim in enumerate(body.claims, 1):
            job.report(f"Checking claim {index} of {len(body.claims)}: {claim.claim}", index - 1, len(body.claims))
            checked.append(crew.verify_claim(claim).model_dump())
        job.report("Saving the results", len(body.claims), len(body.claims))
        # Re-read so results saved by someone else meanwhile are kept
        existing = (mongodb.get_meeting(meeting_id) or {}).get("fact_check") or {}
        checked_texts = {c["claim"] for c in checked}
        merged = [c for c in existing.get("claims") or [] if c["claim"] not in checked_texts] + checked
        mongodb.update_meeting(meeting_id, {"fact_check": {"claims": merged}})
        return {"fact_check": {"claims": merged}}

    return {"job_id": jobs.start("verify_claims", run).id}
