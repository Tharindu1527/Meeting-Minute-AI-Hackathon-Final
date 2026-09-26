# agents/tasks/research.py
from agents.tasks.task_base import BaseTask
from models import ResearchReport


class ResearchTask(BaseTask):
    """Tasks that add background research"""

    @staticmethod
    def create_research_task(agent, meeting_info, context, max_topics=4):
        """
        Research background on the topics the meeting discussed

        Args:
            agent: Researcher agent (has the Wikipedia search tool)
            meeting_info: Meeting details
            context: Upstream tasks (the analysis task)
            max_topics: Maximum number of topics to research

        Returns:
            Task: Research task
        """
        return BaseTask.create_task(
            agent=agent,
            description=f"""
            Using the meeting analysis in the context, pick up to {max_topics} topics where outside background
            would help the attendees make better decisions (industry terms, regulations, technologies,
            organisations, market context).

            For each topic:
            1. Look it up with the Wikipedia search tool.
            2. Write 2-4 sentences of background.
            3. Explain why it matters for what was discussed or decided in this meeting.
            4. List the URLs of the articles you used. Only cite URLs returned by the tool.
            """,
            expected_output="Background research on the meeting's topics, each with relevance and sources.",
            output_model=ResearchReport,
            context=context,
            sections={"MEETING": meeting_info},
        )
