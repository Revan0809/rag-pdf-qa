"""
Shared chunk merge/dedupe helpers, used by both the Retriever agent
(retriever.py) and the Analyst's search_documents tool (tools.py) so there's
one definition of "what counts as the same chunk" and "keep the best score."
"""
from app.agents.state import RetrievedChunk


def dedupe_key(chunk: RetrievedChunk) -> tuple:
    return (chunk["doc_id"], chunk["page"], chunk["text"])


def merge_chunks(chunk_lists: list[list[RetrievedChunk]], top_k: int) -> list[RetrievedChunk]:
    """Merges several chunk lists, keeping each (doc, page, text)'s best score, sorted desc."""
    best_by_key: dict[tuple, RetrievedChunk] = {}
    for chunks in chunk_lists:
        for chunk in chunks:
            key = dedupe_key(chunk)
            existing = best_by_key.get(key)
            if existing is None or chunk["score"] > existing["score"]:
                best_by_key[key] = chunk
    return sorted(best_by_key.values(), key=lambda chunk: chunk["score"], reverse=True)[:top_k]
