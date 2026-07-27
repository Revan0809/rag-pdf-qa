"""
The RAG "generation" half: turn retrieved chunks + a question into a grounded
answer, using the OpenAI chat completions API.
"""
from openai import OpenAI

from app.config import settings

client = OpenAI(api_key=settings.OPENAI_API_KEY)

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
    """Calls gpt-4o-mini to produce an answer grounded in the given chunks."""
    prompt = _build_user_prompt(question, chunks)
    response = client.chat.completions.create(
        model=settings.CHAT_MODEL,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )
    return response.choices[0].message.content
