# server/routes/action_items.py
"""Action item tracker across all meetings"""
from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from database import mongodb
from models.minutes import Priority, Status

router = APIRouter(tags=["action items"])


def _as_date(value):
    try:
        return date.fromisoformat(str(value)[:10]) if value else None
    except ValueError:
        return None


@router.get("/action-items")
def list_action_items():
    """Every action item with its meeting, flagged overdue when past due and not done"""
    today = date.today()
    items = []
    for item in mongodb.list_action_items():
        due = _as_date(item.get("due_date"))
        items.append(dict(item, overdue=bool(due and due < today and item.get("status") != "Done")))
    return items


class ActionItemUpdate(BaseModel):
    owner: Optional[str] = None
    due_date: Optional[date] = None
    priority: Optional[Priority] = None
    status: Optional[Status] = None


@router.patch("/meetings/{meeting_id}/action-items/{item_id}")
def update_action_item(meeting_id: str, item_id: str, body: ActionItemUpdate):
    """Update only the fields sent; send null to clear owner or due date"""
    fields = body.model_dump(exclude_unset=True)
    if not fields:
        raise HTTPException(status_code=400, detail="Nothing to update.")
    if "due_date" in fields:
        fields["due_date"] = fields["due_date"].isoformat() if fields["due_date"] else None
    if "owner" in fields:
        fields["owner"] = (fields["owner"] or "").strip() or None
    for required in ("priority", "status"):
        if required in fields and fields[required] is None:
            raise HTTPException(status_code=400, detail=f"{required} cannot be empty.")
    if not mongodb.update_action_item(meeting_id, item_id, fields):
        raise HTTPException(status_code=404, detail="Action item not found")
    return {"updated": fields}
