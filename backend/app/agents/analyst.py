"""
Analyst / Synthesizer agent.

Writes the answer from the Retriever's chunks, with inline citations like
`[Doc name, p.4]`, streaming tokens through LangGraph's custom stream
channel as they arrive so `/ask/stream` can forward them live.

Unlike the original single-call version, this is now a bounded
tool-calling loop: the Analyst may call search_documents, get_page, or
list_documents (native Gemini function calling, see tools.py) when the
Retriever's chunks don't look like enough evidence - typically multi_hop or
comparison questions. At most `_MAX_TOOL_ROUNDS` rounds are allowed to
request a tool; if it still wants to after that, a final round runs with no
tools available at all, guaranteeing termination. On the Verifier-triggered
retry pass, tool-calling is skipped entirely (retry_count > 0) - that pass
already gets a wider Retriever top-K, and letting it also spend up to 3 more
LLM calls would blow the per-question budget for little benefit. See
README.md's call-budget table for the exact worst case this bounds to.
"""
import re
import time

from google.genai import types
from langgraph.config import get_stream_writer

from app.agents.state import Citation, QuorumState, RetrievedChunk, TraceEvent
from app.agents.tools import TOOLS, dispatch_tool
from app.config import settings
from app.llm import call_with_backoff, client

_MAX_TOOL_ROUNDS = 2

_SYSTEM_PROMPT = (
    "You are a research analyst. Answer the user's question using the "
    "provided document excerpts. Cite every claim inline using the exact "
    "format [Doc name, p.X], where Doc name and X are copied from the "
    "excerpt you drew on. Keep the answer concise and well-organized, using "
    "short paragraphs or a bulleted list where that's clearer.\n\n"
    "If the excerpts don't contain enough information to answer "
    "confidently, you may call search_documents, get_page, or "
    "list_documents to gather more evidence before answering - but only "
    "when you actually need to; most questions are already answerable from "
    "what you've been given. Once you do have enough evidence, answer "
    "directly; don't call a tool just to double-check something you're "
    "already confident about. If even after using the tools available "
    "there still isn't enough information, say so plainly instead of "
    "guessing.\n\n"
    "If the question asks for a comparison across documents, structure the "
    "answer as a short side-by-side: one section per document, then a "
    "brief synthesis of the similarities and differences, each part still "
    "citing sources."
)

_CITATION_PATTERN = re.compile(r"\[([^\[\]]+?),\s*p\.\s*(\d+)\]")


def _format_chunks(chunks: list[RetrievedChunk]) -> str:
    return "\n\n".join(
        f"[{chunk['doc_name']}, p.{chunk['page']}]\n{chunk['text']}" for chunk in chunks
    )


def _format_args(args: dict | None) -> str:
    if not args:
        return ""
    return ", ".join(f"{key}={value!r}" for key, value in args.items())


