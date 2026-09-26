# agents/tasks/analysis.py
from agents.tasks.task_base import BaseTask
from models import MeetingAnalysis


class AnalysisTask(BaseTask):
    """Tasks that structure the meeting discussion"""

    @staticmethod
    def create_analysis_task(agent, transcript, meeting_info, context):
        """
        Break the meeting into agenda items, decisions, topics and open issues

        Args:
            agent: Analyzer agent
            transcript: Formatted transcript text
            meeting_info: Meeting details (title, date, language)
            context: Upstream tasks (the attendee task)

        Returns:
            Task: Meeting analysis task
        """
        return BaseTask.create_task(
            agent=agent,
            description="""
            Produce the structured record of this meeting.

            1. Agenda items: split the discussion into its agenda items or topics, in the order they were
               discussed. For each, summarise the discussion in 2-4 sentences naming who contributed what,
               and state the outcome if one was reached.
            2. Decisions: list only decisions that were explicitly agreed or approved. Ideas that were
               floated but not agreed are not decisions, and neither are task assignments ("Ravi, send the
               report") - those are action items and are recorded separately. Record who made or approved
               each decision and why, if stated.
            3. Key topics: 3-8 short labels that cover the meeting.
            4. Open issues: questions left unresolved, items parked for a later meeting, and disagreements
               that still need follow-up. Do not repeat tasks that were assigned to someone.
            """,
            expected_output="Agenda items with discussion and outcomes, decisions, key topics and open issues.",
            output_model=MeetingAnalysis,
            context=context,
            sections={"MEETING": meeting_info, "TRANSCRIPT": transcript},
        )
