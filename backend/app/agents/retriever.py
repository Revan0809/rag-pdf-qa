"""
Retriever agent — no LLM call.

Embeds each sub-query, queries Pinecone per selected document namespace,
merges and de-duplicates the results, and keeps the top-K by score. For
'summary' questions, pulls a broader spread of chunks across pages instead of
a similarity search, since a single query vector would over-focus on
whichever part of the document happens to match it best.

On a Verifier-triggered retry, doubles top-K and re-embeds the (already
Planner-produced) sub-queries to cast a wider net — no extra LLM call either
way, so retries stay free from this agent's side of the budget.
"""
import time

from app.agents.retrieval import merge_chunks
from app.agents.state import QuorumState
from app.config import settings
from app.embeddings import embed_query
from app.vector_store import query_chunks, sample_chunks


def retrieve(state: QuorumState) -> dict:
    start = time.perf_counter()

    document_ids = state["document_ids"]
    is_retry = state.get("retry_count", 0) > 0
    top_k = settings.TOP_K * 2 if is_retry else settings.TOP_K

    if state.get("plan") == "summary":
        chunk_lists = [sample_chunks(doc_id, limit=top_k * 2) for doc_id in document_ids]
    else:
        sub_queries = state.get("sub_queries") or [state["standalone_question"]]
        chunk_lists = []
        for sub_query in sub_queries:
            query_vector = embed_query(sub_query)
            for doc_id in document_ids:
                chunk_lists.append(query_chunks(doc_id, query_vector, top_k=top_k))

    merged = merge_chunks(chunk_lists, top_k=top_k)

    duration_ms = int((time.perf_counter() - start) * 1000)
    summary = f"Retrieved {len(merged)} chunk(s) across {len(document_ids)} document(s)"
    if is_retry:
        summary += " (expanded retry)"

    return {
        "retrieved_chunks": merged,
        "trace": [
            {
                "agent": "retriever",
                "status": "completed",
                "summary": summary,
                "duration_ms": duration_ms,
            }
        ],
    }
