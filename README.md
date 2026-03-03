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
- Embeddings: sentence-transformers (for indexing and query embeddings)
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

## Running Qdrant (dev quickstart)
1. Start Qdrant with Docker Compose or the official image:

```sh
docker run -p 6333:6333 -v qdrant_storage:/qdrant/storage qdrant/qdrant:v1.2.0
```

2. Use `db/ingestion.py` (or `db/test_qdrant.py`) to connect, create a collection, and upsert vectors.

## Notes and next steps
- This repo has been refactored so active code lives in `data_collection/`, `db/`, and `pipeline/`.
- Keep `archive/` for reference only.
- If you want, I can also add a minimal `requirements.txt` and a short `scripts/` folder with reproducible quickstart commands.

---
Last updated: March 2026