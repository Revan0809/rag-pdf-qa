"""
Tool declarations and dispatch for the Analyst's native function calling.

Each tool is declared with a plain JSON schema (google-genai's
`parameters_json_schema`) rather than a raw Python callable, so dispatch
stays manual and inspectable: every argument is validated here before
touching Pinecone, a document_id outside the question's selection is
rejected rather than fetched, and an unrecognized tool name returns an
error result instead of raising. None of this costs an LLM call by itself -
only the Gemini turns that request or consume a tool result do.
"""
from google.genai import types

from app.agents.retrieval import merge_chunks
from app.agents.state import RetrievedChunk
from app.embeddings import embed_query
from app.vector_store import get_doc_metadata, query_chunks, query_chunks_by_page

_DEFAULT_TOP_K = 5
_MIN_TOP_K = 1
_MAX_TOP_K = 10

_SEARCH_DOCUMENTS = types.FunctionDeclaration(
    name="search_documents",
    description=(
        "Search the documents selected for this question for chunks relevant "
        "to a query. Use this when the excerpts you've already been given "
        "don't contain enough evidence to answer confidently - for example a "
        "multi-hop question that needs a different part of a document, or a "
        "comparison question that needs a specific detail from one of them."
    ),
    parameters_json_schema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query to embed and match against document chunks.",
            },
            "top_k": {
                "type": "integer",
                "description": "Number of chunks to return. 1-10, defaults to 5.",
            },
        },
        "required": ["query"],
    },
)

_GET_PAGE = types.FunctionDeclaration(
    name="get_page",
    description=(
        "Fetch every chunk stored for one page of one of the selected "
        "documents, when you need that page's full context rather than a "
        "similarity-ranked snippet of it. document_id must be one of the "
        "documents selected for this question - use list_documents first if "
        "you're unsure of the exact id."
    ),
    parameters_json_schema={
        "type": "object",
        "properties": {
            "document_id": {
                "type": "string",
                "description": "ID of one of the documents selected for this question.",
            },
            "page": {
                "type": "integer",
                "description": "1-indexed page number to fetch.",
            },
        },
        "required": ["document_id", "page"],
    },
)

_LIST_DOCUMENTS = types.FunctionDeclaration(
    name="list_documents",
    description=(
        "List the id, name, and page count of every document selected for "
        "this question. Use this to see what's available before calling "
        "get_page, or to know how to refer to a document by name in a "
        "comparison."
    ),
    parameters_json_schema={"type": "object", "properties": {}},
)

TOOL_DECLARATIONS = [_SEARCH_DOCUMENTS, _GET_PAGE, _LIST_DOCUMENTS]
TOOLS = [types.Tool(function_declarations=TOOL_DECLARATIONS)]

_TOOL_NAMES = {declaration.name for declaration in TOOL_DECLARATIONS}


def _clamp_top_k(value: object) -> int:
    try:
        top_k = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return _DEFAULT_TOP_K
    return max(_MIN_TOP_K, min(_MAX_TOP_K, top_k))


def _as_result_dict(chunks: list[RetrievedChunk]) -> dict:
    return {
        "results": [
            {"doc_name": chunk["doc_name"], "page": chunk["page"], "text": chunk["text"]}
            for chunk in chunks
        ]
    }


def _search_documents(
    args: dict, allowed_document_ids: list[str]
) -> tuple[dict, list[RetrievedChunk]]:
    query = str(args.get("query", "")).strip()
    if not query:
        return {"error": "query must not be empty."}, []

    top_k = _clamp_top_k(args.get("top_k", _DEFAULT_TOP_K))
    query_vector = embed_query(query)
    chunk_lists = [
        query_chunks(doc_id, query_vector, top_k=top_k) for doc_id in allowed_document_ids
    ]
    chunks = merge_chunks(chunk_lists, top_k=top_k)
    return _as_result_dict(chunks), chunks


def _get_page(args: dict, allowed_document_ids: list[str]) -> tuple[dict, list[RetrievedChunk]]:
    document_id = args.get("document_id")
    if document_id not in allowed_document_ids:
        return {
            "error": (
                f"document_id {document_id!r} is not one of the documents selected "
                "for this question."
            )
        }, []

    try:
        page = int(args.get("page"))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return {"error": "page must be an integer."}, []

    chunks = query_chunks_by_page(document_id, page)
    return _as_result_dict(chunks), chunks


def _list_documents(allowed_document_ids: list[str]) -> tuple[dict, list[RetrievedChunk]]:
    documents = []
    for document_id in allowed_document_ids:
        metadata = get_doc_metadata(document_id)
        documents.append(
            {
                "document_id": document_id,
                "doc_name": metadata["doc_name"] if metadata else "Untitled document",
                "num_pages": metadata["num_pages"] if metadata else None,
            }
        )
    return {"documents": documents}, []


def dispatch_tool(
    name: str, args: dict, allowed_document_ids: list[str]
) -> tuple[dict, list[RetrievedChunk]]:
    """
    Executes one tool call. Returns (function_response, chunks_returned) -
    `chunks_returned` feeds the Analyst's citation pool; it's empty for
    list_documents and for any error result. Never raises: an unknown tool
    name or a bad/out-of-scope argument comes back as {"error": "..."} for
    the model to see and adapt to, instead of crashing the request.
    """
    args = args or {}

    if name not in _TOOL_NAMES:
        return {"error": f"Unknown tool {name!r}."}, []
    if name == "search_documents":
        return _search_documents(args, allowed_document_ids)
    if name == "get_page":
        return _get_page(args, allowed_document_ids)
    return _list_documents(allowed_document_ids)
