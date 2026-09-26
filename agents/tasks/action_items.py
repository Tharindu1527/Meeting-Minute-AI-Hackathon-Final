# agents/tasks/action_items.py
from agents.tasks.task_base import BaseTask
from models import ActionItemList


class ActionItemsTask(BaseTask):
    """Tasks that extract commitments from the meeting"""

    @staticmethod
    def create_action_items_task(agent, transcript, meeting_info, context):
        """
        Extract action items with owners, due dates and priorities

        Args:
            agent: Action item agent
            transcript: Formatted transcript text
            meeting_info: Meeting details, including the meeting date for resolving deadlines
            context: Upstream tasks (attendees and analysis)

        Returns:
            Task: Action items task
        """
        return BaseTask.create_task(
            agent=agent,
            description="""
            Extract every action item from this meeting.

            1. Include only tasks someone committed to or was assigned ("I'll send the report",
               "Ravi, can you check with legal?"). General suggestions nobody took on are not action items.
            2. Task: what needs to be done, starting with a verb.
            3. Owner: the person responsible, using names from the attendee list. Null if nobody was assigned.
            4. Due date: YYYY-MM-DD when a deadline was given. Resolve relative deadlines ("next Friday",
               "end of month") against the meeting date in MEETING. Null if no deadline was given.
            5. Priority: High, Medium or Low, based on the urgency and impact discussed.
            6. Context: one sentence on why the task is needed.
            7. Next meeting: when the next meeting is, if it was scheduled.
            """,
            expected_output="The list of action items with owner, due date, priority and context, and the next meeting date.",
            output_model=ActionItemList,
            context=context,
            sections={"MEETING": meeting_info, "TRANSCRIPT": transcript},
        )
