"""
Planner / Router agent.

One LLM call: classifies the question, rewrites it as a standalone question
using chat history (so follow-ups like "what about page 3?" retrieve
correctly), and produces 1-3 sub-queries for the Retriever.
"""
import time

from google.genai import types
from pydantic import BaseModel

from app.agents.state import ChatTurn, QuestionType, QuorumState
from app.config import settings
from app.llm import call_with_backoff, client

_SYSTEM_PROMPT = (
    "You are the routing agent for a multi-document research assistant. Given "
    "a user's question and recent chat history, decide how it should be "
    "answered.\n\n"
    "Classifications:\n"
    "- simple_lookup: a single fact findable in one or two passages.\n"
    "- summary: asks for an overview, main points, or 'what is this document "
    "about'.\n"
    "- comparison: asks to compare/contrast across two or more documents.\n"
    "- multi_hop: needs combining facts from multiple, possibly disjoint, "
    "passages.\n"
    "- out_of_scope: not answerable from documents at all (chit-chat, asks "
    "about the assistant itself, or clearly unrelated to any document).\n\n"
    "Rewrite the question as a standalone question that makes sense without "
    "the chat history (resolve pronouns and references like 'it' or 'that "
    "page'). If it is already standalone, repeat it unchanged.\n\n"
    "Produce 1 to 3 short search queries that would retrieve the passages "
    "needed to answer it. For summary questions, one broad query is enough. "
    "For out_of_scope questions, still return the standalone question and a "
    "single sub-query equal to it."
)


class PlannerOutput(BaseModel):
    classification: QuestionType
    standalone_question: str
    sub_queries: list[str]


def _format_history(chat_history: list[ChatTurn]) -> str:
    if not chat_history:
        return "(no prior turns)"
    return "\n".join(f"{turn['role']}: {turn['content']}" for turn in chat_history)


def plan(state: QuorumState) -> dict:
    start = time.perf_counter()
    question = state["question"]

    prompt = (
        f"Chat history:\n{_format_history(state.get('chat_history', []))}\n\n"
        f"Question: {question}"
    )

    response = call_with_backoff(
        lambda: client.models.generate_content(
            model=settings.CHAT_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=_SYSTEM_PROMPT,
                temperature=0.0,
                response_mime_type="application/json",
                response_schema=PlannerOutput,
            ),
        )
    )

    result: PlannerOutput | None = response.parsed
    if result is None:
        # The model failed to conform to the schema; fail safe into the most
        # capable path rather than guessing at partial JSON.
        classification: QuestionType = "multi_hop"
        standalone_question = question
        sub_queries = [question]
    else:
        classification = result.classification
        standalone_question = result.standalone_question
        sub_queries = result.sub_queries[:3] or [result.standalone_question]

    duration_ms = int((time.perf_counter() - start) * 1000)
    return {
        "plan": classification,
        "standalone_question": standalone_question,
        "sub_queries": sub_queries,
        "trace": [
            {
                "agent": "planner",
                "status": "completed",
                "summary": f"Classified as {classification} · {len(sub_queries)} search quer{'y' if len(sub_queries) == 1 else 'ies'}",
                "duration_ms": duration_ms,
            }
        ],
    }
