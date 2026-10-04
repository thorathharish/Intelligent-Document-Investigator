"""Evidence analyst: the single LLM call per question (LLD section 10)."""
from ..llm import LLMResult, get_llm_client
from ..schemas import AnalystOutput, validate_analyst_output
from .prompts import SYSTEM_PROMPT, build_user_message


def _reissue_ids(output: AnalystOutput) -> AnalystOutput:
    """Give aspects and claims server-side ids (A1.., C1..) and rewrite every reference to them."""
    aspect_ids: dict[str, str] = {}
    for number, aspect in enumerate(output.aspects, start=1):
        aspect_ids.setdefault(aspect.id, f"A{number}")
        aspect.id = f"A{number}"

    claim_ids: dict[str, str] = {}
    for number, claim in enumerate(output.claims, start=1):
        if claim.id:
            claim_ids.setdefault(claim.id, f"C{number}")
        claim.id = f"C{number}"
        claim.aspect = aspect_ids.get(claim.aspect, "")  # unknown aspect -> dropped by the verifier

    for sentence in output.answer:
        sentence.claims = [claim_ids[c] for c in sentence.claims if c in claim_ids]
    for entry in output.supersession:
        entry.aspect = aspect_ids.get(entry.aspect or "")
    return output


def analyse(question: str, evidence: list[dict]) -> LLMResult[AnalystOutput]:
    """Raises LLMUnavailable or LLMBadOutput; the orchestrator turns those into evidence-only mode."""
    user = build_user_message(question, evidence)
    result = get_llm_client().complete_json(SYSTEM_PROMPT, user, validate_analyst_output)
    result.value = _reissue_ids(result.value)
    return result
