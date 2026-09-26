# agents/definitions/researcher.py
from agents.base import BaseAgent
from agents.registry import register_agent
from agents.tools import wikipedia_search


@register_agent("researcher")
class ResearcherAgent(BaseAgent):
    """Agent that adds background research on topics discussed in the meeting"""

    def __init__(self, model=None):
        """Initialize the Researcher Agent"""
        super().__init__(
            role="Background Researcher",
            goal="Give attendees useful background on the topics the meeting discussed, with sources",
            backstory="You are a research analyst who prepares briefing notes. You find the context that "
                      "helps a team make better decisions and always cite where it came from.",
            model=model,
            tools=[wikipedia_search]
        )
