# agents/base.py
from crewai import LLM, Agent

from api.llm import REQUEST_TIMEOUT, call_with_fallback, chat_models
from utils.config import (
    GEMINI_OPENAI_BASE_URL,
    get_default_model,
    get_gemini_api_key,
    get_reasoning_effort,
    get_requests_per_minute,
    is_debug,
)

# Appended to every backstory: the minutes must be a faithful record, not a creative one
FAITHFULNESS_RULE = (
    " You only report what is supported by the transcript and the context you are given. "
    "You never invent names, numbers, dates, decisions or commitments; when something is "
    "not stated you leave it empty."
)


class GeminiLLM(LLM):
    """
    CrewAI LLM for Gemini, called through Gemini's OpenAI-compatible endpoint

    Each call is paced to the free-tier quota, waits as long as Gemini asks when
    rate-limited, and falls back to another free model when one is overloaded.
    """

    def call(self, messages, *args, **kwargs):
        # After a tool call CrewAI sends its "Thought/Action/Observation" text as the last,
        # assistant-role message. Gemini rejects requests that end with a model turn, so
        # hand the turn back to the model explicitly.
        if isinstance(messages, list) and messages and messages[-1].get("role") == "assistant":
            messages = messages + [{"role": "user", "content": "Continue."}]
        configured = self.model

        def attempt(model_name):
            self.model = f"openai/{model_name}"
            return LLM.call(self, messages, *args, **kwargs)

        try:
            return call_with_fallback(attempt, chat_models(configured.split("/", 1)[-1]), get_requests_per_minute())
        finally:
            self.model = configured

    def supports_function_calling(self):
        # CrewAI would otherwise send JSON conversion and tool-argument parsing straight to
        # LiteLLM, bypassing call() and its pacing/retries. Its text-based fallback works well.
        return False


def create_llm(model):
    """
    CrewAI LLM for a Gemini model

    Temperature is left at Gemini's default (Google advises against lowering it for
    Gemini 3). Retries are handled by GeminiLLM, so the SDK's own retries are off.
    """
    return GeminiLLM(
        model=f"openai/{model}",
        base_url=GEMINI_OPENAI_BASE_URL,
        api_key=get_gemini_api_key(),
        reasoning_effort=get_reasoning_effort(),
        timeout=REQUEST_TIMEOUT,
        num_retries=0,
    )


class BaseAgent:
    """Base class for all meeting analysis agents"""

    def __init__(self, role, goal, backstory, model=None, tools=None):
        """
        Initialize a base agent

        Args:
            role: Agent's role
            goal: Agent's goal
            backstory: Agent's backstory
            model: Gemini model to use (defaults to GEMINI_MODEL)
            tools: CrewAI tools the agent may call
        """
        self.role = role
        self.goal = goal
        self.backstory = backstory + FAITHFULNESS_RULE
        self.model = model or get_default_model()
        self.tools = list(tools or [])
        self._agent = None

    def create_agent(self):
        """
        The CrewAI agent for this definition

        It is created once and reused, so every task and the crew that runs them
        refer to the same Agent object.

        Returns:
            Agent: CrewAI agent
        """
        if self._agent is None:
            self._agent = Agent(
                role=self.role,
                goal=self.goal,
                backstory=self.backstory,
                llm=create_llm(self.model),
                tools=self.tools,
                allow_delegation=False,
                verbose=is_debug(),
            )
        return self._agent
