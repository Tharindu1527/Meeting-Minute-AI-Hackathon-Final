# agents/definitions/translator.py
from agents.base import BaseAgent
from agents.registry import register_agent


@register_agent("translator")
class TranslatorAgent(BaseAgent):
    """Agent that translates the minutes into other languages"""

    def __init__(self, model=None):
        """Initialize the Translator Agent"""
        super().__init__(
            role="Business Translator",
            goal="Translate meeting minutes accurately and naturally while keeping names, dates and figures unchanged",
            backstory="You are a professional translator for international business teams. Your translations "
                      "read naturally to native speakers and never change the meaning.",
            model=model
        )
