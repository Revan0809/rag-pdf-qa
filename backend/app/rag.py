"""
The RAG "generation" half: turn retrieved chunks + a question into a grounded
answer, using the Gemini chat API (Google's free-tier-eligible alternative
to OpenAI chat completions, used here to keep this project runnable without
a paid API key).
"""
from google import genai
from google.genai import types

from app.config import settings

client = genai.Client(api_key=settings.GEMINI_API_KEY)

_SYSTEM_PROMPT = (
    "You are a helpful assistant that answers questions using ONLY the "
    "provided document excerpts. If the excerpts don't contain enough "
    "information to answer, say so clearly instead of guessing. Keep "
    "answers concise and reference specific facts from the excerpts."
)


def _build_user_prompt(question: str, chunks: list[dict]) -> str:
    context = "\n\n".join(f"[Page {chunk['page']}]\n{chunk['text']}" for chunk in chunks)
    return (
        f"Document excerpts:\n{context}\n\n"
        f"Question: {question}\n\n"
        "Answer using only the excerpts above."
    )


def generate_answer(question: str, chunks: list[dict]) -> str:
    """Calls Gemini to produce an answer grounded in the given chunks."""
    prompt = _build_user_prompt(question, chunks)
    response = client.models.generate_content(
        model=settings.CHAT_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=_SYSTEM_PROMPT,
            temperature=0.2,
        ),
    )
    return response.text
