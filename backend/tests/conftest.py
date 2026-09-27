"""
Shared fixtures: env vars so app.config.settings.validate() passes, plus
helpers for building fake Gemini `generate_content` responses that carry a
`.parsed` pydantic object the way structured-output calls do.
"""
import os
from unittest.mock import MagicMock

import pytest

os.environ.setdefault("GEMINI_API_KEY", "test-key")
os.environ.setdefault("PINECONE_API_KEY", "test-key")


def make_parsed_response(parsed_model):
    """A fake google.genai GenerateContentResponse with `.parsed` set."""
    response = MagicMock()
    response.parsed = parsed_model
    return response


def make_stream_chunks(texts: list[str]):
    """Fake chunks as yielded by generate_content_stream: each has `.text`."""
    chunks = []
    for text in texts:
        chunk = MagicMock()
        chunk.text = text
        chunks.append(chunk)
    return chunks


@pytest.fixture
def retrieved_chunk():
    def _make(doc_id="doc-1", doc_name="Report", page=1, text="Some excerpt text.", score=0.9):
        return {"doc_id": doc_id, "doc_name": doc_name, "page": page, "text": text, "score": score}

    return _make
