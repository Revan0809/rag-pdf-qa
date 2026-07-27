"""
FastAPI entrypoint for the PDF RAG backend.

Two endpoints:
  POST /upload  -> extract, chunk, embed, and store a PDF's contents
  POST /ask     -> retrieve relevant chunks for a question and answer it

Kept as a single file since the app is small; logic that would grow the file
too much (PDF parsing, embeddings, Pinecone, prompting) lives in app/.
"""
import logging
import uuid

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.config import settings
from app.embeddings import embed_chunks, embed_query
from app.pdf_processor import PDFExtractionError, process_pdf
from app.rag import generate_answer
from app.vector_store import namespace_exists, query_chunks, upsert_chunks

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("pdf-rag")

settings.validate()

app = FastAPI(title="PDF RAG API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class UploadResponse(BaseModel):
    document_id: str
    num_chunks: int
    num_pages: int


class AskRequest(BaseModel):
    document_id: str
    question: str


class AskResponse(BaseModel):
    answer: str
    source_pages: list[int]


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/upload", response_model=UploadResponse)
async def upload_pdf(file: UploadFile = File(...)) -> UploadResponse:
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="File must be a PDF.")

    pdf_bytes = await file.read()
    if not pdf_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    try:
        chunks = process_pdf(pdf_bytes)
    except PDFExtractionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        vectors = embed_chunks([chunk["text"] for chunk in chunks])
    except Exception as exc:
        logger.exception("Gemini embedding request failed during upload")
        raise HTTPException(
            status_code=502, detail="Failed to generate embeddings for this document."
        ) from exc

    document_id = str(uuid.uuid4())

    try:
        upsert_chunks(document_id, chunks, vectors)
    except Exception as exc:
        logger.exception("Pinecone upsert failed during upload")
        raise HTTPException(
            status_code=502, detail="Failed to store document vectors."
        ) from exc

    num_pages = len({chunk["page"] for chunk in chunks})
    return UploadResponse(document_id=document_id, num_chunks=len(chunks), num_pages=num_pages)


@app.post("/ask", response_model=AskResponse)
async def ask_question(request: AskRequest) -> AskResponse:
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question must not be empty.")

    try:
        exists = namespace_exists(request.document_id)
    except Exception as exc:
        logger.exception("Pinecone lookup failed during ask")
        raise HTTPException(status_code=502, detail="Failed to look up document.") from exc

    if not exists:
        raise HTTPException(
            status_code=404,
            detail="Document not found. It may not have finished uploading, or the ID is wrong.",
        )

    try:
        question_vector = embed_query(request.question)
    except Exception as exc:
        logger.exception("Gemini embedding request failed during ask")
        raise HTTPException(
            status_code=502, detail="Failed to embed the question."
        ) from exc

    try:
        chunks = query_chunks(request.document_id, question_vector, top_k=settings.TOP_K)
    except Exception as exc:
        logger.exception("Pinecone query failed during ask")
        raise HTTPException(status_code=502, detail="Failed to retrieve relevant chunks.") from exc

    if not chunks:
        return AskResponse(
            answer="I couldn't find any relevant content in this document to answer that.",
            source_pages=[],
        )

    try:
        answer = generate_answer(request.question, chunks)
    except Exception as exc:
        logger.exception("Gemini chat completion failed during ask")
        raise HTTPException(status_code=502, detail="Failed to generate an answer.") from exc

    source_pages = sorted({chunk["page"] for chunk in chunks})
    return AskResponse(answer=answer, source_pages=source_pages)
