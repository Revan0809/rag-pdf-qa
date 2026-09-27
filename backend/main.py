"""
FastAPI entrypoint for the Quorum multi-agent PDF research backend.

Endpoints:
  POST /upload                          -> extract, chunk, embed, and store a PDF
  POST /ask                             -> run the agent graph, return the final answer
  POST /ask/stream                      -> run the agent graph, streaming trace + answer via SSE
  DELETE /documents/{document_id}       -> delete a document's vectors
  POST /documents/{document_id}/summary -> one-shot overview of a document
  GET  /health

Kept as a single file since the app is small; logic that would grow the file
too much (PDF parsing, embeddings, Pinecone, the agent graph) lives in app/.
"""
import json
import logging
import os
import uuid
from typing import Literal

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from app.agents.graph import quorum_graph
from app.agents.state import QuorumState
from app.config import settings
from app.embeddings import embed_chunks
from app.pdf_processor import PDFExtractionError, process_pdf
from app.sse import run_graph_as_sse
from app.summary import summarize_document
from app.vector_store import delete_namespace, namespace_exists, upsert_chunks

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("pdf-rag")

settings.validate()

app = FastAPI(title="Quorum API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class UploadResponse(BaseModel):
    document_id: str
    doc_name: str
    num_chunks: int
    num_pages: int


class ChatTurnModel(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class AskRequest(BaseModel):
    document_ids: list[str]
    question: str
    history: list[ChatTurnModel] = []


class CitationModel(BaseModel):
    doc_id: str
    doc_name: str
    page: int
    snippet: str


class TraceEventModel(BaseModel):
    agent: str
    status: str
    summary: str
    duration_ms: int


class AskResponse(BaseModel):
    final_answer: str
    citations: list[CitationModel]
    confidence: str
    trace: list[TraceEventModel]


class SummaryResponse(BaseModel):
    title_guess: str
    key_points: list[str]
    suggested_questions: list[str]


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
    doc_name = os.path.splitext(file.filename or "")[0] or "Untitled document"
    num_pages = len({chunk["page"] for chunk in chunks})

    try:
        upsert_chunks(document_id, doc_name, num_pages, chunks, vectors)
    except Exception as exc:
        logger.exception("Pinecone upsert failed during upload")
        raise HTTPException(
            status_code=502, detail="Failed to store document vectors."
        ) from exc

    return UploadResponse(
        document_id=document_id, doc_name=doc_name, num_chunks=len(chunks), num_pages=num_pages
    )


def _validate_documents(document_ids: list[str]) -> None:
    if not document_ids:
        raise HTTPException(status_code=400, detail="At least one document must be selected.")

    for document_id in document_ids:
        try:
            exists = namespace_exists(document_id)
        except Exception as exc:
            logger.exception("Pinecone lookup failed while validating document %s", document_id)
            raise HTTPException(status_code=502, detail="Failed to look up document.") from exc
        if not exists:
            raise HTTPException(
                status_code=404,
                detail=f"Document {document_id} not found. It may not have finished "
                "uploading, or the ID is wrong.",
            )


def _build_initial_state(request: AskRequest) -> QuorumState:
    return {
        "question": request.question,
        # Keep only the last few turns: enough for follow-up resolution
        # without growing the Planner's prompt unboundedly.
        "chat_history": [turn.model_dump() for turn in request.history[-6:]],
        "document_ids": request.document_ids,
        "retry_count": 0,
    }


@app.post("/ask", response_model=AskResponse)
async def ask_question(request: AskRequest) -> AskResponse:
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question must not be empty.")
    _validate_documents(request.document_ids)

    try:
        result = quorum_graph.invoke(_build_initial_state(request))
    except Exception as exc:
        logger.exception("Quorum graph run failed during ask")
        raise HTTPException(status_code=502, detail="Failed to generate an answer.") from exc

    return AskResponse(
        final_answer=result.get("final_answer", ""),
        citations=result.get("citations", []),
        confidence=result.get("confidence", "medium"),
        trace=result.get("trace", []),
    )


@app.post("/ask/stream")
async def ask_question_stream(request: AskRequest) -> EventSourceResponse:
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question must not be empty.")
    _validate_documents(request.document_ids)

    def event_stream():
        try:
            yield from run_graph_as_sse(_build_initial_state(request))
        except Exception:
            logger.exception("Quorum graph run failed during ask/stream")
            yield {
                "event": "error",
                "data": json.dumps({"detail": "Failed to generate an answer."}),
            }

    # A plain (sync) generator: sse-starlette runs it in a thread pool, so
    # the blocking Gemini/Pinecone calls inside the graph don't stall the
    # event loop for other requests.
    return EventSourceResponse(event_stream())


@app.delete("/documents/{document_id}")
async def delete_document(document_id: str) -> dict:
    try:
        delete_namespace(document_id)
    except Exception as exc:
        logger.exception("Pinecone delete failed for document %s", document_id)
        raise HTTPException(status_code=502, detail="Failed to delete document.") from exc
    return {"status": "deleted", "document_id": document_id}


@app.post("/documents/{document_id}/summary", response_model=SummaryResponse)
async def get_document_summary(document_id: str) -> SummaryResponse:
    try:
        summary = summarize_document(document_id)
    except Exception as exc:
        logger.exception("Failed to summarize document %s", document_id)
        raise HTTPException(status_code=502, detail="Failed to summarize document.") from exc

    if summary is None:
        raise HTTPException(status_code=404, detail="Document not found.")

    return SummaryResponse(
        title_guess=summary.title_guess,
        key_points=summary.key_points,
        suggested_questions=summary.suggested_questions,
    )
