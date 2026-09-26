# agents/definitions/transcriber.py
from agents.base import BaseAgent
from agents.registry import register_agent


@register_agent("transcriber")
class TranscriberAgent(BaseAgent):
    """Agent that works out who attended and maps transcript speaker labels to people"""

    def __init__(self, model=None):
        """Initialize the Transcriber Agent"""
        super().__init__(
            role="Meeting Secretary",
            goal="Identify everyone who attended the meeting and match each transcript speaker label to a real name and role",
            backstory="You are an experienced company secretary who has taken minutes for hundreds of meetings. "
                      "You pick up names from introductions, from people addressing each other, and from "
                      "context such as who presents which update.",
            model=model
        )
