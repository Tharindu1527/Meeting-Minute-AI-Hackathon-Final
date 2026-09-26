# agents/definitions/summarizer.py
from agents.base import BaseAgent
from agents.registry import register_agent


@register_agent("summarizer")
class SummarizerAgent(BaseAgent):
    """Agent that writes the executive summary"""

    def __init__(self, model=None):
        """Initialize the Summarizer Agent"""
        super().__init__(
            role="Executive Summarizer",
            goal="Write a concise, accurate summary of the meeting for people who did not attend",
            backstory="You write briefings for busy executives and board members. You lead with outcomes "
                      "(decisions and next steps), keep it short, and use plain language.",
            model=model
        )
