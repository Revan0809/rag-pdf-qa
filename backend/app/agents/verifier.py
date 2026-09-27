"""
Verifier / Critic agent.

One LLM call: checks every claim in the draft against the retrieved chunks,
flags unsupported claims, and returns a confidence score. If confidence is
low and this is the first pass, `graph.py` routes back to the Retriever with
a wider top-K instead of finalizing here.

To keep the per-question LLM call budget at 4 (Planner + Analyst + Verifier,
plus at most one more Analyst on retry), the retry pass is NOT re-verified —
`skip_reverification` ships that second Analyst draft as-is with confidence
downgraded to "medium" instead of spending a 5th call re-checking it.
"""
import time

from google.genai import types
from pydantic import BaseModel

from app.agents.state import Confidence, QuorumState
from app.config import settings
from app.llm import call_with_backoff, client

_SYSTEM_PROMPT = (
    "You are a fact-checking critic. You are given a question, a draft "
    "answer, and the document excerpts it was supposed to be grounded in. "
    "Check every factual claim in the draft against the excerpts.\n\n"
    "List any claims that are NOT supported by the excerpts (empty list if "
    "none). Then give an overall confidence:\n"
    "- high: every claim is directly supported.\n"
    "- medium: minor unsupported details, or the excerpts only partially "
    "cover the question, but the core answer is sound.\n"
    "- low: a significant claim is unsupported, or the excerpts don't "
    "really answer the question.\n\n"
    "If confidence is not high, also provide a revised answer that removes "
    "or hedges the unsupported parts (keep it grounded only in the "
    "excerpts). If confidence is high, repeat the draft answer unchanged as "
    "the revised answer."
)


class VerifierOutput(BaseModel):
    unsupported_claims: list[str]
    confidence: Confidence
    revised_answer: str


def verify(state: QuorumState) -> dict:
    start = time.perf_counter()

    context = "\n\n".join(
        f"[{chunk['doc_name']}, p.{chunk['page']}]\n{chunk['text']}"
        for chunk in state["retrieved_chunks"]
    )
    prompt = (
        f"Question: {state['standalone_question']}\n\n"
        f"Draft answer:\n{state['draft_answer']}\n\n"
        f"Document excerpts:\n{context}"
    )

    response = call_with_backoff(
        lambda: client.models.generate_content(
            model=settings.CHAT_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=_SYSTEM_PROMPT,
                temperature=0.0,
                response_mime_type="application/json",
                response_schema=VerifierOutput,
            ),
        )
    )

    result: VerifierOutput | None = response.parsed
    if result is None:
        # Fail safe: ship the draft as-is rather than block on a malformed
        # verification response.
        confidence: Confidence = "medium"
        unsupported_claims: list[str] = []
        revised_answer = state["draft_answer"]
    else:
        confidence = result.confidence
        unsupported_claims = result.unsupported_claims
        revised_answer = result.revised_answer

    already_retried = state.get("retry_count", 0) > 0
    should_retry = confidence == "low" and not already_retried

    duration_ms = int((time.perf_counter() - start) * 1000)
    summary = f"Confidence: {confidence}"
    if should_retry:
        summary += f" · retrying retrieval ({len(unsupported_claims)} unsupported claim(s))"

    update: dict = {
        "confidence": confidence,
        "unsupported_claims": unsupported_claims,
        "trace": [
            {
                "agent": "verifier",
                "status": "completed",
                "summary": summary,
                "duration_ms": duration_ms,
            }
        ],
    }

    if should_retry:
        update["retry_count"] = 1
    else:
        update["final_answer"] = revised_answer

    return update


def skip_reverification(state: QuorumState) -> dict:
    """Finalizes the retry-pass Analyst output without a second Verifier call."""
    return {
        "final_answer": state["draft_answer"],
        "confidence": "medium",
        "trace": [
            {
                "agent": "verifier",
                "status": "completed",
                "summary": "Re-answered with expanded context; skipped re-verification to stay within the call budget",
                "duration_ms": 0,
            }
        ],
    }
