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


def get_index():
    """Returns the Pinecone index, creating it first if it doesn't exist yet."""
    existing_names = [idx["name"] for idx in _pc.list_indexes()]
    if settings.PINECONE_INDEX_NAME not in existing_names:
        _pc.create_index(
            name=settings.PINECONE_INDEX_NAME,
            dimension=settings.EMBEDDING_DIMENSION,
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-east-1"),
        )
    return _pc.Index(settings.PINECONE_INDEX_NAME)


def upsert_chunks(document_id: str, chunks: list[dict], vectors: list[list[float]]) -> None:
    """Stores each chunk's embedding + text/page metadata under the document's namespace."""
    index = get_index()
    records = [
        {
            "id": f"{document_id}-{i}",
            "values": vector,
            "metadata": {"text": chunk["text"], "page": chunk["page"]},
        }
        for i, (chunk, vector) in enumerate(zip(chunks, vectors))
    ]

    for i in range(0, len(records), _UPSERT_BATCH_SIZE):
        index.upsert(vectors=records[i : i + _UPSERT_BATCH_SIZE], namespace=document_id)


def namespace_exists(document_id: str) -> bool:
    """Checks whether any vectors have been stored for this document."""
    index = get_index()
    stats = index.describe_index_stats()
    namespace_stats = stats.get("namespaces", {}).get(document_id)
    return bool(namespace_stats and namespace_stats.get("vector_count", 0) > 0)


def query_chunks(document_id: str, query_vector: list[float], top_k: int) -> list[dict]:
    """Returns the top_k most similar chunks (text + page) for a document."""
    index = get_index()
    result = index.query(
        vector=query_vector,
        top_k=top_k,
        namespace=document_id,
        include_metadata=True,
    )
    return [
        {
            # Pinecone stores metadata numbers as floats; cast back to int
            # so it doesn't leak into the LLM prompt as e.g. "Page 1.0".
            "text": match["metadata"]["text"],
            "page": int(match["metadata"]["page"]),
            "score": match["score"],
        }
        for match in result["matches"]
    ]
