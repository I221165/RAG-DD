# RAG Chatbot

A Retrieval-Augmented Generation chatbot. Upload PDF / DOCX / TXT files, then ask context-aware questions about them with follow-up support and source citations.

**Stack:** FastAPI · ChromaDB · Groq (Llama 3.3 70B) · MongoDB Atlas · sentence-transformers · React + Vite + Tailwind

---

## Architecture

```
┌─────────────────┐         ┌───────────────────────────────────────┐
│                 │  HTTP   │              FastAPI                  │
│  React + Vite   │ ──────► │                                       │
│  (Tailwind)     │         │  /upload  /documents  /chat (stream)  │
│                 │ ◄────── │  /history /session    /health         │
└─────────────────┘  NDJSON │                                       │
                            └──────────┬────────┬───────┬───────────┘
                                       │        │       │
                              ┌────────▼──┐  ┌──▼───┐ ┌─▼──────────┐
                              │ Document  │  │ RAG  │ │ Chat       │
                              │ Processor │  │ Pipe │ │ History    │
                              └────┬──────┘  └─┬──┬─┘ └──┬─────────┘
                                   │           │  │      │
                              ┌────▼───────────▼┐ │   ┌──▼────────┐
                              │   ChromaDB      │ │   │  MongoDB  │
                              │   (vectors)     │ │   │   Atlas   │
                              └────┬────────────┘ │   └───────────┘
                                   │              │
                              ┌────▼─────────┐ ┌──▼──────────┐
                              │ sentence-    │ │  Groq API   │
                              │ transformers │ │ (Llama 3.3) │
                              └──────────────┘ └─────────────┘
```

**Upload pipeline:** file → validate (size, MIME, extension) → LangChain loader → `RecursiveCharacterTextSplitter` (1000 / 200) → sentence-transformers embed → ChromaDB persist (metadata: `document_id`, `filename`, `chunk_index`, `uploaded_at`).

**Chat pipeline:** load last N turns from Mongo → build retrieval query from recent **user** messages + current question → embed → top-k Chroma search → compose prompt (system + history + retrieved context + question) → Groq stream → emit tokens → final `sources` event → persist both turns.

---

## Project Structure

```
rag-chatbot/
├── backend/
│   ├── app/
│   │   ├── main.py                   # FastAPI, CORS, lifespan, /health
│   │   ├── config.py                 # pydantic-settings (env-driven)
│   │   ├── routes/
│   │   │   ├── upload.py             # /upload, /documents, /documents/{id}
│   │   │   └── chat.py               # /chat (stream), /history, /session
│   │   ├── services/
│   │   │   ├── llm_service.py        # LLMProvider ABC + GroqProvider
│   │   │   ├── embeddings.py         # EmbeddingProvider ABC + ST
│   │   │   ├── vector_store.py       # VectorStore ABC + ChromaStore (DI'd embedder)
│   │   │   ├── chat_history.py       # ChatHistoryStore ABC + MongoStore
│   │   │   ├── document_processor.py # load → chunk → embed → store
│   │   │   └── rag_pipeline.py       # retrieve → prompt → (stream) generate
│   │   ├── utils/
│   │   │   ├── loaders.py            # extension → loader registry
│   │   │   ├── chunking.py           # text splitter wrapper
│   │   │   └── file_validation.py    # size / extension / magic-byte sniff
│   │   └── models/
│   │       └── schemas.py            # Pydantic API contracts
│   ├── scripts/
│   │   └── smoke_test_phase4.py      # standalone embedder + Chroma roundtrip
│   ├── uploads/                      # (gitignored) raw uploaded files
│   ├── chroma_db/                    # (gitignored) persisted vectors
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
│
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── main.jsx
│   │   ├── index.css                 # tailwind v4 entry
│   │   ├── services/
│   │   │   └── api.js                # fetch wrappers + NDJSON stream parser
│   │   └── components/
│   │       ├── Sidebar.jsx
│   │       ├── UploadBox.jsx
│   │       ├── ChatBox.jsx
│   │       └── MessageBubble.jsx
│   ├── nginx.conf                    # used by the production frontend container
│   ├── vite.config.js                # dev proxy → backend on :8000
│   ├── package.json
│   └── Dockerfile
│
├── docker-compose.yml
└── README.md
```

---

## Quickstart

