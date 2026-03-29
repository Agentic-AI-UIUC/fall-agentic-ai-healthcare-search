# Codebase Overview: Agentic AI Healthcare Search

This is an **open research prototype for a Retrieval-Augmented Generation (RAG) pipeline** focused on medical text. The goal is to build an explainable medical assistant that can answer health-related queries with source citations.

---

## Project Structure

```
fall-agentic-ai-healthcare-search/
├── data_collection/          # Data ingestion pipeline
│   ├── scripts/              # PDF extraction, web scraping, KB building
│   │   ├── step1_clean_pdf.py       # PDF extraction and cleaning
│   │   ├── msd_link_fetcher.py      # MSD Manual link scraping
│   │   ├── msd_content_fetcher.py   # MSD Manual content scraping
│   │   └── build_knowledge_base.py  # Combine sources into KB
│   ├── sources/              # Raw PDFs and MSD data
│   └── processed/            # Generated knowledge base (~111K entries, 37MB)
├── db/                       # Vector database integration
│   ├── ingestion.py          # Load embeddings into Qdrant
│   └── test_qdrant.py        # Connectivity tests
├── pipeline/                 # RAG Pipeline (skeleton - not yet implemented)
│   ├── main.py               # Orchestration (empty)
│   ├── retriever.py          # Vector search (empty)
│   └── generator.py          # LLM interface (empty)
├── archive/                  # Legacy experimental code
│   ├── src/                  # Old experimental modules
│   └── convo-history/        # Previous conversation storage
└── README.md                 # Main project documentation
```

---

## Implementation Status

### Completed Components

| Component | Status | Details |
|-----------|--------|---------|
| **PDF Text Extraction** | ✅ Done | Extracts and chunks medical PDFs (~644 chunks) |
| **MSD Manual Scraping** | ✅ Done | Scraped content from msdmanuals.com |
| **Knowledge Base Assembly** | ✅ Done | Combined 111K+ medical document chunks |
| **Vector Database Setup** | ✅ Done | Qdrant integration with sentence-transformers embeddings |
| **Data Ingestion** | ✅ Done | Batch upload to Qdrant verified working |

### Pending Implementation

| Component | Status | Location |
|-----------|--------|----------|
| **Retriever** | ⚠️ Empty | `pipeline/retriever.py` - query Qdrant, get top-k results |
| **Generator** | ⚠️ Empty | `pipeline/generator.py` - LLM interface with prompts |
| **Orchestrator** | ⚠️ Empty | `pipeline/main.py` - coordinate retrieval → generation |

---

## Technology Stack

| Category | Technology |
|----------|------------|
| **Vector Database** | Qdrant (Docker-based, localhost:6333) |
| **Embeddings** | sentence-transformers (`all-MiniLM-L6-v2`, 384-dim) |
| **RAG Framework** | LangChain |
| **Web Scraping** | Playwright, httpx, selectolax |
| **PDF Processing** | pypdf |
| **Data Processing** | pandas, CSV |
| **Python Version** | 3.11+ |

---

## Data Pipeline Details

### Data Sources

1. **PDF Textbook** - "Symptoms to Diagnosis" (medical case studies and diagnostic algorithms)
2. **MSD Manual** - Professional medical reference articles scraped from msdmanuals.com

### Knowledge Base Format

Combined into a **37MB knowledge base** (`knowledge_base.json`) with 111K+ searchable chunks:

```json
{
  "id": "pdf_1" or "msd_idx_j",
  "source": "PDF" or "MSD",
  "title": "document title",
  "url": null or "https://...",
  "text": "chunk content (3000 chars with 250 char overlap)"
}
```

### Processing Pipeline

1. **Step 1:** Extract text from PDFs using `pypdf`
2. **Step 2:** Clean and chunk text (3000 char chunks, 250 char overlap)
3. **Step 3:** Scrape MSD Manual links and content
4. **Step 4:** Combine all sources into unified knowledge base
5. **Step 5:** Generate embeddings and upload to Qdrant

---

## Component Details

### Data Collection (`data_collection/scripts/`)

| Script | Purpose |
|--------|---------|
| `step1_clean_pdf.py` | Extract text from PDFs, clean, and chunk into segments |
| `msd_link_fetcher.py` | Scrape MSD Manual topic links using Playwright |
| `msd_content_fetcher.py` | Fetch article content from MSD URLs using httpx |
| `build_knowledge_base.py` | Combine PDF chunks and MSD articles into unified JSON |

### Database (`db/`)

| Script | Purpose |
|--------|---------|
| `ingestion.py` | Load knowledge base into Qdrant with embeddings |
| `test_qdrant.py` | Verify Qdrant server connectivity |

### Pipeline (`pipeline/`) - TO BE IMPLEMENTED

| Script | Purpose |
|--------|---------|
| `main.py` | Orchestrate retrieval → prompt building → LLM call |
| `retriever.py` | Query Qdrant, retrieve top-k similar chunks |
| `generator.py` | LLM interface with prompt templates and source attribution |

---

## Environment Setup

### Prerequisites

```bash
# Create virtual environment
python3.11 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r archive/requirementsllm.txt
pip install playwright selectolax
python -m playwright install
```

### Running Qdrant (Development)

```bash
# Docker-based local Qdrant
docker run -p 6333:6333 -v qdrant_storage:/qdrant/storage qdrant/qdrant:v1.2.0
```

---

## Recent Git History

| Commit | Description |
|--------|-------------|
| `d5a2c05` | Merge PR #4 - Recent contributions |
| `4b90fa9` | Adding data to Qdrant - Main ingestion verified |
| `18f893f` | Updated README, high-level overview |
| `eb874c1` | Moving test_qdrant |
| `18521a8` | Merge PR #3 - Collaborative updates |

---

## Next Steps

1. **Implement RAG Pipeline:**
   - Fill in `pipeline/retriever.py` - query Qdrant, retrieve top-k
   - Fill in `pipeline/generator.py` - prompt templates, LLM calls
   - Fill in `pipeline/main.py` - orchestration

2. **LLM Integration:**
   - Decide on LLM provider (Groq, Ollama, OpenAI, etc.)
   - Implement prompt engineering with source attribution
   - Add streaming response capability

3. **Testing & Refinement:**
   - Benchmark embedding models and retrieval accuracy
   - Tune chunk size and overlap parameters
   - Evaluate answer quality

4. **Future Enhancements:**
   - Multi-modal retrieval (medical images)
   - Fine-tuned domain embeddings
   - Chat history and conversational context
   - Agent-based specialized tasks (symptom checker, risk assessment)

---

## Summary

The **data foundation is solid** - medical documents are extracted, chunked, and indexed in Qdrant. The **next step** is implementing the actual RAG pipeline (`retriever.py`, `generator.py`, `main.py`) to query the vector database and generate grounded answers with an LLM.
