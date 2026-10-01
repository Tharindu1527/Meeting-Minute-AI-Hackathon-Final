# database/mongodb.py
"""
MongoDB storage for meetings.

Document shape (collection "meetings"):
    owner_id (the user's id), title, meeting_date (YYYY-MM-DD), created_at, updated_at, options, source,
    transcript {text, utterances, language, duration_seconds, truncated},
    minutes (models.MeetingMinutes), fact_check, research, translations, warnings

Functions return plain dicts with the ObjectId exposed as a string "id".
Every meeting belongs to one user: each function takes the owner's id and
only ever sees that user's meetings.
"""
import logging
from datetime import datetime, timezone

from bson.errors import InvalidId
from bson.objectid import ObjectId
from pymongo import DESCENDING, MongoClient
from pymongo.errors import PyMongoError

from utils.config import get_mongodb_db_name, get_mongodb_uri

logger = logging.getLogger(__name__)

_client = None
_indexes_ready = False


class DatabaseError(Exception):
    """Raised when MongoDB is unreachable or an operation fails"""


def get_client():
    """Shared MongoClient (pymongo pools connections and is thread-safe)"""
    global _client
    if _client is None:
        uri = get_mongodb_uri()
        if not uri:
            raise DatabaseError("MONGODB_URI is not set")
        _client = MongoClient(uri, serverSelectionTimeoutMS=5000, tz_aware=True)
    return _client


def get_database():
    return get_client()[get_mongodb_db_name()]


def get_collection():
    global _indexes_ready
    collection = get_database()["meetings"]
    if not _indexes_ready:
        try:
            collection.create_index([("owner_id", 1), ("meeting_date", -1)])
        except PyMongoError:  # an index only speeds up queries; never block the app on it
            logger.warning("Could not create the meetings index", exc_info=True)
        _indexes_ready = True
    return collection


def ping():
    """
    Check the connection

    Returns:
        tuple: (ok, error message or None)
    """
    try:
        get_client().admin.command("ping")
        return True, None
    except (PyMongoError, DatabaseError) as e:
        return False, str(e)


def _now():
    return datetime.now(timezone.utc)


def _object_id(value, kind="meeting"):
    try:
        return ObjectId(value)
    except (InvalidId, TypeError) as e:
        raise DatabaseError(f"Invalid {kind} id: {value}") from e


def _mine(meeting_id, owner_id):
    """Filter matching one meeting, only when it belongs to owner_id"""
    return {"_id": _object_id(meeting_id), "owner_id": owner_id}


def _to_public(doc):
    if doc is None:
        return None
    doc = dict(doc)
    doc["id"] = str(doc.pop("_id"))
    return doc


def _run(operation, action):
    try:
        return operation()
    except PyMongoError as e:
        logger.exception("MongoDB error while %s", action)
        raise DatabaseError(f"Database error while {action}: {e}") from e


def create_meeting(meeting, owner_id):
    """
    Insert a meeting owned by a user

    Returns:
        str: The new meeting id
    """
    doc = dict(meeting, owner_id=owner_id, created_at=_now(), updated_at=_now())
    doc.pop("id", None)
    result = _run(lambda: get_collection().insert_one(doc), "saving the meeting")
    return str(result.inserted_id)


def get_meeting(meeting_id, owner_id):
    """The meeting, or None when it doesn't exist or belongs to someone else"""
    query = _mine(meeting_id, owner_id)
    return _to_public(_run(lambda: get_collection().find_one(query), "loading the meeting"))


def list_meetings(owner_id):
    """
    List a user's meetings, newest meeting date first (without transcripts)

    Returns:
        list: [{"id", "title", "meeting_date", "created_at", "summary", "decision_count",
                "action_item_count", "open_action_item_count"}]
    """
    def query():
        cursor = get_collection().find(
            {"owner_id": owner_id}, {"title": 1, "meeting_date": 1, "created_at": 1,
                 "minutes.summary": 1, "minutes.decisions": 1, "minutes.action_items.status": 1},
        ).sort([("meeting_date", DESCENDING), ("created_at", DESCENDING)])
        meetings = []
        for doc in cursor:
            minutes = doc.pop("minutes", None) or {}
            items = minutes.get("action_items") or []
            summary = minutes.get("summary") or ""
            meetings.append(dict(
                _to_public(doc),
                summary=summary[:240] + ("…" if len(summary) > 240 else ""),
                decision_count=len(minutes.get("decisions") or []),
                action_item_count=len(items),
                open_action_item_count=sum(1 for item in items if item.get("status") != "Done"),
            ))
        return meetings
    return _run(query, "listing meetings")


def update_meeting(meeting_id, owner_id, fields):
    """Set top-level fields (e.g. {"minutes": {...}}) on a meeting"""
    query = _mine(meeting_id, owner_id)
    update = dict(fields, updated_at=_now())
    result = _run(lambda: get_collection().update_one(query, {"$set": update}), "updating the meeting")
    return result.matched_count > 0


def delete_meeting(meeting_id, owner_id):
    query = _mine(meeting_id, owner_id)
    result = _run(lambda: get_collection().delete_one(query), "deleting the meeting")
    return result.deleted_count > 0


def delete_meetings_of(owner_id):
    """
    Delete every meeting a user owns

    Returns:
        list: Ids of the deleted meetings
    """
    def delete():
        ids = [str(doc["_id"]) for doc in get_collection().find({"owner_id": owner_id}, {"_id": 1})]
        get_collection().delete_many({"owner_id": owner_id})
        return ids
    return _run(delete, "deleting the meetings")


def claim_unowned_meetings(owner_id):
    """
    Give meetings saved before accounts existed to a user (the first account)

    Returns:
        int: Number of meetings claimed
    """
    result = _run(lambda: get_collection().update_many({"owner_id": {"$exists": False}}, {"$set": {"owner_id": owner_id}}),
                  "claiming earlier meetings")
    return result.modified_count


def list_action_items(owner_id):
    """
    All action items across a user's meetings, flattened, with the meeting they came from

    Returns:
        list: [{"meeting_id", "meeting_title", "meeting_date", "id", "task", "owner", "due_date", "priority", "status", "context"}]
    """
    def query():
        cursor = get_collection().find(
            {"owner_id": owner_id, "minutes.action_items.0": {"$exists": True}},
            {"title": 1, "meeting_date": 1, "minutes.action_items": 1},
        ).sort("meeting_date", DESCENDING)
        items = []
        for doc in cursor:
            for item in doc.get("minutes", {}).get("action_items", []):
                items.append(dict(
                    item,
                    meeting_id=str(doc["_id"]),
                    meeting_title=doc.get("title", ""),
                    meeting_date=doc.get("meeting_date"),
                ))
        return items
    return _run(query, "loading action items")


def update_action_item(meeting_id, owner_id, item_id, fields):
    """Update fields (status, owner, due_date, priority) of one action item in place"""
    query = dict(_mine(meeting_id, owner_id), **{"minutes.action_items.id": item_id})
    update = {f"minutes.action_items.$.{key}": value for key, value in fields.items()}
    update["updated_at"] = _now()
    result = _run(
        lambda: get_collection().update_one(query, {"$set": update}),
        "updating the action item",
    )
    return result.matched_count > 0
