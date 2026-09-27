"""
Analyst / Synthesizer agent.

One LLM call: writes the answer using only retrieved chunks, with inline
citations like `[Doc name, p.4]`. Streams tokens through LangGraph's custom
stream channel as they arrive, so `/ask/stream` can forward them to the
client live instead of waiting for the whole answer to finish.
"""
import re
import time

from google.genai import types
from langgraph.config import get_stream_writer

from app.agents.state import Citation, QuorumState, RetrievedChunk
from app.config import settings
from app.llm import call_with_backoff, client

_SYSTEM_PROMPT = (
    "You are a research analyst. Answer the user's question using ONLY the "
    "provided document excerpts. Cite every claim inline using the exact "
    "format [Doc name, p.X], where Doc name and X are copied from the "
    "excerpt you drew on. If the excerpts don't contain enough information, "
    "say so plainly instead of guessing. Keep the answer concise and "
    "well-organized, using short paragraphs or a bulleted list where that's "
    "clearer.\n\n"
    "If the question asks for a comparison across documents, structure the "
    "answer as a short side-by-side: one section per document, then a brief "
    "synthesis of the similarities and differences, each part still citing "
    "sources."
)

_CITATION_PATTERN = re.compile(r"\[([^\[\]]+?),\s*p\.\s*(\d+)\]")


def _format_chunks(chunks: list[RetrievedChunk]) -> str:
    return "\n\n".join(
        f"[{chunk['doc_name']}, p.{chunk['page']}]\n{chunk['text']}" for chunk in chunks
    )


def _extract_citations(answer: str, chunks: list[RetrievedChunk]) -> list[Citation]:
    """
    Matches `[Doc name, p.X]` markers in the answer back to the retrieved
    chunks, so the frontend gets a deduplicated, clickable citation list
    without a second LLM call.
    """
    cited: dict[tuple, Citation] = {}
    for doc_name, page_str in _CITATION_PATTERN.findall(answer):
        page = int(page_str)
        for chunk in chunks:
            if chunk["doc_name"] == doc_name.strip() and chunk["page"] == page:
                key = (chunk["doc_id"], chunk["page"])
                if key not in cited:
                    cited[key] = {
                        "doc_id": chunk["doc_id"],
                        "doc_name": chunk["doc_name"],
                        "page": chunk["page"],
                        "snippet": chunk["text"][:220],
                    }
                break
    return list(cited.values())


def analyze(state: QuorumState) -> dict:
    start = time.perf_counter()
    writer = get_stream_writer()

    chunks = state["retrieved_chunks"]
    context = _format_chunks(chunks)
    prompt = (
        f"Document excerpts:\n{context}\n\n"
        f"Question: {state['standalone_question']}\n\n"
        "Answer using only the excerpts above, with inline citations."
    )

    def _run_stream() -> str:
        parts: list[str] = []
        for response_chunk in client.models.generate_content_stream(
            model=settings.CHAT_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=_SYSTEM_PROMPT,
                temperature=0.2,
            ),
        ):
            text = response_chunk.text or ""
            if text:
                parts.append(text)
                writer({"type": "answer_token", "text": text})
        return "".join(parts)

    draft_answer = call_with_backoff(
        _run_stream,
        # A retry re-runs _run_stream from scratch, which re-emits every
        # token already sent for the failed attempt; tell listeners to
        # discard what they have so the client doesn't show duplicated text.
        on_retry=lambda: writer({"type": "answer_reset"}),
    )
    citations = _extract_citations(draft_answer, chunks)

    duration_ms = int((time.perf_counter() - start) * 1000)
    return {
        "draft_answer": draft_answer,
        "citations": citations,
        "trace": [
            {
                "agent": "analyst",
                "status": "completed",
                "summary": f"Drafted answer with {len(citations)} citation(s)",
                "duration_ms": duration_ms,
            }
        ],
    }
