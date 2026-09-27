from unittest.mock import patch

from tests.conftest import make_parsed_response

from app.agents.graph import build_graph
from app.agents.verifier import VerifierOutput, skip_reverification, verify


def _base_state(retry_count=0):
    return {
        "standalone_question": "q",
        "draft_answer": "draft",
        "retrieved_chunks": [
            {"doc_id": "doc-1", "doc_name": "Doc", "page": 1, "text": "t", "score": 0.9}
        ],
        "retry_count": retry_count,
    }


def test_verify_flags_retry_on_low_confidence_first_pass():
    fake_output = VerifierOutput(
        unsupported_claims=["claim x"], confidence="low", revised_answer="revised"
    )
    with patch("app.agents.verifier.client") as mock_client:
        mock_client.models.generate_content.return_value = make_parsed_response(fake_output)
        result = verify(_base_state(retry_count=0))

    assert result["confidence"] == "low"
    assert result["retry_count"] == 1
    assert "final_answer" not in result


def test_verify_does_not_retry_twice():
    fake_output = VerifierOutput(
        unsupported_claims=["claim x"], confidence="low", revised_answer="revised"
    )
    with patch("app.agents.verifier.client") as mock_client:
        mock_client.models.generate_content.return_value = make_parsed_response(fake_output)
        result = verify(_base_state(retry_count=1))

    # Already retried once: ship the answer instead of asking for another retry.
    assert "final_answer" in result
    assert "retry_count" not in result


def test_verify_finalizes_on_high_confidence():
    fake_output = VerifierOutput(unsupported_claims=[], confidence="high", revised_answer="draft")
    with patch("app.agents.verifier.client") as mock_client:
        mock_client.models.generate_content.return_value = make_parsed_response(fake_output)
        result = verify(_base_state())

    assert result["final_answer"] == "draft"
    assert result["confidence"] == "high"
    assert "retry_count" not in result


def test_skip_reverification_ships_draft_with_medium_confidence():
    result = skip_reverification({"draft_answer": "second draft"})
    assert result["final_answer"] == "second draft"
    assert result["confidence"] == "medium"


def test_graph_retries_retriever_at_most_once():
    # graph.py does `from app.agents.planner import plan` etc, so patching
    # must target the names as bound in graph.py's own namespace, not the
    # defining modules, or build_graph() would still wire up the originals.
    with patch("app.agents.graph.plan") as mock_plan, patch(
        "app.agents.graph.retrieve"
    ) as mock_retrieve, patch("app.agents.graph.analyze") as mock_analyze, patch(
        "app.agents.graph.verify"
    ) as mock_verify:
        mock_plan.return_value = {
            "plan": "multi_hop",
            "standalone_question": "q",
            "sub_queries": ["q"],
            "trace": [],
        }
        mock_retrieve.return_value = {"retrieved_chunks": [], "trace": []}
        mock_analyze.return_value = {"draft_answer": "d", "citations": [], "trace": []}
        # Always reports low confidence; the graph must still only retry once
        # (skip_reverification handles the second pass, not another verify()).
        mock_verify.return_value = {
            "confidence": "low",
            "unsupported_claims": ["x"],
            "retry_count": 1,
            "trace": [],
        }

        graph = build_graph()
        result = graph.invoke({"question": "q", "chat_history": [], "document_ids": ["d1"]})

    assert mock_retrieve.call_count == 2
    assert mock_analyze.call_count == 2
    assert mock_verify.call_count == 1
    assert result["final_answer"] == "d"
    assert result["confidence"] == "medium"


def test_graph_short_circuits_out_of_scope():
    with patch("app.agents.graph.plan") as mock_plan, patch(
        "app.agents.graph.retrieve"
    ) as mock_retrieve:
        mock_plan.return_value = {
            "plan": "out_of_scope",
            "standalone_question": "q",
            "sub_queries": ["q"],
            "trace": [],
        }

        graph = build_graph()
        result = graph.invoke({"question": "q", "chat_history": [], "document_ids": ["d1"]})

    mock_retrieve.assert_not_called()
    assert "final_answer" in result
    assert result["confidence"] == "high"