### Prerequisites
- Python **3.10 – 3.12** (3.13 also works locally, but Docker uses 3.11 for wheel safety)
- Node **18+**
- A free [Groq API key](https://console.groq.com)
- A free [MongoDB Atlas cluster](https://www.mongodb.com/cloud/atlas) (M0 tier is fine). Allowlist `0.0.0.0/0` for local dev.

### Option A — Local dev

```bash
# 1. Backend
cd backend
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
# Edit .env: set GROQ_API_KEY and MONGODB_URI

uvicorn app.main:app --reload --port 8000
```

In a second terminal:

```bash
cd frontend
npm install
npm run dev
# opens http://localhost:5173
```

### Option B — Docker

```bash
# 1. Fill in backend/.env first (as above)
cp backend/.env.example backend/.env
# Edit backend/.env with your secrets

# 2. Build + run
docker compose up --build
```

- Backend: http://localhost:8000 (Swagger at `/docs`)
- Frontend: http://localhost:5173

Stopping with `docker compose down` preserves Chroma + uploads via volume mounts.

---

## Configuration

All settings live in `backend/.env`. Defaults shown.

| Variable                | Default                                           | What it does                                          |
|-------------------------|---------------------------------------------------|-------------------------------------------------------|
| `GROQ_API_KEY`          | _(required for chat)_                             | Groq API credentials                                  |
| `MONGODB_URI`           | _(required for history)_                          | Mongo Atlas connection string                         |
| `MONGODB_DB_NAME`       | `rag_chatbot`                                     | Mongo database name                                   |
| `LLM_PROVIDER`          | `groq`                                            | Selector for `get_llm()` factory                      |
| `EMBEDDING_PROVIDER`    | `sentence_transformers`                           | Selector for `get_embedder()` factory                 |
| `VECTOR_STORE`          | `chroma`                                          | Selector for `get_vector_store()` factory             |
| `CHAT_HISTORY_STORE`    | `mongodb`                                         | Selector for `get_history_store()` factory            |
| `MODEL_NAME`            | `llama-3.3-70b-versatile`                         | Groq model id                                         |
| `EMBEDDING_MODEL`       | `sentence-transformers/all-MiniLM-L6-v2`          | SBERT model                                           |
| `CHUNK_SIZE`            | `1000`                                            | Chars per chunk                                       |
| `CHUNK_OVERLAP`         | `200`                                             | Overlap between chunks                                |
| `TOP_K`                 | `4`                                               | Chunks retrieved per query                            |
| `HISTORY_TURNS`         | `6`                                               | Messages kept in the LLM prompt                       |
| `TEMPERATURE`           | `0.2`                                             | Generation temperature                                |
| `MAX_TOKENS`            | `1024`                                            | Per-response cap                                      |
| `CHROMA_PATH`           | `./chroma_db`                                     | Where Chroma persists                                 |
| `UPLOAD_DIR`            | `./uploads`                                       | Where raw files are stored                            |
| `CHROMA_COLLECTION`     | `documents`                                       | Collection name                                       |
| `MAX_UPLOAD_MB`         | `20`                                              | Per-file size cap                                     |
| `ALLOWED_ORIGINS`       | `["http://localhost:5173", ...]`                  | CORS allowlist (JSON array)                           |

---

## API Reference

| Method | Path                       | Body / Params                        | Response                                       |
|--------|----------------------------|--------------------------------------|------------------------------------------------|
| POST   | `/upload`                  | multipart `file`                     | `{document_id, filename, num_chunks, uploaded_at}` |
| GET    | `/documents`               | —                                    | `[DocumentInfo, ...]`                          |
| DELETE | `/documents/{document_id}` | —                                    | `{deleted, document_id}`                       |
| POST   | `/chat`                    | `{message, session_id?}`             | `application/x-ndjson` stream (see below)      |
| GET    | `/history/{session_id}`    | —                                    | `{session_id, messages: [...]}`                |
| DELETE | `/session/{session_id}`    | —                                    | `{cleared, session_id}`                        |
| GET    | `/health`                  | —                                    | `{status, mongodb, vector_store, llm}`         |

Full schemas are at `http://localhost:8000/docs` (Swagger).

### `/chat` streaming protocol

Newline-delimited JSON (NDJSON). One object per line:

```
{"type": "session", "content": "uuid-..."}     # only on a brand-new session
{"type": "token",   "content": "Penguins "}    # many
{"type": "token",   "content": "are flight…"}
{"type": "sources", "content": [{"filename": "...", "chunk_index": 3, "snippet": "..."}]}
{"type": "done",    "content": ""}
{"type": "error",   "content": "..."}          # replaces remaining events on failure
```

---

## How follow-up retrieval works

A naive RAG embeds only the current question. That breaks on follow-ups like *"tell me more about that one"* — `that` has no semantic content, so retrieval misses.

This implementation concatenates the **recent user messages** with the current question to build the embedding query. Assistant text is **excluded** to avoid letting the model's prior hallucinations bias future retrieval.

```python
# rag_pipeline.py
recent_user = " ".join(m.content for m in history[-N:] if m.role == "user")
retrieval_query = f"{recent_user}\n{message}" if recent_user else message
```

History is _also_ passed to the LLM directly (as message turns), so the model can resolve pronouns and references when generating the answer.

The next step up (not implemented in v1) would be a small LLM call to rewrite the follow-up into a fully standalone query before embedding. That is a ~20-line addition in `_build_retrieval_query`.

---

## Architecture Decisions

**Why ChromaDB (vs Pinecone / FAISS / Qdrant)?**
Persistent and local out of the box, simple Python API, ships with metadata filtering. Pinecone adds a network dependency and account setup for a demo-scale project; FAISS needs more boilerplate for persistence and metadata.

**Why provider ABC + factory pattern?**
The spec calls out keeping the implementation "as dynamic and flexible as possible." Each of `LLMProvider`, `EmbeddingProvider`, `VectorStore`, `ChatHistoryStore` is an ABC with one concrete implementation today, selected via an env var. Adding e.g. `OpenAIProvider` is one new file + one branch in the factory — no route or pipeline changes.

**Why dependency-inject the embedder into the vector store (vs Chroma's `embedding_function`)?**
Coupling embedding to Chroma's collection config means swapping vector stores requires re-wiring the embedder in a new place. With DI, `EmbeddingProvider` stays the single source of truth — swap stores and the embedder comes along.

**Why MongoDB Atlas for chat history?**
Persists across restarts without local infra, supports the embedded-message schema cleanly (one document per session, `$push` for new messages), and adds zero cost on the free tier. Trade-off: introduces a cloud dependency at demo time, mitigated by allowlisting `0.0.0.0/0`. At demo scale this is fine; for production, messages would move to a separate collection to avoid MongoDB's 16 MB document limit on very long sessions and to enable efficient per-message queries.

**Why a loader registry instead of switch/if statements?**
Adding a new file type (`.md`, `.html`, `.csv`, `.pptx`) is one new function + one line in `LOADERS`. No conditionals to update.

**Why HTTP streaming with NDJSON (vs SSE)?**
NDJSON is one JSON object per line — trivially parsable on the client without an `EventSource` abstraction or SSE framing. The `/chat` route uses `StreamingResponse` so tokens arrive incrementally; the React client decodes them as they stream in.

**Why concatenate user-only history for retrieval (vs full history or LLM reformulation)?**
- Full history would pull assistant text — and any prior hallucinations — into the embedding query.
- LLM reformulation works better but adds one round-trip per turn (~300ms + cost).
- User-only concatenation is free and handles ~80% of follow-ups (the realistic demo cases).

---

## Known Limitations

- **No auth or multi-tenancy.** All documents live in one shared collection. Adding per-user isolation would require a `user_id` metadata field on every chunk + auth gating on every route.
- **No OCR for scanned PDFs.** `pdfplumber` only extracts embedded text. Scanned-image PDFs surface as "no extractable text" with a clear 400 error.
- **Retrieval is semantic similarity only.** No BM25, no hybrid search, no reranking layer. Fine for clean prose documents; degrades on rare keywords or exact-string queries.
- **In-prompt history is bounded.** Default `HISTORY_TURNS=6`. Long conversations drop early turns from the LLM context (though the full history is stored in MongoDB).
- **Chroma persistence is tied to the deployment volume.** On Railway, data survives redeploys only if a persistent volume is mounted at `/app/chroma_db`. Without it, every redeploy wipes embeddings.
- **MongoDB sessions use an embedded messages array.** Good for demo scale — MongoDB documents support up to 16 MB. For production workloads with very long conversations, messages would move to a separate collection to avoid unbounded document growth and improve query performance.

---

## Future Improvements

- LLM-based query reformulation for harder follow-ups
- Re-ranking (cross-encoder) on retrieved chunks
- Hybrid search (BM25 + vector fusion)
- Per-document filter in the UI (chat only against selected docs)
- Authentication + per-user document collections
- Streaming-aware UI polish (typing indicators, partial-markdown render)
- Evaluation harness (RAGAS or custom)

---

## License

MIT
