import json
from unittest.mock import patch

from fastapi.testclient import TestClient
from tests.conftest import make_parsed_response, make_stream_chunks

import main
from app.agents.planner import PlannerOutput
from app.agents.verifier import VerifierOutput


def _parse_sse_events(raw_text: str) -> list[tuple[str, str]]:
    # sse-starlette writes "\r\n" line endings; normalize before splitting
    # into event blocks on the blank line between them.
    events = []
    for block in raw_text.replace("\r\n", "\n").strip().split("\n\n"):
        if not block.strip():
            continue
        event_name = None
        data = None
        for line in block.splitlines():
            if line.startswith("event:"):
                event_name = line[len("event:") :].strip()
            elif line.startswith("data:"):
                data = line[len("data:") :].strip()
        events.append((event_name, data))
    return events


def test_ask_stream_emits_events_in_order():
    planner_output = PlannerOutput(
        classification="simple_lookup", standalone_question="q", sub_queries=["q"]
    )
    verifier_output = VerifierOutput(
        unsupported_claims=[], confidence="high", revised_answer="Answer [Doc, p.1]"
    )

    with (
        # main.py does `from app.vector_store import ... namespace_exists`, so
        # the patch target is main's own namespace, not vector_store's.
        patch("main.namespace_exists", return_value=True),
        patch("app.agents.planner.client") as mock_planner_client,
        patch("app.agents.retriever.embed_query", return_value=[0.0]),
        patch(
            "app.agents.retriever.query_chunks",
            return_value=[
                {
                    "doc_id": "doc-1",
                    "doc_name": "Doc",
                    "page": 1,
                    "text": "excerpt",
                    "score": 0.9,
                }
            ],
        ),
        patch("app.agents.analyst.client") as mock_analyst_client,
        patch("app.agents.verifier.client") as mock_verifier_client,
    ):
        mock_planner_client.models.generate_content.return_value = make_parsed_response(
            planner_output
        )
        mock_analyst_client.models.generate_content_stream.return_value = make_stream_chunks(
            ["Answer ", "[Doc, p.1]"]
        )
        mock_verifier_client.models.generate_content.return_value = make_parsed_response(
            verifier_output
        )

        client = TestClient(main.app)
        with client.stream(
            "POST",
            "/ask/stream",
            json={"document_ids": ["doc-1"], "question": "what is this about?", "history": []},
        ) as response:
            assert response.status_code == 200
            raw = "".join(response.iter_text())

    events = _parse_sse_events(raw)
    event_names = [name for name, _ in events]

    assert event_names.count("trace") == 4  # planner, retriever, analyst, verifier
    assert event_names.index("trace") < event_names.index("token")
    assert event_names[-1] == "final"

    token_events = [json.loads(data) for name, data in events if name == "token"]
    assert "".join(t["text"] for t in token_events) == "Answer [Doc, p.1]"

    final_data = json.loads(events[-1][1])
    assert final_data["confidence"] == "high"
    assert final_data["final_answer"] == "Answer [Doc, p.1]"
    assert final_data["citations"] == [
        {"doc_id": "doc-1", "doc_name": "Doc", "page": 1, "snippet": "excerpt"}
    ]


def test_ask_stream_rejects_empty_question():
    client = TestClient(main.app)
    response = client.post(
        "/ask/stream", json={"document_ids": ["doc-1"], "question": "   ", "history": []}
    )
    assert response.status_code == 400


def test_ask_stream_rejects_missing_document():
    with patch("main.namespace_exists", return_value=False):
        client = TestClient(main.app)
        response = client.post(
            "/ask/stream",
            json={"document_ids": ["doc-1"], "question": "hi", "history": []},
        )
    assert response.status_code == 404
