# PDF Q&A (RAG)

Upload a PDF, ask questions about it in a chat interface, and get answers
grounded in the document with the source page numbers cited.

## Architecture

```
frontend/  Next.js (Vercel)      -->  backend/  FastAPI (Render)  -->  Pinecone (vector storage)
                                                    |
                                                    v
                                              Gemini (embeddings + chat)
```

| Layer            | Tech                    | Deployed to |
|------------------|-------------------------|-------------|
| Frontend         | Next.js + Tailwind CSS  | Vercel      |
| Backend / API    | FastAPI                 | Render      |
| Vector storage   | Pinecone                | Pinecone cloud |
| Embeddings / LLM | Gemini (free tier)      | called from backend only |

### Why split frontend and backend across two platforms?

Vercel is built around serverless functions: each request runs in a fresh,
stateless invocation with no long-lived process and no local disk to persist
data between calls. A RAG pipeline needs the opposite — the vectors created
for a document during `/upload` must still exist when `/ask` is called
later, potentially by a different serverless instance, potentially minutes
or hours later. Running the pipeline as Vercel functions would mean either
losing that state on every cold start or bolting on an external store just
to survive Vercel's own execution model.

Render, by contrast, runs the FastAPI app as a normal long-lived process, so
it's the natural home for a backend with real compute (PDF parsing, calling
Gemini, talking to Pinecone). Persistent state across requests still doesn't
live in the backend process itself, though — it lives in **Pinecone**, which
is what actually makes documents queryable across cold starts, deploys, and
scaled-out instances. Splitting this way keeps each piece doing what it's
good at: Vercel for fast static/SSR delivery of the UI, Render for a
persistent API process, Pinecone for durable vector storage.

## Project structure

```
RAG_pdf/
├── backend/            FastAPI app
│   ├── app/
│   │   ├── config.py           env vars / settings
│   │   ├── pdf_processor.py    text extraction + chunking
│   │   ├── embeddings.py       Gemini embeddings wrapper
│   │   ├── vector_store.py     Pinecone upsert/query
│   │   └── rag.py              prompt construction + Gemini chat call
│   ├── main.py                 FastAPI routes (/upload, /ask, /health)
│   ├── requirements.txt
│   └── .env.example
├── frontend/            Next.js app
│   ├── app/                    pages (App Router)
│   ├── components/              PdfUploader, ChatPanel
│   ├── lib/api.ts               fetch/XHR wrappers around the backend
│   ├── types/index.ts
│   └── .env.example
├── render.yaml          Render Blueprint for the backend
└── README.md
```

## How it works

**Upload (`POST /upload`)**
1. `pdfplumber` extracts text per page.
2. `RecursiveCharacterTextSplitter` (LangChain) splits each page's text into
   ~800-token chunks with 100-token overlap, tokenized with `tiktoken`. Each
   chunk keeps a reference to the page it came from.
3. Each chunk is embedded with Gemini's `gemini-embedding-001`.
4. Vectors are upserted into a Pinecone index, under a namespace equal to a
   freshly generated `document_id`. Namespacing keeps documents isolated
   inside a single shared index.
5. The `document_id` is returned to the frontend, which uses it for all
   subsequent questions about that document.

**Ask (`POST /ask`)**
1. The question is embedded with the same Gemini embedding model.
2. Pinecone is queried for the top 5 most similar chunks, scoped to the
   document's namespace.
3. The retrieved chunks (with page numbers) are inserted into a prompt as
   context.
4. `gemini-flash-latest` generates an answer grounded in that context.
5. The answer is returned along with the sorted, de-duplicated list of page
   numbers the answer was drawn from.

The Gemini API key never reaches the browser — all embedding and chat calls
happen inside the FastAPI backend.

## Prerequisites

- Python 3.11+
- Node.js 18.18+
- A [Gemini API key](https://aistudio.google.com/apikey) (free, no credit card required)
- A [Pinecone](https://app.pinecone.io) account and API key

You do **not** need to manually create the Pinecone index — the backend
creates it automatically on first use (1536 dimensions, cosine metric,
matching `gemini-embedding-001`) if it doesn't already exist. You only
need to choose a name for it via `PINECONE_INDEX_NAME`.

## Running locally

### Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS/Linux

pip install -r requirements.txt
copy .env.example .env         # then fill in GEMINI_API_KEY and PINECONE_API_KEY
uvicorn main:app --reload --port 8000
```

The API is now running at `http://localhost:8000`. Check `http://localhost:8000/health`.

### Frontend

```bash
cd frontend
npm install
copy .env.example .env.local   # NEXT_PUBLIC_API_URL=http://localhost:8000
npm run dev
```

Open `http://localhost:3000`.

## Deploying

### Backend -> Render

1. Push this repo to GitHub.
2. In the Render dashboard: **New -> Blueprint**, point it at the repo. It
   will pick up [`render.yaml`](render.yaml), which configures a Python web
   service rooted at `backend/` with:
   - Build: `pip install -r requirements.txt`
   - Start: `uvicorn main:app --host 0.0.0.0 --port $PORT`
3. When prompted, set the environment variables (marked `sync: false` in
   `render.yaml` so Render asks for them rather than committing them):
   - `GEMINI_API_KEY`
   - `PINECONE_API_KEY`
   - `PINECONE_INDEX_NAME`
   - `ALLOWED_ORIGINS` — set this to your Vercel URL once you have it (e.g.
     `https://your-app.vercel.app`), comma-separated with `http://localhost:3000`
     if you still want local frontend dev to work against the deployed backend.
4. Deploy. Note the resulting service URL (e.g. `https://pdf-rag-backend.onrender.com`).

If you'd rather configure it manually instead of using the Blueprint: create
a new Web Service, set root directory to `backend`, runtime Python 3.11,
build command `pip install -r requirements.txt`, start command
`uvicorn main:app --host 0.0.0.0 --port $PORT`, and add the same env vars.

### Frontend -> Vercel

1. In the Vercel dashboard: **New Project**, import the repo, and set the
   **root directory** to `frontend`.
2. Vercel auto-detects Next.js (`frontend/vercel.json` just pins the
   build/dev/install commands explicitly).
3. Add an environment variable:
   - `NEXT_PUBLIC_API_URL` = your Render backend URL (e.g.
     `https://pdf-rag-backend.onrender.com`)
4. Deploy. Once you have the resulting Vercel URL, go back to Render and add
   it to `ALLOWED_ORIGINS` so CORS allows requests from it.

## Notes on the free tiers

- Render's free web services spin down when idle and take ~30-60s to wake
  on the next request — the first `/upload` or `/ask` after a period of
  inactivity will be slow.
- Pinecone's free tier is fine for this project's scale; a single shared
  index with per-document namespaces avoids needing one index per PDF.
