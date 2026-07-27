"""
PDF text extraction and chunking.

Text is extracted per-page (so we can tag every chunk with the page it came
from), then split into overlapping chunks sized by token count rather than
character count, since that's what actually matters for embedding/LLM limits.
"""
from io import BytesIO

import pdfplumber
import tiktoken
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config import settings

# cl100k_base is the encoding used by both the embedding and chat models here.
_encoding = tiktoken.get_encoding("cl100k_base")


def _tiktoken_len(text: str) -> int:
    return len(_encoding.encode(text))


class PDFExtractionError(Exception):
    """Raised when a PDF can't be opened or contains no extractable text."""


def extract_pages(pdf_bytes: bytes) -> list[tuple[int, str]]:
    """Returns a list of (page_number, page_text) for every page with text."""
    try:
        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            pages = []
            for page_number, page in enumerate(pdf.pages, start=1):
                text = page.extract_text() or ""
                if text.strip():
                    pages.append((page_number, text))
            return pages
    except Exception as exc:
        raise PDFExtractionError(f"Could not read PDF file: {exc}") from exc


def chunk_pages(pages: list[tuple[int, str]]) -> list[dict]:
    """
    Splits each page's text into ~800-token chunks with 100-token overlap.
    Each resulting chunk keeps a reference to its source page number.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.CHUNK_SIZE_TOKENS,
        chunk_overlap=settings.CHUNK_OVERLAP_TOKENS,
        length_function=_tiktoken_len,
    )

    chunks = []
    for page_number, page_text in pages:
        for chunk_text in splitter.split_text(page_text):
            chunks.append({"text": chunk_text, "page": page_number})
    return chunks


def process_pdf(pdf_bytes: bytes) -> list[dict]:
    """End-to-end: raw PDF bytes -> list of {"text", "page"} chunks."""
    pages = extract_pages(pdf_bytes)
    if not pages:
        raise PDFExtractionError(
            "No extractable text found in this PDF. It may be a scanned "
            "image without OCR, or empty."
        )
    return chunk_pages(pages)
