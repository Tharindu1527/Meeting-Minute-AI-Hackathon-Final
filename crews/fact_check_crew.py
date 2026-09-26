# crews/fact_check_crew.py
"""On-demand fact checking used by the Fact Check tab"""
from agents.tasks import FactCheckingTask
from api.wiki_api import format_results, search_wikipedia
from crews.base_crew import AnalysisError, BaseCrew, run_single_task
from models import CheckedClaim, Claim, ClaimList, ClaimVerdict
from utils.transcript import bound_for_llm


class FactCheckCrew(BaseCrew):
    """Extract claims from a transcript, then verify the ones the user picks"""

    def __init__(self, model=None):
        super().__init__(model=model)

    def extract_claims(self, transcript):
        """
        Returns:
            list: [Claim]
        """
        transcript, _ = bound_for_llm(transcript)
        agent = self.agent("fact_checker")
        task = FactCheckingTask.create_claim_extraction_task(agent, transcript)
        result = run_single_task(agent, task, ClaimList)
        if result is None:
            raise AnalysisError("The fact checker did not return a list of claims. Please try again.")
        return result.claims

    def verify_claim(self, claim: Claim):
        """
        Verify one claim, starting from Wikipedia evidence gathered up front

        Returns:
            CheckedClaim
        """
        evidence = format_results(search_wikipedia(claim.claim))
        agent = self.agent("fact_checker")
        task = FactCheckingTask.create_verification_task(agent, claim.claim, evidence)
        verdict = run_single_task(agent, task, ClaimVerdict)
        if verdict is None:
            verdict = ClaimVerdict(status="Unverifiable", explanation="The fact checker did not return a verdict.")
        return CheckedClaim(claim=claim.claim, speaker=claim.speaker, **verdict.model_dump())
