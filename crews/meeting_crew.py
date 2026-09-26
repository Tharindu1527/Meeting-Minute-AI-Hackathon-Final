# crews/meeting_crew.py
from agents.tasks import (
    ActionItemsTask,
    AnalysisTask,
    FactCheckingTask,
    ResearchTask,
    SentimentTask,
    SummaryTask,
    TranscriptionTask,
    TranslationTask,
)
from crews.base_crew import AnalysisError, BaseCrew, output_or_repair
from models import (
    ActionItemList,
    AttendeeList,
    FactCheckReport,
    MeetingAnalysis,
    MeetingMinutes,
    MeetingSummary,
    ResearchReport,
    SentimentReport,
    TrackedActionItem,
    TranslatedMinutes,
)

LANGUAGES = ["English", "Spanish", "French", "German", "Portuguese", "Italian", "Dutch",
             "Hindi", "Chinese", "Japanese", "Korean", "Arabic"]

# AssemblyAI language codes for the languages above, so the meeting's own language is not "translated"
LANGUAGE_CODES = {"en": "English", "es": "Spanish", "fr": "French", "de": "German", "pt": "Portuguese",
                  "it": "Italian", "nl": "Dutch", "hi": "Hindi", "zh": "Chinese", "ja": "Japanese",
                  "ko": "Korean", "ar": "Arabic"}


def build_meeting_info(title, meeting_date, language_code=None):
    """Meeting details given to every task (the date is needed to resolve deadlines like 'next Friday')"""
    lines = [f"Title: {title}", f"Meeting date: {meeting_date}"]
    if language_code:
        lines.append(f"Transcript language: {LANGUAGE_CODES.get(language_code, language_code)}")
    return "\n".join(lines)


class MeetingCrew(BaseCrew):
    """
    Crew that turns a meeting transcript into structured minutes

    Core steps (always run):
        attendees -> analysis (agenda, decisions, open issues) -> summary
        -> sentiment -> action items
    Optional steps:
        fact_check: verify factual claims against Wikipedia
        research: add sourced background on the topics discussed
        target_languages: translate summary, decisions and action items
    """

    def __init__(self, model=None, fact_check=False, research=False, target_languages=None):
        super().__init__(model=model)
        self.fact_check = fact_check
        self.research = research
        self.target_languages = list(target_languages or [])

    def languages_to_translate(self, language_code=None):
        source = LANGUAGE_CODES.get(language_code or "", "").lower()
        return [lang for lang in self.target_languages if lang.lower() != source]

    def plan(self, transcript, meeting_info, language_code=None):
        """
        Build the ordered steps for this crew

        Returns:
            list: [(key, label, task, model_cls)] in execution order
        """
        steps = []

        attendees = TranscriptionTask.create_attendee_task(self.agent("transcriber"), transcript, meeting_info)
        steps.append(("attendees", "Identified attendees", attendees, AttendeeList))

        analysis = AnalysisTask.create_analysis_task(
            self.agent("analyzer"), transcript, meeting_info, context=[attendees])
        steps.append(("analysis", "Mapped agenda, decisions and open issues", analysis, MeetingAnalysis))

        summary_context = [attendees, analysis]
        if self.fact_check:
            fact_check = FactCheckingTask.create_fact_check_task(
                self.agent("fact_checker"), transcript, meeting_info, context=[attendees])
            steps.append(("fact_check", "Fact-checked claims", fact_check, FactCheckReport))
            summary_context.append(fact_check)

        summary = SummaryTask.create_summary_task(self.agent("summarizer"), meeting_info, context=summary_context)
        steps.append(("summary", "Wrote the executive summary", summary, MeetingSummary))

        sentiment = SentimentTask.create_sentiment_task(
            self.agent("sentiment"), transcript, meeting_info, context=[attendees])
        steps.append(("sentiment", "Assessed tone and dynamics", sentiment, SentimentReport))

        actions = ActionItemsTask.create_action_items_task(
            self.agent("action_item"), transcript, meeting_info, context=[attendees, analysis])
        steps.append(("action_items", "Extracted action items", actions, ActionItemList))

        if self.research:
            research = ResearchTask.create_research_task(self.agent("researcher"), meeting_info, context=[analysis])
            steps.append(("research", "Researched background topics", research, ResearchReport))

        for language in self.languages_to_translate(language_code):
            translation = TranslationTask.create_translation_task(
                self.agent("translator"), language, context=[summary, analysis, actions])
            steps.append((f"translation:{language}", f"Translated into {language}", translation, TranslatedMinutes))

        return steps

    def run_analysis(self, transcript, meeting_info, language_code=None, progress=None):
        """
        Run the crew and assemble the minutes

        Args:
            transcript: Formatted transcript text
            meeting_info: Output of build_meeting_info
            language_code: Detected transcript language (skips translating into it)
            progress: Optional callback(completed, total, label)

        Returns:
            dict: {"minutes", "fact_check", "research", "translations", "warnings"}
        """
        steps = self.plan(transcript, meeting_info, language_code)
        self.kickoff([(label, task) for _, label, task, _ in steps], progress=progress)
        results = {key: output_or_repair(task, model_cls, self.model) for key, _, task, model_cls in steps}
        return self.assemble(results, steps)

    @staticmethod
    def assemble(results, steps):
        """Combine per-task results into the stored record, noting any step that produced nothing"""
        labels = {key: label for key, label, _, _ in steps}
        warnings = [
            f"Step '{labels[key]}' did not return usable results, so that section is empty."
            for key, value in results.items() if value is None
        ]

        core = ("attendees", "analysis", "summary", "sentiment", "action_items")
        if all(results.get(key) is None for key in core):
            raise AnalysisError("None of the analysis steps returned usable results. Please try again.")

        attendees, analysis = results.get("attendees"), results.get("analysis")
        summary, actions = results.get("summary"), results.get("action_items")
        minutes = MeetingMinutes(
            summary=summary.summary if summary else "",
            highlights=summary.highlights if summary else [],
            key_topics=analysis.key_topics if analysis else [],
            attendees=attendees.attendees if attendees else [],
            agenda_items=analysis.agenda_items if analysis else [],
            decisions=analysis.decisions if analysis else [],
            open_issues=analysis.open_issues if analysis else [],
            action_items=[TrackedActionItem(**item.model_dump()) for item in actions.action_items] if actions else [],
            next_meeting=actions.next_meeting if actions else None,
            sentiment=results.get("sentiment"),
        )

        translations = {
            key.split(":", 1)[1].lower(): value.model_dump()
            for key, value in results.items()
            if key.startswith("translation:") and value is not None
        }
        fact_check, research = results.get("fact_check"), results.get("research")
        return {
            "minutes": minutes.model_dump(),
            "fact_check": fact_check.model_dump() if fact_check else None,
            "research": research.model_dump() if research else None,
            "translations": translations,
            "warnings": warnings,
        }
