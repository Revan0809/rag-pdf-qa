"""
Turns a Quorum graph run into a stream of SSE-ready event dicts.

Runs the compiled graph with stream_mode=["updates", "custom"]: "updates"
carries each agent node's trace event (and, on the terminal node, the final
answer/citations/confidence), while "custom" carries the Analyst's
token-by-token output pushed via get_stream_writer(). The caller hands the
yielded {"event", "data"} dicts straight to sse-starlette's
EventSourceResponse.
"""
import json
from typing import Iterator

from app.agents.graph import quorum_graph
from app.agents.state import QuorumState


def run_graph_as_sse(initial_state: QuorumState) -> Iterator[dict]:
    accumulated: dict = dict(initial_state)

    for mode, payload in quorum_graph.stream(initial_state, stream_mode=["updates", "custom"]):
        if mode == "custom":
            if payload.get("type") == "answer_token":
                yield {"event": "token", "data": json.dumps({"text": payload["text"]})}
            elif payload.get("type") == "answer_reset":
                yield {"event": "reset", "data": "{}"}
            elif payload.get("type") == "trace":
                # A tool-call trace event pushed mid-node (e.g. from the
                # Analyst's tool-calling loop), not one returned in a node's
                # "updates" - forward it the same way so the UI timeline
                # doesn't need to know the difference. The node's own
                # "updates" return also includes it, for /ask's non-streaming
                # callers, so it isn't tracked separately here.
                yield {"event": "trace", "data": json.dumps(payload["data"])}
            continue

        # mode == "updates": payload is {node_name: partial_state_update}
        for update in payload.values():
            accumulated.update(update)

            for trace_event in update.get("trace", []):
                yield {"event": "trace", "data": json.dumps(trace_event)}

            if "final_answer" in update:
                yield {
                    "event": "final",
                    "data": json.dumps(
                        {
                            "final_answer": accumulated.get("final_answer"),
                            "citations": accumulated.get("citations", []),
                            "confidence": accumulated.get("confidence"),
                        }
                    ),
                }
