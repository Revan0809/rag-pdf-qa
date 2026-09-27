"""
Pinecone vector store access.

Each uploaded PDF gets its own namespace (named after its document_id) inside
a single shared index. Namespacing keeps documents isolated from each other
without needing a separate index per document.
"""
from pinecone import Pinecone, ServerlessSpec

from app.config import settings

_pc = Pinecone(api_key=settings.PINECONE_API_KEY)
_UPSERT_BATCH_SIZE = 100

# Cached index handle: list_indexes()/create_index() only need to run once
# per process, not on every request.
_index_cache = None


def get_index():
    """Returns the Pinecone index, creating it first if it doesn't exist yet."""
    global _index_cache
    if _index_cache is not None:
        return _index_cache

    if settings.PINECONE_INDEX_NAME not in _pc.list_indexes().names():
        _pc.create_index(
            name=settings.PINECONE_INDEX_NAME,
            dimension=settings.EMBEDDING_DIMENSION,
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-east-1"),
        )
    _index_cache = _pc.Index(settings.PINECONE_INDEX_NAME)
    return _index_cache


def upsert_chunks(
    document_id: str,
    doc_name: str,
    num_pages: int,
    chunks: list[dict],
    vectors: list[list[float]],
) -> None:
    """Stores each chunk's embedding + text/page/doc metadata under the document's namespace."""
    index = get_index()
    records = [
        {
            "id": f"{document_id}-{i}",
            "values": vector,
            "metadata": {
                "text": chunk["text"],
                "page": chunk["page"],
                "doc_name": doc_name,
                "num_pages": num_pages,
            },
        }
        for i, (chunk, vector) in enumerate(zip(chunks, vectors))
    ]

    for i in range(0, len(records), _UPSERT_BATCH_SIZE):
        index.upsert(vectors=records[i : i + _UPSERT_BATCH_SIZE], namespace=document_id)


def namespace_exists(document_id: str) -> bool:
    """Checks whether any vectors have been stored for this document."""
    index = get_index()
    stats = index.describe_index_stats()
    namespace = stats.namespaces.get(document_id)
    return bool(namespace and namespace.vector_count > 0)


def get_doc_metadata(document_id: str) -> dict | None:
    """
    Reads the doc_name/num_pages stamped on a document's first chunk during
    upload. Returns None if the document doesn't exist (or predates this
    metadata being added, in which case callers should fall back gracefully).
    """
    index = get_index()
    chunk_zero_id = f"{document_id}-0"
    result = index.fetch(ids=[chunk_zero_id], namespace=document_id)
    record = result.vectors.get(chunk_zero_id)
    if not record or not record.metadata:
        return None
    return {
        "doc_name": record.metadata.get("doc_name", "Untitled document"),
        "num_pages": int(record.metadata.get("num_pages", 0)),
    }


def query_chunks(document_id: str, query_vector: list[float], top_k: int) -> list[dict]:
    """Returns the top_k most similar chunks (text + page + doc_name) for a document."""
    index = get_index()
    result = index.query(
        vector=query_vector,
        top_k=top_k,
        namespace=document_id,
        include_metadata=True,
    )
    return [
        {
            "doc_id": document_id,
            "doc_name": match.metadata.get("doc_name", "Untitled document"),
            # Pinecone stores metadata numbers as floats; cast back to int
            # so it doesn't leak into the LLM prompt as e.g. "Page 1.0".
            "page": int(match.metadata["page"]),
            "text": match.metadata["text"],
            "score": match.score,
        }
        for match in result.matches
    ]


def sample_chunks(document_id: str, limit: int = 20) -> list[dict]:
    """
    Returns a spread of chunks across the whole document (ordered by page),
    for use by the Retriever on 'summary' questions and by the one-shot
    document summary endpoint, where similarity search to a single query
    vector would over-focus on one part of the document.
    """
    index = get_index()
    ids: list[str] = []
    for page in index.list(namespace=document_id, limit=limit):
        ids.extend(item.id for item in page.vectors)
        if len(ids) >= limit:
            break
    ids = ids[:limit]
    if not ids:
        return []

    result = index.fetch(ids=ids, namespace=document_id)
    chunks = [
        {
            "doc_id": document_id,
            "doc_name": record.metadata.get("doc_name", "Untitled document"),
            "page": int(record.metadata["page"]),
            "text": record.metadata["text"],
            "score": 1.0,
        }
        for record in result.vectors.values()
        if record.metadata
    ]
    return sorted(chunks, key=lambda chunk: chunk["page"])


def delete_namespace(document_id: str) -> None:
    """Deletes all vectors for a document."""
    index = get_index()
    index.delete(delete_all=True, namespace=document_id)
