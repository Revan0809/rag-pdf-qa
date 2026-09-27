"""
Thin wrapper around the Gemini embeddings API (Google's free-tier-eligible
alternative to OpenAI embeddings, used here to keep this project runnable
without a paid API key).

Batches requests so a large PDF (hundreds of chunks) doesn't exceed the
API's per-request input limits, and passes a task_type hint so document
chunks and search queries are embedded optimally for retrieval.
"""
from google.genai import types

from app.config import settings
from app.llm import call_with_backoff, client

_BATCH_SIZE = 100


def _embed(texts: list[str], task_type: str) -> list[list[float]]:
    embeddings: list[list[float]] = []
    for i in range(0, len(texts), _BATCH_SIZE):
        batch = texts[i : i + _BATCH_SIZE]
        response = call_with_backoff(
            lambda batch=batch: client.models.embed_content(
                model=settings.EMBEDDING_MODEL,
                contents=batch,
                config=types.EmbedContentConfig(
                    task_type=task_type,
                    output_dimensionality=settings.EMBEDDING_DIMENSION,
                ),
            )
        )
        embeddings.extend(item.values for item in response.embeddings)
    return embeddings


def embed_chunks(texts: list[str]) -> list[list[float]]:
    """Embeds document chunks for storage."""
    return _embed(texts, task_type="RETRIEVAL_DOCUMENT")


def embed_query(text: str) -> list[float]:
    """Embeds a user's question for similarity search."""
    return _embed([text], task_type="RETRIEVAL_QUERY")[0]
