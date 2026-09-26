# models/minutes.py
"""
Typed schemas for meeting minutes.

Each agent task asks for JSON matching one of these schemas, so agents return
structured data instead of free text. `MeetingMinutes` is the combined record
stored in MongoDB and rendered in the UI.

Models are lenient about the small variations LLMs produce (null instead of an
empty list, "HIGH" or "completed" instead of the exact enum value), so a
cosmetic difference never throws away an otherwise good answer.
"""
import uuid
from typing import List, Literal, Optional, get_origin

from pydantic import BaseModel, Field, field_validator

PRIORITIES = ["High", "Medium", "Low"]
STATUSES = ["Open", "In progress", "Done"]
CLAIM_STATUSES = ["Verified", "Partially verified", "Refuted", "Unverifiable"]

Priority = Literal["High", "Medium", "Low"]
Status = Literal["Open", "In progress", "Done"]
ClaimStatus = Literal["Verified", "Partially verified", "Refuted", "Unverifiable"]

_PRIORITY_SYNONYMS = {"high": "High", "urgent": "High", "critical": "High", "medium": "Medium", "normal": "Medium",
                      "moderate": "Medium", "low": "Low"}
_STATUS_SYNONYMS = {"open": "Open", "todo": "Open", "to do": "Open", "not started": "Open", "pending": "Open",
                    "in progress": "In progress", "in-progress": "In progress", "ongoing": "In progress",
                    "started": "In progress", "done": "Done", "complete": "Done", "completed": "Done", "closed": "Done"}
_CLAIM_SYNONYMS = {"verified": "Verified", "true": "Verified", "confirmed": "Verified", "correct": "Verified",
                   "accurate": "Verified", "partially verified": "Partially verified",
                   "partially true": "Partially verified", "partly true": "Partially verified",
                   "mostly true": "Partially verified", "mixed": "Partially verified", "refuted": "Refuted",
                   "false": "Refuted", "incorrect": "Refuted", "inaccurate": "Refuted", "unverifiable": "Unverifiable",
                   "unverified": "Unverifiable", "unknown": "Unverifiable", "insufficient evidence": "Unverifiable"}


def _normalize(value, synonyms, default):
    if value is None:
        return default
    return synonyms.get(str(value).strip().lower().rstrip("."), value)


class Lenient(BaseModel):
    """Base model that turns null into [] for list fields and "" for required text fields"""

    @field_validator("*", mode="before")
    @classmethod
    def _null_to_empty(cls, value, info):
        if value is None:
            annotation = cls.model_fields[info.field_name].annotation
            if get_origin(annotation) is list:
                return []
            if annotation is str:
                return ""
        return value


# --- Agent outputs -----------------------------------------------------------

class Attendee(Lenient):
    name: str = Field(description="The person's real name if it is stated or clearly implied in the meeting, otherwise the transcript speaker label")
    role: Optional[str] = Field(None, description="Job title or role in the meeting (e.g. 'Chair', 'Finance lead') if mentioned")
    speaker_label: Optional[str] = Field(None, description="The transcript label for this person, e.g. 'Speaker A'")


class AttendeeList(Lenient):
    attendees: List[Attendee] = Field(description="Everyone who spoke in the meeting")


class AgendaItem(Lenient):
    title: str = Field(description="Short name of the agenda item or discussion topic")
    discussion: str = Field(description="What was discussed, in 2-4 sentences, naming who contributed what")
    outcome: Optional[str] = Field(None, description="The conclusion reached for this item, if any")


class Decision(Lenient):
    decision: str = Field(description="The decision that was explicitly agreed")
    decided_by: Optional[str] = Field(None, description="Who made or approved the decision, if stated")
    rationale: Optional[str] = Field(None, description="Why it was decided, if stated")


class MeetingAnalysis(Lenient):
    key_topics: List[str] = Field(description="3-8 short topic labels covering the meeting")
    agenda_items: List[AgendaItem] = Field(description="Discussion broken down by agenda item or topic, in the order discussed")
    decisions: List[Decision] = Field(description="Decisions explicitly agreed in the meeting. Empty if none were made")
    open_issues: List[str] = Field(description="Unresolved questions, parked items or disagreements that need follow-up")