def _extract_citations(answer: str, chunks: list[RetrievedChunk]) -> list[Citation]:
    """
    Matches `[Doc name, p.X]` markers in the answer back to chunks the
    Analyst actually saw - the Retriever's chunks plus anything a tool call
    fetched - so the frontend gets a deduplicated, clickable citation list
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


def _build_prompt(question: str, chunks: list[RetrievedChunk]) -> str:
    context = _format_chunks(chunks)
    return (
        f"Document excerpts:\n{context}\n\n"
        f"Question: {question}\n\n"
        "Answer using the excerpts above, with inline citations. Call a "
        "tool first only if they clearly aren't enough."
    )


def _run_round(
    contents: list[types.Content], tools_enabled: bool, writer
) -> tuple[str, list[types.FunctionCall]]:
    """Streams one Gemini turn. Returns (text, function_calls)."""

    def _stream() -> tuple[str, list[types.FunctionCall]]:
        text_parts: list[str] = []
        function_calls: list[types.FunctionCall] = []
        config = types.GenerateContentConfig(
            system_instruction=_SYSTEM_PROMPT,
            temperature=0.2,
            tools=TOOLS if tools_enabled else None,
        )
        for response_chunk in client.models.generate_content_stream(
            model=settings.CHAT_MODEL,
            contents=contents,
            config=config,
        ):
            text = response_chunk.text or ""
            if text:
                text_parts.append(text)
                writer({"type": "answer_token", "text": text})
            if response_chunk.function_calls:
                function_calls.extend(response_chunk.function_calls)
        return "".join(text_parts), function_calls

    text, function_calls = call_with_backoff(
        _stream,
        # A retry re-runs _stream from scratch, which re-emits every token
        # already sent for the failed attempt; tell listeners to discard
        # what they have so the client doesn't show duplicated text.
        on_retry=lambda: writer({"type": "answer_reset"}),
    )

    if function_calls and text:
        # A stray preamble streamed before the model decided to call a
        # tool; discard it so the client isn't left with a half-answer that
        # a later round's real answer would otherwise just append to.
        writer({"type": "answer_reset"})
        text = ""

    return text, function_calls


def analyze(state: QuorumState) -> dict:
    start = time.perf_counter()
    writer = get_stream_writer()

    chunks: list[RetrievedChunk] = list(state["retrieved_chunks"])
    tool_trace_events: list[TraceEvent] = []
    tools_enabled = state.get("retry_count", 0) == 0

    contents: list[types.Content] = [
        types.Content(
            role="user",
            parts=[types.Part.from_text(text=_build_prompt(state["standalone_question"], chunks))],
        )
    ]

    if not tools_enabled:
        final_text, _ = _run_round(contents, tools_enabled=False, writer=writer)
    else:
        final_text = ""
        for _round in range(_MAX_TOOL_ROUNDS):
            text, function_calls = _run_round(contents, tools_enabled=True, writer=writer)
            if not function_calls:
                final_text = text
                break

            model_parts = [
                types.Part.from_function_call(name=call.name, args=call.args or {})
                for call in function_calls
            ]
            response_parts = []
            for call in function_calls:
                tool_start = time.perf_counter()
                result, tool_chunks = dispatch_tool(
                    call.name, call.args or {}, state["document_ids"]
                )
                tool_duration_ms = int((time.perf_counter() - tool_start) * 1000)
                chunks.extend(tool_chunks)

                args_str = _format_args(call.args)
                if "error" in result:
                    summary = f"{call.name}({args_str}) -> error: {result['error']}"
                else:
                    summary = f"{call.name}({args_str}) -> {len(tool_chunks)} result(s)"

                trace_event: TraceEvent = {
                    "agent": "analyst",
                    "status": "completed",
                    "summary": summary,
                    "duration_ms": tool_duration_ms,
                }
                tool_trace_events.append(trace_event)
                writer({"type": "trace", "data": trace_event})

                response_parts.append(types.Part.from_function_response(name=call.name, response=result))

            contents.append(types.Content(role="model", parts=model_parts))
            contents.append(types.Content(role="user", parts=response_parts))
        else:
            # Exhausted _MAX_TOOL_ROUNDS and the model still wants to call a
            # tool - force a final, tool-free round so this always
            # terminates instead of looping (or costing LLM calls) forever.
            contents.append(
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_text(
                            text=(
                                "You've reached the tool call limit for this question. "
                                "Answer now using only the evidence already gathered."
                            )
                        )
                    ],
                )
            )
            final_text, _ = _run_round(contents, tools_enabled=False, writer=writer)

    citations = _extract_citations(final_text, chunks)

    duration_ms = int((time.perf_counter() - start) * 1000)
    return {
        "draft_answer": final_text,
        "citations": citations,
        "trace": tool_trace_events
        + [
            {
                "agent": "analyst",
                "status": "completed",
                "summary": f"Drafted answer with {len(citations)} citation(s)",
                "duration_ms": duration_ms,
            }
        ],
    }
