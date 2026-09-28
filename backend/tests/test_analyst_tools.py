from unittest.mock import patch

import pytest
from tests.conftest import make_function_call, make_stream_chunks

from app.agents.analyst import analyze


@pytest.fixture(autouse=True)
def _no_op_stream_writer():
    # analyze() calls LangGraph's get_stream_writer(), which requires an
    # actual graph execution context; these tests call analyze() directly
    # as a unit, so give it a harmless stand-in instead of the real one.
    with patch("app.agents.analyst.get_stream_writer", return_value=lambda *args, **kwargs: None):
        yield


def _chunk(doc_id, page, text, score=0.9, doc_name="Doc"):
    return {"doc_id": doc_id, "doc_name": doc_name, "page": page, "text": text, "score": score}


def _base_state(retry_count=0):
    return {
        "standalone_question": "What does page 2 say?",
        "retrieved_chunks": [_chunk("doc-1", 1, "orig text", score=0.5)],
        "document_ids": ["doc-1"],
        "retry_count": retry_count,
    }


def test_tool_call_is_executed_and_fed_back_into_final_answer():
    call_round = make_stream_chunks(
        [], function_calls=[make_function_call("search_documents", {"query": "page 2", "top_k": 3})]
    )
    final_round = make_stream_chunks(["The answer is 42 ", "[Doc, p.2]."])
    tool_chunk = _chunk("doc-1", 2, "tool-fetched text", score=0.9)

    with patch("app.agents.analyst.client") as mock_client, patch(
        "app.agents.analyst.dispatch_tool", return_value=({"results": []}, [tool_chunk])
    ) as mock_dispatch:
        mock_client.models.generate_content_stream.side_effect = [call_round, final_round]

        result = analyze(_base_state())

    assert mock_client.models.generate_content_stream.call_count == 2
    mock_dispatch.assert_called_once_with("search_documents", {"query": "page 2", "top_k": 3}, ["doc-1"])

    assert result["draft_answer"] == "The answer is 42 [Doc, p.2]."
    # The citation resolves against the tool-fetched chunk, not just the
    # chunks the Retriever originally handed to the Analyst.
    assert result["citations"] == [
        {"doc_id": "doc-1", "doc_name": "Doc", "page": 2, "snippet": "tool-fetched text"}
    ]

    tool_trace = [t for t in result["trace"] if "search_documents" in t["summary"]]
    assert len(tool_trace) == 1
    assert tool_trace[0]["agent"] == "analyst"
    assert "1 result(s)" in tool_trace[0]["summary"]


def test_tool_round_cap_forces_a_final_tool_free_round():
    call_round = make_stream_chunks(
        [], function_calls=[make_function_call("list_documents", {})]
    )
    final_round = make_stream_chunks(["No more tools for you."])

    with patch("app.agents.analyst.client") as mock_client, patch(
        "app.agents.analyst.dispatch_tool", return_value=({"documents": []}, [])
    ):
        mock_client.models.generate_content_stream.side_effect = [call_round, call_round, final_round]

        result = analyze(_base_state())

    # Exactly 2 tool rounds + 1 forced final round - never a 4th call.
    assert mock_client.models.generate_content_stream.call_count == 3
    third_call_kwargs = mock_client.models.generate_content_stream.call_args_list[2].kwargs
    assert third_call_kwargs["config"].tools is None

    assert result["draft_answer"] == "No more tools for you."


def test_unknown_tool_name_does_not_crash_the_loop():
    call_round = make_stream_chunks(
        [], function_calls=[make_function_call("delete_everything", {})]
    )
    final_round = make_stream_chunks(["Here's what I found anyway."])

    with patch("app.agents.analyst.client") as mock_client:
        # dispatch_tool is NOT mocked here - exercises the real
        # "unknown tool" guardrail in tools.py end to end.
        mock_client.models.generate_content_stream.side_effect = [call_round, final_round]

        result = analyze(_base_state())

    assert result["draft_answer"] == "Here's what I found anyway."
    error_trace = [t for t in result["trace"] if "Unknown tool" in t["summary"]]
    assert len(error_trace) == 1


def test_retry_pass_skips_tool_calling_entirely():
    final_round = make_stream_chunks(["Plain answer, no tools involved."])

    with patch("app.agents.analyst.client") as mock_client, patch(
        "app.agents.analyst.dispatch_tool"
    ) as mock_dispatch:
        mock_client.models.generate_content_stream.return_value = final_round

        result = analyze(_base_state(retry_count=1))

    assert mock_client.models.generate_content_stream.call_count == 1
    mock_dispatch.assert_not_called()
    call_kwargs = mock_client.models.generate_content_stream.call_args.kwargs
    assert call_kwargs["config"].tools is None
    assert result["draft_answer"] == "Plain answer, no tools involved."
