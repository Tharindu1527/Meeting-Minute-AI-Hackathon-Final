# agents/tasks/sentiment.py
from agents.tasks.task_base import BaseTask
from models import SentimentReport


class SentimentTask(BaseTask):
    """Tasks that analyse tone and dynamics"""

    @staticmethod
    def create_sentiment_task(agent, transcript, meeting_info, context):
        """
        Assess the tone of the meeting and each participant

        Args:
            agent: Sentiment agent
            transcript: Formatted transcript text
            meeting_info: Meeting details (title, date, language)
            context: Upstream tasks (the attendee task)

        Returns:
            Task: Sentiment task
        """
        return BaseTask.create_task(
            agent=agent,
            description="""
            Assess the tone and dynamics of this meeting.

            1. Overall tone in one or two words, and a 2-4 sentence summary of the mood and how it shifted.
            2. For each attendee: their tone and one sentence explaining it, with an example of what they said.
            3. Points where participants clearly agreed.
            4. Points of disagreement or tension.
            Base every observation on what was actually said.
            """,
            expected_output="The overall tone, per-speaker tone, and points of agreement and disagreement.",
            output_model=SentimentReport,
            context=context,
            sections={"MEETING": meeting_info, "TRANSCRIPT": transcript},
        )
