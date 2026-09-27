"""
One-shot document overview: title guess, key points, suggested questions.

Runs outside the agent graph — it's a single-document, single-LLM-call
operation the frontend calls right after upload, not a question to route,
retrieve for, or verify.
"""
from google.genai import types
from pydantic import BaseModel

from app.config import settings
from app.llm import call_with_backoff, client
from app.vector_store import get_doc_metadata, sample_chunks

_SYSTEM_PROMPT = (
    "You are given a spread of excerpts from a document. Produce a short "
    "overview: a guessed title (use the document's own title if the "
    "excerpts show one), exactly 5 key points, and exactly 3 suggested "
    "questions a reader might ask about it. Base everything only on the "
    "excerpts."
)


class DocumentSummary(BaseModel):
    title_guess: str
    key_points: list[str]
    suggested_questions: list[str]


def summarize_document(document_id: str) -> DocumentSummary | None:
    """Returns None if the document doesn't exist (no vectors stored for it)."""
    metadata = get_doc_metadata(document_id)
    if metadata is None:
        return None

    chunks = sample_chunks(document_id, limit=20)
    if not chunks:
        return None

    context = "\n\n".join(f"[p.{chunk['page']}]\n{chunk['text']}" for chunk in chunks)
    prompt = f"Document excerpts:\n{context}"

    response = call_with_backoff(
        lambda: client.models.generate_content(
            model=settings.CHAT_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=_SYSTEM_PROMPT,
                temperature=0.3,
                response_mime_type="application/json",
                response_schema=DocumentSummary,
            ),
        )
    )
    return response.parsed
