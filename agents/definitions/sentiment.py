# agents/definitions/sentiment.py
from agents.base import BaseAgent
from agents.registry import register_agent


@register_agent("sentiment")
class SentimentAgent(BaseAgent):
    """Agent that assesses tone, engagement and agreement in the meeting"""

    def __init__(self, model=None):
        """Initialize the Sentiment Agent"""
        super().__init__(
            role="Meeting Dynamics Analyst",
            goal="Assess the tone of the meeting, how each participant engaged, and where people agreed or disagreed",
            backstory="You are an organisational psychologist who facilitates leadership teams. You read "
                      "tone from word choice and reactions, and you back every observation with what was "
                      "actually said.",
            model=model
        )
