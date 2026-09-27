"""
Shared state schema passed between agents in the Quorum graph.

Every agent reads from and writes a partial update to this TypedDict.
`trace` uses `operator.add` as its reducer so each agent's single-event
update is appended to the running list rather than overwriting it.
"""
import operator
from typing import Literal, TypedDict

from typing_extensions import Annotated

QuestionType = Literal["simple_lookup", "summary", "comparison", "multi_hop", "out_of_scope"]
Confidence = Literal["high", "medium", "low"]
TraceStatus = Literal["started", "completed", "error"]


class ChatTurn(TypedDict):
    role: Literal["user", "assistant"]
    content: str


class RetrievedChunk(TypedDict):
    doc_id: str
    doc_name: str
    page: int
    text: str
    score: float


class Citation(TypedDict):
    doc_id: str
    doc_name: str
    page: int
    snippet: str


class TraceEvent(TypedDict):
    agent: str
    status: TraceStatus
    summary: str
    duration_ms: int


class QuorumState(TypedDict, total=False):
    # ---- Input ----
    question: str
    chat_history: list[ChatTurn]
    document_ids: list[str]

    # ---- Planner output ----
    plan: QuestionType
    standalone_question: str
    sub_queries: list[str]

    # ---- Retriever output ----
    retrieved_chunks: list[RetrievedChunk]
    retry_count: int

    # ---- Analyst output ----
    draft_answer: str
    citations: list[Citation]

    # ---- Verifier output ----
    confidence: Confidence
    unsupported_claims: list[str]

    # ---- Final ----
    final_answer: str

    trace: Annotated[list[TraceEvent], operator.add]
