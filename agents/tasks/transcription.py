# agents/tasks/transcription.py
from agents.tasks.task_base import BaseTask
from models import AttendeeList


class TranscriptionTask(BaseTask):
    """Tasks that work on the transcript itself"""

    @staticmethod
    def create_attendee_task(agent, transcript, meeting_info):
        """
        Identify attendees and map speaker labels to names

        Args:
            agent: Transcriber agent
            transcript: Formatted transcript text
            meeting_info: Meeting details (title, date, language)

        Returns:
            Task: Attendee identification task
        """
        return BaseTask.create_task(
            agent=agent,
            description="""
            Identify everyone who spoke in this meeting.

            1. For each speaker label in the transcript (e.g. "Speaker A"), work out the person's real name
               from introductions, people addressing each other ("Thanks, Priya"), or sign-offs.
            2. Record each person's role or title if it is mentioned or clearly implied
               (e.g. chairs the meeting, presents the finance update).
            3. If a name cannot be determined, use the speaker label as the name.
            4. If the transcript has no speaker labels, list the people clearly taking part by name.
            """,
            expected_output="The list of attendees with their names, roles and transcript speaker labels.",
            output_model=AttendeeList,
            sections={"MEETING": meeting_info, "TRANSCRIPT": transcript},
        )
