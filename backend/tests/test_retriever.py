from unittest.mock import patch

from app.agents.retriever import retrieve


def _chunk(doc_id, page, text, score):
    return {"doc_id": doc_id, "doc_name": "Doc", "page": page, "text": text, "score": score}


def test_retrieve_merges_and_dedupes_across_subqueries_and_documents():
    # Two sub-queries x two documents = 4 query_chunks calls; the same
    # (doc, page, text) chunk comes back from more than one call with
    # different scores, and should be kept once at its best score.
    dupe_low = _chunk("doc-1", 1, "same text", 0.5)
    dupe_high = _chunk("doc-1", 1, "same text", 0.95)
    unique_a = _chunk("doc-1", 2, "other text", 0.7)
    unique_b = _chunk("doc-2", 1, "doc2 text", 0.6)

    call_results = [[dupe_low], [unique_a], [dupe_high], [unique_b]]

    with patch("app.agents.retriever.embed_query", return_value=[0.0]) as mock_embed, patch(
        "app.agents.retriever.query_chunks", side_effect=call_results
    ) as mock_query:
        state = {
            "plan": "multi_hop",
            "standalone_question": "q",
            "sub_queries": ["sub a", "sub b"],
            "document_ids": ["doc-1", "doc-2"],
            "retry_count": 0,
        }
        result = retrieve(state)

    assert mock_embed.call_count == 2
    assert mock_query.call_count == 4

    chunks = result["retrieved_chunks"]
    # The duplicate key (doc-1, page 1, "same text") appears once, at its best score.
    matches = [c for c in chunks if c["doc_id"] == "doc-1" and c["page"] == 1]
    assert len(matches) == 1
    assert matches[0]["score"] == 0.95

    # Results are sorted by score descending.
    assert [c["score"] for c in chunks] == sorted(
        (c["score"] for c in chunks), reverse=True
    )


def test_retrieve_uses_sample_chunks_for_summary_plan():
    with patch("app.agents.retriever.sample_chunks", return_value=[_chunk("doc-1", 1, "t", 1.0)]) as mock_sample, patch(
        "app.agents.retriever.query_chunks"
    ) as mock_query:
        state = {
            "plan": "summary",
            "standalone_question": "summarize this",
            "sub_queries": ["summarize this"],
            "document_ids": ["doc-1"],
            "retry_count": 0,
        }
        retrieve(state)

    mock_sample.assert_called_once()
    mock_query.assert_not_called()


def test_retrieve_widens_top_k_on_retry():
    with patch("app.agents.retriever.embed_query", return_value=[0.0]), patch(
        "app.agents.retriever.query_chunks", return_value=[]
    ) as mock_query:
        state = {
            "plan": "multi_hop",
            "standalone_question": "q",
            "sub_queries": ["q"],
            "document_ids": ["doc-1"],
            "retry_count": 1,
        }
        retrieve(state)

    _, kwargs = mock_query.call_args
    from app.config import settings

    assert kwargs["top_k"] == settings.TOP_K * 2
