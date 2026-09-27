# Changelog

## v2.0.0 — Quorum

Renamed from "PDF Q&A" to **Quorum** and rebuilt around a multi-agent
backend and a multi-document frontend.

### Backend

- Replaced the single Gemini call in `/ask` with a LangGraph agent graph:
  Planner (classify + rewrite + sub-queries) → Retriever (merge/dedupe
  across sub-queries and documents) → Analyst (cited, streamed answer) →
  Verifier (confidence score, one retry back to the Retriever on low
  confidence). Capped at 4 LLM calls per question to respect Gemini's
  free-tier rate limits.
- Added `POST /ask/stream` (SSE: trace events, streamed answer tokens, a
  reset event on a mid-stream retry, final answer + citations).
- Added `DELETE /documents/{id}` and `POST /documents/{id}/summary`.
- `/upload` now stamps `doc_name` and `num_pages` onto chunk metadata and
  returns `doc_name`.
- Fixed: `render.yaml` declared `OPENAI_API_KEY`; the app only ever read
  `GEMINI_API_KEY`.
- Fixed: `.env.example` referenced `gemini-2.0-flash`; the app uses
  `gemini-flash-latest`.
- Fixed: `get_index()` re-listed indexes and `namespace_exists()` re-ran
  `describe_index_stats()` on every request; the index handle is now cached
  per process.
- Migrated `pinecone-client` → `pinecone` (the current package name).
- Added a shared retry-with-backoff wrapper for Gemini 429s, used by both
  embeddings and every agent's LLM call.
- Added a pytest suite (Planner classification/fallback, Retriever
  merge/dedupe/summary-mode, the Verifier's single-retry cap, `/ask/stream`
  event ordering) with Gemini and Pinecone mocked.

### Frontend

- Replaced the single-PDF upload+chat page with a three-panel workspace
  (Library / Chat / Viewer, collapsing to tabs on mobile).
- Documents are tracked client-side in localStorage (the backend stays
  stateless); questions can target multiple selected documents at once.
- Answers stream in with a live, animated agent trace timeline, clickable
  citation chips, and a confidence badge.
- Added a PDF viewer (react-pdf) that jumps to a citation's page. Known
  limitation: since the backend never stores original PDF bytes, the
  viewer can only render documents still in the browser's memory from the
  current session's upload.
- Added light/dark theming (CSS variables + toggle, set pre-hydration to
  avoid a flash), a Render cold-start banner, and toast notifications for
  upload/ask failures.
- Renamed the FastAPI app title, Next.js metadata/favicon, and
  `package.json` name to Quorum; renamed the Render service to
  `quorum-backend`.

### Breaking changes

- `/ask`'s request/response shape changed: it now takes `document_ids`
  (plural) + `history`, and returns `final_answer`/`citations`/`confidence`/
  `trace` instead of `answer`/`source_pages`. There was no versioned public
  API to preserve, so this ships as a straight replacement rather than a
  new endpoint.
- The Pinecone index name default changed from `pdf-rag-index` to
  `quorum-index`; deployments that already set `PINECONE_INDEX_NAME`
  explicitly are unaffected.

## v1.0.0

Initial release: single-PDF upload, single Gemini call per question,
Pinecone per-document namespaces, Next.js + FastAPI on Vercel + Render.
