# agents/tasks/task_base.py
import json

from crewai import Task

# Shared instructions appended to every task
COMMON_RULES = """
Rules:
- Use only the transcript and the context provided. Do not invent names, numbers, dates, decisions or commitments.
- If something was not discussed, leave that field empty or null rather than guessing.
- Refer to people by the names in the attendee list when one is available.
- Write in the same language as the transcript."""


def json_instructions(output_model):
    """Instruction asking for a JSON answer that matches the model's schema"""
    schema = json.dumps(output_model.model_json_schema(), separators=(",", ":"))
    return (
        "Your final answer must be a single JSON object, with no code fences and no text before or after it, "
        f"that matches this JSON schema: {schema}"
    )


class BaseTask:
    """
    Base class for all task types

    Inputs are passed two ways:
      - `sections`: literal text (transcript, meeting details) added to the description
      - `context`: upstream CrewAI tasks; CrewAI hands their outputs to this task

    Structured output is requested through the prompt and parsed by
    crews.base_crew.structured_output rather than CrewAI's `output_pydantic`:
    CrewAI 0.105's converter crashes when a model's JSON needs repair.
    """

    @staticmethod
    def create_task(agent, description, expected_output, output_model=None, context=None, sections=None):
        """
        Create a CrewAI task

        Args:
            agent: BaseAgent instance (or a CrewAI Agent)
            description (str): Task instructions
            expected_output (str): Short description of the result
            output_model: Pydantic model the answer must match (requested as JSON)
            context (list, optional): Upstream tasks whose outputs this task needs
            sections (dict, optional): {"LABEL": text} blocks appended to the description

        Returns:
            Task: CrewAI task
        """
        crew_agent = agent.create_agent() if hasattr(agent, "create_agent") else agent

        full_description = description.strip() + "\n" + COMMON_RULES
        for label, content in (sections or {}).items():
            full_description += f"\n\n===== {label} =====\n{content}"

        if output_model is not None:
            expected_output = f"{expected_output}\n{json_instructions(output_model)}"

        task_kwargs = {
            "description": full_description,
            "expected_output": expected_output,
            "agent": crew_agent,
        }
        if context:
            task_kwargs["context"] = list(context)
        return Task(**task_kwargs)
