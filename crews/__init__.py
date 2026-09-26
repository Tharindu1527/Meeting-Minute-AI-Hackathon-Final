# crews/__init__.py
"""
Meeting Analysis Crews Package

MeetingCrew orchestrates the agents that turn a transcript into minutes;
its optional steps (fact checking, research, translation) are switched on
per analysis. FactCheckCrew runs on-demand claim checking.
"""

from crews.base_crew import AnalysisError, BaseCrew
from crews.fact_check_crew import FactCheckCrew
from crews.meeting_crew import LANGUAGES, MeetingCrew, build_meeting_info


def get_crew(model=None, fact_check=False, research=False, target_languages=None):
    """
    Create a meeting crew with the requested optional steps

    Args:
        model: LLM model for all agents
        fact_check: Add the fact-checker agent
        research: Add the background researcher agent
        target_languages: Languages to translate the minutes into

    Returns:
        MeetingCrew
    """
    kwargs = {"fact_check": fact_check, "research": research, "target_languages": target_languages}
    if model:
        kwargs["model"] = model
    return MeetingCrew(**kwargs)
