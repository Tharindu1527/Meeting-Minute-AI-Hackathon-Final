# agents/definitions/action_item.py
from agents.base import BaseAgent
from agents.registry import register_agent


@register_agent("action_item")
class ActionItemAgent(BaseAgent):
    """Agent that captures commitments with owners, deadlines and priorities"""

    def __init__(self, model=None):
        """Initialize the Action Item Agent"""
        super().__init__(
            role="Action Item Tracker",
            goal="Capture every commitment made in the meeting with its owner, deadline and priority",
            backstory="You are a project manager who never lets a commitment slip. You listen for phrases "
                      "like 'I'll send', 'can you look into', 'by Friday' and record exactly who owns what "
                      "and by when. Suggestions nobody took on are not action items.",
            model=model
        )