class MeetingSummary(Lenient):
    summary: str = Field(description="Executive summary of the meeting, 150-300 words")
    highlights: List[str] = Field(description="3-6 one-line key takeaways")


class SpeakerSentiment(Lenient):
    speaker: str
    tone: str = Field(description="One or two words, e.g. 'Supportive', 'Concerned'")
    notes: str = Field(description="One sentence explaining the tone, with an example")


class SentimentReport(Lenient):
    overall_tone: str = Field(description="One or two words, e.g. 'Constructive', 'Tense'")
    summary: str = Field(description="2-4 sentences on the mood and dynamics of the meeting")
    per_speaker: List[SpeakerSentiment] = Field(default_factory=list)
    agreements: List[str] = Field(default_factory=list, description="Points where participants clearly agreed")
    disagreements: List[str] = Field(default_factory=list, description="Points of disagreement or tension")


class ActionItem(Lenient):
    task: str = Field(description="What needs to be done, starting with a verb")
    owner: Optional[str] = Field(None, description="The person responsible. Null if nobody was assigned")
    due_date: Optional[str] = Field(None, description="YYYY-MM-DD if a deadline was given (resolve relative dates like 'next Friday' against the meeting date), otherwise null")
    priority: Priority = Field("Medium", description="High, Medium or Low, based on urgency and impact discussed")
    context: Optional[str] = Field(None, description="One sentence on why this is needed")

    @field_validator("priority", mode="before")
    @classmethod
    def _normalize_priority(cls, value):
        return _normalize(value, _PRIORITY_SYNONYMS, "Medium")


class ActionItemList(Lenient):
    action_items: List[ActionItem] = Field(description="Only tasks that were actually committed to or assigned in the meeting")
    next_meeting: Optional[str] = Field(None, description="When the next meeting is, if it was scheduled")


class Claim(Lenient):
    claim: str = Field(description="A checkable factual statement, worded so it stands on its own")
    speaker: Optional[str] = Field(None, description="Who said it")


class ClaimList(Lenient):
    claims: List[Claim]


class ClaimVerdict(Lenient):
    status: ClaimStatus
    explanation: str = Field(description="2-3 sentences explaining the verdict")
    sources: List[str] = Field(default_factory=list, description="URLs or titles of sources used")

    @field_validator("status", mode="before")
    @classmethod
    def _normalize_status(cls, value):
        return _normalize(value, _CLAIM_SYNONYMS, "Unverifiable")


class CheckedClaim(Claim, ClaimVerdict):
    pass


class FactCheckReport(Lenient):
    claims: List[CheckedClaim]


class ResearchInsight(Lenient):
    topic: str
    background: str = Field(description="Useful background on the topic, 2-4 sentences")
    relevance: str = Field(description="Why this matters for the decisions or discussion in this meeting")
    sources: List[str] = Field(default_factory=list, description="URLs of sources used")


class ResearchReport(Lenient):
    insights: List[ResearchInsight]


class TranslatedMinutes(Lenient):
    language: str
    summary: str
    decisions: List[str] = Field(default_factory=list)
    action_items: List[str] = Field(default_factory=list, description="Each item as 'task — owner — due date'")


# --- Stored record -----------------------------------------------------------

def new_item_id():
    return uuid.uuid4().hex[:12]


class TrackedActionItem(ActionItem):
    id: str = Field(default_factory=new_item_id)
    status: Status = "Open"

    @field_validator("status", mode="before")
    @classmethod
    def _normalize_status(cls, value):
        return _normalize(value, _STATUS_SYNONYMS, "Open")

    @field_validator("id", mode="before")
    @classmethod
    def _ensure_id(cls, value):
        return value or new_item_id()


class MeetingMinutes(Lenient):
    summary: str = ""
    highlights: List[str] = Field(default_factory=list)
    key_topics: List[str] = Field(default_factory=list)
    attendees: List[Attendee] = Field(default_factory=list)
    agenda_items: List[AgendaItem] = Field(default_factory=list)
    decisions: List[Decision] = Field(default_factory=list)
    action_items: List[TrackedActionItem] = Field(default_factory=list)
    open_issues: List[str] = Field(default_factory=list)
    next_meeting: Optional[str] = None
    sentiment: Optional[SentimentReport] = None
