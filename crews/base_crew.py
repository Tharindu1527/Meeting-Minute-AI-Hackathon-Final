# crews/base_crew.py
import json
import logging
import re
import sys

from crewai import Crew, Process
from pydantic import ValidationError

from agents.registry import get_agent
from api.llm import AllModelsUnavailable, chat
from utils.config import get_default_model, is_debug

logger = logging.getLogger(__name__)


class AnalysisError(Exception):
    """Raised when the crew could not produce usable results"""


def make_console_output_safe():
    """
    Stop console encoding errors from aborting a crew run

    CrewAI prints emoji status lines even with verbose off. On Windows, when output
    goes to a pipe or a legacy code page (cp1252), printing them raises
    UnicodeEncodeError; replacing unencodable characters avoids that.
    """
    tolerant = {"replace", "backslashreplace", "ignore", "xmlcharrefreplace", "namereplace"}
    for stream in (sys.stdout, sys.stderr):
        encoding = (getattr(stream, "encoding", "") or "").lower().replace("-", "")
        if encoding.startswith("utf") or getattr(stream, "errors", None) in tolerant:
            continue
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(errors="replace")
            except (ValueError, OSError):
                pass


def describe_failure(error, failed="The AI analysis failed"):
    """A readable message for a failed LLM run, calling out free-tier rate limits"""
    text = str(error)
    if isinstance(error, AllModelsUnavailable) or "All Gemini models are unavailable" in text:
        return (f"{text}. Busy models usually recover within a few minutes, and daily free quotas "
                "reset every 24 hours. Please try again shortly.")
    if "PerDay" in text:
        return ("Gemini's free daily quota is used up for every configured model. It resets daily; "
                "try again later, or add models to GEMINI_FALLBACK_MODELS.")
    if any(marker in text for marker in ("429", "RESOURCE_EXHAUSTED", "RateLimit", "rate limit", "quota")):
        return ("Gemini's free-tier rate limit was reached. Wait a minute and try again, "
                "or pick the lighter model in the sidebar.")
    return f"{failed}: {text}"


def parse_model(text, model_cls):
    """
    The JSON object in `text` (ignoring code fences and surrounding prose) as model_cls

    Returns:
        BaseModel|None
    """
    match = re.search(r"\{.*\}", text or "", re.DOTALL)
    if not match:
        return None
    try:
        return model_cls.model_validate_json(match.group(0))
    except ValidationError:
        return None


def structured_output(task, model_cls):
    """
    The task's answer parsed as model_cls

    Returns:
        BaseModel|None: Parsed result, or None if the answer does not fit the schema
    """
    output = getattr(task, "output", None)
    if output is None:
        return None
    result = parse_model(output.raw, model_cls)
    if result is None:
        logger.warning("Task output did not match %s: %.300s", model_cls.__name__, output.raw)
    return result


def repair_output(raw, model_cls, model=None):
    """
    One LLM request that rewrites an answer to fit the schema

    Returns:
        BaseModel|None: The repaired result, or None if that fails too
    """
    if not (raw or "").strip():
        return None
    schema = json.dumps(model_cls.model_json_schema(), separators=(",", ":"))
    prompt = (
        "Rewrite the text below as a single JSON object matching this JSON schema. Keep all of its "
        "information; only fix the structure and use the allowed values. Return only the JSON.\n\n"
        f"SCHEMA:\n{schema}\n\nTEXT:\n{raw}"
    )
    try:
        return parse_model(chat([{"role": "user", "content": prompt}], model=model), model_cls)
    except Exception as e:  # a failed repair leaves the section empty rather than failing the analysis
        logger.warning("Could not repair %s output: %s", model_cls.__name__, e)
        return None


def output_or_repair(task, model_cls, model=None):
    """The task's parsed answer, repairing it with one extra request if it does not fit the schema"""
    result = structured_output(task, model_cls)
    output = getattr(task, "output", None)
    if result is None and output is not None:
        result = repair_output(output.raw, model_cls, model)
    return result


class BaseCrew:
    """Base class for meeting analysis crews"""

    def __init__(self, model=None):
        """
        Args:
            model: Gemini model used by every agent in the crew (defaults to GEMINI_MODEL)
        """
        self.model = model or get_default_model()
        self._agents = {}

    def agent(self, agent_id):
        """This crew's instance of an agent (one per crew, so concurrent crews never share agents)"""
        if agent_id not in self._agents:
            self._agents[agent_id] = get_agent(agent_id, model=self.model)
        return self._agents[agent_id]

    def kickoff(self, steps, progress=None):
        """
        Run steps sequentially

        Args:
            steps: [(label, task)] in execution order
            progress: Optional callback(completed_count, total, label) called after each step
        """
        tasks = [task for _, task in steps]
        agents = list({id(task.agent): task.agent for task in tasks}.values())
        completed = {"count": 0}

        def on_task_done(_output):
            completed["count"] += 1
            if progress:
                index = completed["count"]
                try:
                    progress(index, len(steps), steps[index - 1][0])
                except Exception:  # a UI hiccup must not abort the analysis
                    logger.exception("Progress callback failed")

        crew = Crew(
            agents=agents,
            tasks=tasks,
            process=Process.sequential,
            verbose=is_debug(),
            task_callback=on_task_done,
        )
        try:
            make_console_output_safe()
            return crew.kickoff()
        except Exception as e:
            logger.exception("Crew run failed")
            raise AnalysisError(describe_failure(e)) from e


def run_single_task(agent, task, model_cls):
    """
    Run one task on its own and return its structured result

    Args:
        agent: BaseAgent that owns the task
        task: CrewAI task
        model_cls: Expected Pydantic model

    Returns:
        BaseModel|None
    """
    crew = Crew(agents=[agent.create_agent()], tasks=[task], process=Process.sequential, verbose=is_debug())
    try:
        make_console_output_safe()
        crew.kickoff()
    except Exception as e:
        logger.exception("Single-task run failed")
        raise AnalysisError(describe_failure(e)) from e
    return output_or_repair(task, model_cls, agent.model)
