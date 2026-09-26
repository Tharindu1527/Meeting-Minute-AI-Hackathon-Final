# agents/definitions/fact_checker.py
from agents.base import BaseAgent
from agents.registry import register_agent
from agents.tools import wikipedia_search


@register_agent("fact_checker")
class FactCheckerAgent(BaseAgent):
    """Agent that identifies and verifies factual claims made in the meeting"""

    def __init__(self, model=None):
        """Initialize the Fact Checker Agent"""
        super().__init__(
            role="Fact Checker",
            goal="Identify checkable factual claims made in the meeting and verify them against reliable sources",
            backstory="You are a seasoned fact-checker from a major newsroom. You separate facts from opinions "
                      "and plans, check claims against sources, and say 'Unverifiable' rather than guess.",
            model=model,
            tools=[wikipedia_search]
        )
