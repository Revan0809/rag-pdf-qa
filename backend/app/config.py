"""
Centralized app configuration, loaded from environment variables.

Keeping all env var access in one place makes it obvious what the service
needs to run, and means the rest of the codebase never touches os.environ
directly.
"""
import os

from dotenv import load_dotenv

# Loads variables from a local .env file when running outside of Render.
# In production, Render injects env vars directly, so this is a no-op there.
load_dotenv()


class Settings:
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    PINECONE_API_KEY: str = os.getenv("PINECONE_API_KEY", "")
    PINECONE_INDEX_NAME: str = os.getenv("PINECONE_INDEX_NAME", "pdf-rag-index")

    # Comma-separated list of origins allowed to call this API (the deployed
    # Vercel URL, plus localhost for development).
    ALLOWED_ORIGINS: list[str] = [
        origin.strip()
        for origin in os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
        if origin.strip()
    ]

    # Gemini's embedding model supports variable output size (Matryoshka
    # representation learning); pinned to 1536 to match the Pinecone index.
    EMBEDDING_MODEL: str = "gemini-embedding-001"
    EMBEDDING_DIMENSION: int = 1536
    CHAT_MODEL: str = "gemini-flash-latest"

    CHUNK_SIZE_TOKENS: int = 800
    CHUNK_OVERLAP_TOKENS: int = 100
    TOP_K: int = 5

    def validate(self) -> None:
        """Fail fast on startup if required secrets are missing."""
        missing = [
            name
            for name, value in [
                ("GEMINI_API_KEY", self.GEMINI_API_KEY),
                ("PINECONE_API_KEY", self.PINECONE_API_KEY),
            ]
            if not value
        ]
        if missing:
            raise RuntimeError(
                f"Missing required environment variable(s): {', '.join(missing)}. "
                "Copy .env.example to .env and fill them in."
            )


settings = Settings()
