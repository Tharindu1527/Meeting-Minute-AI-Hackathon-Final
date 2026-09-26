# app/export.py
"""Render meeting minutes as Markdown, HTML (also used for email), Word (.docx) and a script for audio"""
import io
from html import escape

from docx import Document
from docx.shared import Pt

from models import MeetingMinutes


def load_minutes(meeting):
    return MeetingMinutes.model_validate(meeting.get("minutes") or {})


def _duration(meeting):
    seconds = (meeting.get("transcript") or {}).get("duration_seconds")
    if not seconds:
        return None
    minutes = round(seconds / 60)
    return f"{minutes // 60} h {minutes % 60} min" if minutes >= 60 else f"{minutes} min"


def _attendee_label(attendee):
    return f"{attendee.name} ({attendee.role})" if attendee.role else attendee.name


def _action_fields(item):
    return item.owner or "Unassigned", item.due_date or "No date", item.priority, item.status


def minutes_to_markdown(meeting):
    m = load_minutes(meeting)
    lines = [f"# Meeting minutes: {meeting.get('title', 'Untitled meeting')}", ""]
    meta = [f"**Date:** {meeting.get('meeting_date') or 'Not recorded'}"]
    if _duration(meeting):
        meta.append(f"**Duration:** {_duration(meeting)}")
    lines += ["  \n".join(meta), ""]

    if m.attendees:
        lines += ["## Attendees", ""] + [f"- {_attendee_label(a)}" for a in m.attendees] + [""]
    if m.summary:
        lines += ["## Summary", "", m.summary, ""]
    if m.highlights:
        lines += ["## Key takeaways", ""] + [f"- {h}" for h in m.highlights] + [""]
    if m.agenda_items:
        lines += ["## Discussion", ""]
        for index, item in enumerate(m.agenda_items, 1):
            lines += [f"### {index}. {item.title}", "", item.discussion, ""]
            if item.outcome:
                lines += [f"**Outcome:** {item.outcome}", ""]
    lines += ["## Decisions", ""]
    if m.decisions:
        for d in m.decisions:
            by = f" ({d.decided_by})" if d.decided_by else ""
            lines.append(f"- {d.decision}{by}")
    else:
        lines.append("- No decisions were recorded.")
    lines += ["", "## Action items", ""]
    if m.action_items:
        lines += ["| Task | Owner | Due | Priority | Status |", "|---|---|---|---|---|"]
        for item in m.action_items:
            owner, due, priority, status = _action_fields(item)
            task = item.task.replace("|", "\\|")
            lines.append(f"| {task} | {owner} | {due} | {priority} | {status} |")
    else:
        lines.append("No action items were recorded.")
    lines.append("")
    if m.open_issues:
        lines += ["## Open issues", ""] + [f"- {issue}" for issue in m.open_issues] + [""]
    if m.next_meeting:
        lines += [f"**Next meeting:** {m.next_meeting}", ""]
    return "\n".join(lines).rstrip() + "\n"


_EMAIL_CSS = """
body { font-family: Arial, sans-serif; line-height: 1.5; color: #222; max-width: 760px; margin: 0 auto; padding: 16px; }
h1 { font-size: 22px; border-bottom: 1px solid #ddd; padding-bottom: 8px; }
h2 { font-size: 17px; color: #1f4e79; margin-top: 24px; }
h3 { font-size: 15px; margin-bottom: 4px; }
table { border-collapse: collapse; width: 100%; font-size: 14px; }
th, td { border: 1px solid #ddd; padding: 6px 8px; text-align: left; vertical-align: top; }
th { background: #f3f6f9; }
.meta { color: #555; }
"""


def minutes_to_html(meeting):
    m = load_minutes(meeting)
    e = lambda value: escape(str(value)) if value is not None else ""  # noqa: E731
    title = e(meeting.get("title", "Untitled meeting"))
    parts = [
        "<!DOCTYPE html><html><head><meta charset='utf-8'>",
        f"<title>Meeting minutes: {title}</title><style>{_EMAIL_CSS}</style></head><body>",
        f"<h1>Meeting minutes: {title}</h1>",
        f"<p class='meta'><strong>Date:</strong> {e(meeting.get('meeting_date') or 'Not recorded')}",
    ]
    if _duration(meeting):
        parts.append(f"<br><strong>Duration:</strong> {e(_duration(meeting))}")
    parts.append("</p>")

    if m.attendees:
        parts.append("<h2>Attendees</h2><ul>" + "".join(f"<li>{e(_attendee_label(a))}</li>" for a in m.attendees) + "</ul>")
    if m.summary:
        paragraphs = "".join(f"<p>{e(p)}</p>" for p in m.summary.split("\n\n") if p.strip())
        parts.append(f"<h2>Summary</h2>{paragraphs}")
    if m.highlights:
        parts.append("<h2>Key takeaways</h2><ul>" + "".join(f"<li>{e(h)}</li>" for h in m.highlights) + "</ul>")
    if m.agenda_items:
        parts.append("<h2>Discussion</h2>")
        for index, item in enumerate(m.agenda_items, 1):
            parts.append(f"<h3>{index}. {e(item.title)}</h3><p>{e(item.discussion)}</p>")
            if item.outcome:
                parts.append(f"<p><strong>Outcome:</strong> {e(item.outcome)}</p>")
    parts.append("<h2>Decisions</h2>")
    if m.decisions:
        parts.append("<ul>" + "".join(
            f"<li>{e(d.decision)}{' (' + e(d.decided_by) + ')' if d.decided_by else ''}</li>" for d in m.decisions
        ) + "</ul>")
    else:
        parts.append("<p>No decisions were recorded.</p>")
    parts.append("<h2>Action items</h2>")
    if m.action_items:
        rows = "".join(
            "<tr>" + "".join(f"<td>{e(v)}</td>" for v in (item.task, *_action_fields(item))) + "</tr>"
            for item in m.action_items
        )
        parts.append(
            "<table><tr><th>Task</th><th>Owner</th><th>Due</th><th>Priority</th><th>Status</th></tr>"
            f"{rows}</table>"
        )
    else:
        parts.append("<p>No action items were recorded.</p>")
    if m.open_issues:
        parts.append("<h2>Open issues</h2><ul>" + "".join(f"<li>{e(i)}</li>" for i in m.open_issues) + "</ul>")
    if m.next_meeting:
        parts.append(f"<p><strong>Next meeting:</strong> {e(m.next_meeting)}</p>")
    parts.append("</body></html>")
    return "".join(parts)


