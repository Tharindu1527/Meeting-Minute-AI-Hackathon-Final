# agents/tasks/translation.py
from agents.tasks.task_base import BaseTask
from models import TranslatedMinutes


class TranslationTask(BaseTask):
    """Tasks that translate the minutes"""

    @staticmethod
    def create_translation_task(agent, language, context):
        """
        Translate the summary, decisions and action items

        Args:
            agent: Translator agent
            language: Target language name, e.g. "Spanish"
            context: Upstream tasks (summary, analysis and action items)

        Returns:
            Task: Translation task
        """
        return BaseTask.create_task(
            agent=agent,
            description=f"""
            Translate the meeting minutes in the context into {language}.

            1. Summary: translate the executive summary.
            2. Decisions: translate each decision.
            3. Action items: translate each one as "task — owner — due date" (omit missing parts).
            Keep people's names, dates, figures and product names unchanged. Set language to "{language}".
            Ignore the rule about writing in the transcript's language: this output must be in {language}.
            """,
            expected_output=f"The summary, decisions and action items translated into {language}.",
            output_model=TranslatedMinutes,
            context=context,
        )
