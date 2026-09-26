# agents/tasks/fact_checking.py
from agents.tasks.task_base import BaseTask
from models import ClaimList, ClaimVerdict, FactCheckReport

VERDICT_GUIDE = """
Verdicts:
- Verified: reliable sources confirm the claim.
- Partially verified: the core is right but details (numbers, dates) are off or missing.
- Refuted: reliable sources contradict the claim.
- Unverifiable: no reliable source confirms or contradicts it (e.g. internal company figures)."""


class FactCheckingTask(BaseTask):
    """Tasks for checking factual claims made in the meeting"""

    @staticmethod
    def create_fact_check_task(agent, transcript, meeting_info, context, max_claims=8):
        """
        Find and verify the most important factual claims (used inside the analysis crew)

        Args:
            agent: Fact checker agent (has the Wikipedia search tool)
            transcript: Formatted transcript text
            meeting_info: Meeting details
            context: Upstream tasks (the attendee task)
            max_claims: Maximum number of claims to check

        Returns:
            Task: Fact check task
        """
        return BaseTask.create_task(
            agent=agent,
            description=f"""
            Fact-check this meeting.

            1. Find up to {max_claims} checkable factual claims about the outside world: statistics, dates,
               market or industry facts, laws and regulations, facts about public organisations or people.
               Skip opinions, plans, predictions and internal company information.
            2. Check each claim with the Wikipedia search tool.
            3. Give each claim a verdict, a 2-3 sentence explanation and the URLs you used.
            {VERDICT_GUIDE}
            If there are no checkable claims, return an empty list.
            """,
            expected_output="The checked claims, each with speaker, verdict, explanation and sources.",
            output_model=FactCheckReport,
            context=context,
            sections={"MEETING": meeting_info, "TRANSCRIPT": transcript},
        )

    @staticmethod
    def create_claim_extraction_task(agent, transcript, max_claims=12):
        """
        List checkable factual claims (used by the Fact Check tab)

        Returns:
            Task: Claim extraction task
        """
        return BaseTask.create_task(
            agent=agent,
            description=f"""
            List up to {max_claims} checkable factual claims made in this meeting: statistics, dates,
            market or industry facts, laws and regulations, facts about public organisations or people.
            Skip opinions, plans, predictions and internal company information. Word each claim so it
            makes sense on its own, and note who said it. Do not check the claims yet.
            """,
            expected_output="A list of factual claims with the speaker of each.",
            output_model=ClaimList,
            sections={"TRANSCRIPT": transcript},
        )

    @staticmethod
    def create_verification_task(agent, claim, evidence):
        """
        Verify one claim (used by the Fact Check tab)

        Args:
            agent: Fact checker agent
            claim: The claim text
            evidence: Wikipedia extracts gathered for the claim

        Returns:
            Task: Verification task
        """
        return BaseTask.create_task(
            agent=agent,
            description=f"""
            Verify the claim below. Start from the evidence provided; use the Wikipedia search tool if
            you need more. Give a verdict, a 2-3 sentence explanation and the URLs of the sources you used.
            {VERDICT_GUIDE}
            """,
            expected_output="A verdict with explanation and sources.",
            output_model=ClaimVerdict,
            sections={"CLAIM": claim, "EVIDENCE": evidence},
        )
