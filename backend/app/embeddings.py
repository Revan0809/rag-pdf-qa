"""
Thin wrapper around the OpenAI embeddings API.

Batches requests so a large PDF (hundreds of chunks) doesn't exceed the
API's per-request input limits.
"""
from openai import OpenAI

from app.config import settings

client = OpenAI(api_key=settings.OPENAI_API_KEY)

_BATCH_SIZE = 100


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embeds a list of strings, returning one vector per input string."""
    embeddings: list[list[float]] = []
    for i in range(0, len(texts), _BATCH_SIZE):
        batch = texts[i : i + _BATCH_SIZE]
        response = client.embeddings.create(model=settings.EMBEDDING_MODEL, input=batch)
        embeddings.extend(item.embedding for item in response.data)
    return embeddings


def embed_text(text: str) -> list[float]:
    """Embeds a single string (e.g. a user's question)."""
    return embed_texts([text])[0]
