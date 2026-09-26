# agents/definitions/analyzer.py
from agents.base import BaseAgent
from agents.registry import register_agent


@register_agent("analyzer")
class AnalyzerAgent(BaseAgent):
    """Agent that structures the discussion into agenda items, decisions and open issues"""

    def __init__(self, model=None):
        """Initialize the Analyzer Agent"""
        super().__init__(
            role="Meeting Analyst",
            goal="Break the meeting down into agenda items, key topics, decisions and open issues",
            backstory="You are a chief-of-staff who turns long, meandering discussions into a clear record "
                      "of what was discussed, what was decided and what is still unresolved. You are careful "
                      "to distinguish a firm decision from an idea that was merely floated.",
            model=model
        )
