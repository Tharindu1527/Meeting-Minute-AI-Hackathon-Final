# agents/tasks/summary.py
from agents.tasks.task_base import BaseTask
from models import MeetingSummary


class SummaryTask(BaseTask):
    """Tasks that summarise the meeting"""

    @staticmethod
    def create_summary_task(agent, meeting_info, context):
        """
        Write the executive summary from the structured analysis

        Args:
            agent: Summarizer agent
            meeting_info: Meeting details (title, date, language)
            context: Upstream tasks (attendees, analysis, and fact check when enabled)

        Returns:
            Task: Summary task
        """
        return BaseTask.create_task(
            agent=agent,
            description="""
            Using the attendee list and meeting analysis in the context, write the executive summary
            for someone who missed the meeting.

            1. Summary (150-300 words): the purpose of the meeting, the main points discussed, the decisions
               made and what happens next. Lead with outcomes.
            2. Highlights: 3-6 one-line key takeaways.
            3. If fact-check results are in the context, mention any claims that were refuted.
            """,
            expected_output="An executive summary and a short list of key takeaways.",
            output_model=MeetingSummary,
            context=context,
            sections={"MEETING": meeting_info},
        )