def minutes_to_speech_script(meeting, language=None):
    """
    The text read aloud for a meeting: summary, decisions and action items

    Args:
        meeting: Meeting dict
        language: A key of meeting["translations"] (e.g. "spanish"), or None for the original
    """
    if language:
        translation = (meeting.get("translations") or {}).get(language)
        if translation is None:
            raise KeyError(f"No {language} translation for this meeting")
        parts = [translation.get("summary", "")]
        if translation.get("decisions"):
            parts.append("\n".join(translation["decisions"]))
        if translation.get("action_items"):
            parts.append("\n".join(translation["action_items"]))
        return "\n\n".join(p for p in parts if p)

    m = load_minutes(meeting)
    parts = [f"Minutes of {meeting.get('title', 'the meeting')}, held on {meeting.get('meeting_date') or 'an unrecorded date'}.",
             m.summary]
    if m.decisions:
        parts.append("Decisions. " + " ".join(f"{d.decision}." for d in m.decisions))
    if m.action_items:
        spoken = []
        for item in m.action_items:
            line = item.task
            if item.owner:
                line += f", owned by {item.owner}"
            if item.due_date:
                line += f", due {item.due_date}"
            spoken.append(line + ".")
        parts.append("Action items. " + " ".join(spoken))
    return "\n\n".join(p for p in parts if p)


def minutes_to_docx(meeting):
    """
    Returns:
        bytes: A .docx file
    """
    m = load_minutes(meeting)
    doc = Document()
    doc.styles["Normal"].font.size = Pt(11)
    doc.add_heading(f"Meeting minutes: {meeting.get('title', 'Untitled meeting')}", level=0)

    meta = doc.add_paragraph()
    meta.add_run("Date: ").bold = True
    meta.add_run(str(meeting.get("meeting_date") or "Not recorded"))
    if _duration(meeting):
        meta.add_run("\nDuration: ").bold = True
        meta.add_run(_duration(meeting))

    if m.attendees:
        doc.add_heading("Attendees", level=1)
        for attendee in m.attendees:
            doc.add_paragraph(_attendee_label(attendee), style="List Bullet")
    if m.summary:
        doc.add_heading("Summary", level=1)
        for paragraph in m.summary.split("\n\n"):
            if paragraph.strip():
                doc.add_paragraph(paragraph.strip())
    if m.highlights:
        doc.add_heading("Key takeaways", level=1)
        for highlight in m.highlights:
            doc.add_paragraph(highlight, style="List Bullet")
    if m.agenda_items:
        doc.add_heading("Discussion", level=1)
        for index, item in enumerate(m.agenda_items, 1):
            doc.add_heading(f"{index}. {item.title}", level=2)
            doc.add_paragraph(item.discussion)
            if item.outcome:
                outcome = doc.add_paragraph()
                outcome.add_run("Outcome: ").bold = True
                outcome.add_run(item.outcome)

    doc.add_heading("Decisions", level=1)
    if m.decisions:
        for d in m.decisions:
            doc.add_paragraph(d.decision + (f" ({d.decided_by})" if d.decided_by else ""), style="List Bullet")
    else:
        doc.add_paragraph("No decisions were recorded.")

    doc.add_heading("Action items", level=1)
    if m.action_items:
        table = doc.add_table(rows=1, cols=5)
        table.style = "Light Grid Accent 1"
        for cell, header in zip(table.rows[0].cells, ["Task", "Owner", "Due", "Priority", "Status"]):
            cell.text = header
        for item in m.action_items:
            for cell, value in zip(table.add_row().cells, (item.task, *_action_fields(item))):
                cell.text = str(value)
    else:
        doc.add_paragraph("No action items were recorded.")

    if m.open_issues:
        doc.add_heading("Open issues", level=1)
        for issue in m.open_issues:
            doc.add_paragraph(issue, style="List Bullet")
    if m.next_meeting:
        next_meeting = doc.add_paragraph()
        next_meeting.add_run("Next meeting: ").bold = True
        next_meeting.add_run(m.next_meeting)

    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()
