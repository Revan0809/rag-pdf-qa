from unittest.mock import patch

from app.agents.tools import dispatch_tool


def _chunk(doc_id, page, text, score=0.9, doc_name="Doc"):
    return {"doc_id": doc_id, "doc_name": doc_name, "page": page, "text": text, "score": score}


def test_dispatch_unknown_tool_returns_error_without_crashing():
    result, chunks = dispatch_tool("delete_everything", {}, ["doc-1"])

    assert result == {"error": "Unknown tool 'delete_everything'."}
    assert chunks == []


def test_get_page_rejects_document_id_outside_selection():
    with patch("app.agents.tools.query_chunks_by_page") as mock_query_by_page:
        result, chunks = dispatch_tool(
            "get_page", {"document_id": "doc-not-selected", "page": 2}, ["doc-1", "doc-2"]
        )

    assert "error" in result
    assert "doc-not-selected" in result["error"]
    assert chunks == []
    mock_query_by_page.assert_not_called()


def test_get_page_allows_a_selected_document_id():
    with patch(
        "app.agents.tools.query_chunks_by_page",
        return_value=[_chunk("doc-1", 2, "page two text")],
    ) as mock_query_by_page:
        result, chunks = dispatch_tool("get_page", {"document_id": "doc-1", "page": 2}, ["doc-1"])

    mock_query_by_page.assert_called_once_with("doc-1", 2)
    assert "error" not in result
    assert result["results"] == [{"doc_name": "Doc", "page": 2, "text": "page two text"}]
    assert chunks == [_chunk("doc-1", 2, "page two text")]


def test_get_page_rejects_non_integer_page():
    result, chunks = dispatch_tool("get_page", {"document_id": "doc-1", "page": "not-a-number"}, ["doc-1"])

    assert "error" in result
    assert chunks == []


def test_search_documents_clamps_top_k_within_range():
    with patch("app.agents.tools.embed_query", return_value=[0.0]), patch(
        "app.agents.tools.query_chunks", return_value=[]
    ) as mock_query:
        dispatch_tool("search_documents", {"query": "pricing", "top_k": 999}, ["doc-1"])

    _, kwargs = mock_query.call_args
    assert kwargs["top_k"] == 10  # clamped to _MAX_TOP_K

    with patch("app.agents.tools.embed_query", return_value=[0.0]), patch(
        "app.agents.tools.query_chunks", return_value=[]
    ) as mock_query:
        dispatch_tool("search_documents", {"query": "pricing", "top_k": 0}, ["doc-1"])

    _, kwargs = mock_query.call_args
    assert kwargs["top_k"] == 1  # clamped to _MIN_TOP_K


def test_search_documents_rejects_empty_query():
    result, chunks = dispatch_tool("search_documents", {"query": "   "}, ["doc-1"])

    assert "error" in result
    assert chunks == []


def test_list_documents_only_covers_allowed_ids():
    with patch(
        "app.agents.tools.get_doc_metadata",
        side_effect=lambda doc_id: {"doc_name": f"Name for {doc_id}", "num_pages": 3},
    ) as mock_get_metadata:
        result, chunks = dispatch_tool("list_documents", {}, ["doc-1", "doc-2"])

    assert mock_get_metadata.call_count == 2
    assert [d["document_id"] for d in result["documents"]] == ["doc-1", "doc-2"]
    assert chunks == []
