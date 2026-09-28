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


def make_stream_chunks(texts: list[str], function_calls: list | None = None):
    """
    Fake chunks as yielded by generate_content_stream: each has `.text` and
    (matching the real SDK, where a chunk with no function-call parts
    reports None rather than an empty list) `.function_calls`. Pass
    `function_calls` to have the *last* chunk carry them, mimicking a model
    turn that ends in a tool call.
    """
    chunks = []
    for text in texts:
        chunk = MagicMock()
        chunk.text = text
        chunk.function_calls = None
        chunks.append(chunk)
    if function_calls:
        call_chunk = MagicMock()
        call_chunk.text = None
        call_chunk.function_calls = function_calls
        chunks.append(call_chunk)
    return chunks


def make_function_call(name: str, args: dict):
    """A fake google.genai.types.FunctionCall-like object."""
    call = MagicMock()
    call.name = name
    call.args = args
    return call


@pytest.fixture
def retrieved_chunk():
    def _make(doc_id="doc-1", doc_name="Report", page=1, text="Some excerpt text.", score=0.9):
        return {"doc_id": doc_id, "doc_name": doc_name, "page": page, "text": text, "score": score}

    return _make
