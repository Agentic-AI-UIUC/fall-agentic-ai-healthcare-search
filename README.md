# Agentic AI Healthcare Search

An open research prototype for a Retrieval-Augmented Generation (RAG) pipeline focused on medical text (MSD, manuals, and scraped content). This repo holds ingestion, vector storage, retrieval, and LLM interaction code for building an explainable medical assistant.

## Quick Summary
- Ingest medical documents, chunk text, and create embeddings.
- Store embeddings in a vector DB (Qdrant).
- Perform semantic retrieval, build context, and query an LLM to produce grounded answers with sources.

## Top-level layout
- `archive/`: previous code kept for reference (legacy, not active).
- `data_collection/`: scrapers and preprocessing scripts for fetching and cleaning raw sources.
- `db/`: database and ingestion utilities (vector DB setup and ingestion scripts).
- `pipeline/`: the RAG pipeline: retrieval, generator (LLM interface), and orchestration.
- `src/`: experimental scripts, examples, and agent definitions used during development.

See the repository root to explore files and modules.

## Techstack (current / planned)
- RAG: LangChain
- Vector DB: Qdrant (local via Docker for development; can swap to Chroma/others)
- Embeddings: sentence-transformers (for indexing and query embeddings using PubMedBERT and BGE Large Hybrid)
- Model hosting: TBD (local Ollama LLM or hosted providers; Groq, etc. considered)

## RAG Pipeline (high-level)

1) Ingestion (one-time)
	- Collect PDFs / articles and split into chunks (300–500 words recommended).
	- Embed chunks with a sentence-transformer and store vectors in the vector DB.
	- Result: a searchable knowledge base.

	Example (LangChain text splitter):

	```py
	from langchain.text_splitter import RecursiveCharacterTextSplitter
	splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
	chunks = splitter.split_documents(docs)
	```

2) User query
	- Embed the user query with the same embedding model.
	- Run a similarity search over the vector DB and retrieve top-k chunks (3–5).
	- Build a prompt combining the retrieved context with the user's question.
	- Send prompt to the LLM and return the response plus source chunks for traceability.

3) Return
	- Provide the user a simplified, sourced answer and point to source documents for verification.

## Where to work (modules of interest)
- Ingestion & DB: `db/ingestion.py` — process `data_collection/processed` outputs and store vectors.
- RAG pipeline: `pipeline/main.py` — orchestrates retrieval → prompt building → LLM call.
- LLM interface: `pipeline/generator.py` — contains prompt templates and code that calls the model.
- Retriever: `pipeline/retriever.py` — handles vector DB queries and result ranking.

## 🚀 Server Setup & Automated Ingestion
### Docker Compose

Run the web app and Qdrant together:

```sh
docker compose up --build
```

Then open http://localhost:5001.

If you want a different host port, set `APP_PORT`:

```sh
APP_PORT=5050 docker compose up --build
```

If your Qdrant volume is empty, ingest the medical chunks after the services are up:

```sh
docker compose exec app uv run --frozen python db/ingestion.py
```

For LLM-backed answers, create a local `.env` file before starting compose:

```sh
GROQ_API_KEY=gsk_...
```

Compose stores Flask app data in the `app_data` volume, Qdrant vectors in the
`qdrant_storage` volume, and downloaded embedding models in the `model_cache`
volume.

### Manual Qdrant

1. Start Qdrant with Docker Compose or the official image in the background:

```sh
docker run -d -p 6333:6333 -p 6334:6334 -v qdrant_storage:/qdrant/storage qdrant/qdrant
```

2. Generate embeddings and ingest chunks automatically into the vector database using our hybrid models (`pritamdeka/S-PubMedBert-MS-MARCO` + `BAAI/bge-large-en-v1.5`):

```sh
uv run python db/ingestion.py
```
This script will parse all processed texts, embed them, upload them natively to Qdrant, and perform a small retrieval test.

## Notes and next steps
- This repo has been refactored so active code lives in `data_collection/`, `db/`, and `pipeline/`.
- Keep `archive/` for reference only.
- Dependencies are managed with `uv` via `pyproject.toml` and `uv.lock`.

---
Last updated: March 2026
