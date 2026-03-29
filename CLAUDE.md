# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

RAG (Retrieval-Augmented Generation) pipeline for medical text search. Ingests medical documents (PDFs, MSD articles), chunks and embeds them, stores vectors in Qdrant, and retrieves relevant context to answer user queries via a Flask web app.

## Architecture

The system has three layers connected in sequence:

1. **Data collection & preprocessing** (`data_collection/scripts/`) — Scrapes MSD articles, extracts/cleans PDF text, chunks with LangChain `RecursiveCharacterTextSplitter` (3000 chars, 250 overlap), outputs to `data_collection/processed/`.

2. **Vector DB ingestion** (`db/ingestion.py`) — Embeds chunks with `all-MiniLM-L6-v2` (sentence-transformers), upserts into Qdrant collection `medical_chunks` with cosine similarity. Batch size 100.

3. **Retrieval + serving** — `pipeline/retriever.py` embeds user queries with the same model and searches Qdrant for top-k chunks. `app.py` (Flask) serves the frontend and exposes `/api/chat`, `/api/upload`, `/api/health`. Currently uses a temporary answer builder (concatenates retrieved chunks) instead of a real LLM generator — `pipeline/generator.py` is a placeholder.

The frontend (`frontend/`) is vanilla HTML/JS/CSS. `app.js` manages chat state in localStorage, renders messages/sources, and calls the Flask API.

`archive/` contains legacy code — not active, kept for reference only.

## Commands

```bash
# Start Qdrant (required before running the app)
docker run -p 6333:6333 -v qdrant_storage:/qdrant/storage qdrant/qdrant:v1.2.0

# Ingest data into Qdrant (one-time, after Qdrant is running)
python db/ingestion.py

# Run the Flask web app (serves frontend + API on port 5000)
python app.py

# Test Qdrant connection with dummy vectors
python db/test_qdrant.py

# Run retriever standalone (interactive query prompt)
python pipeline/retriever.py
```

## Key Configuration

- Qdrant: `localhost:6333`, collection name `medical_chunks`
- Embedding model: `all-MiniLM-L6-v2` (must be consistent between ingestion and retrieval)
- Flask app: port 5000, serves static files from `frontend/`
- Chunked data source: `data_collection/processed/clean_chunks.json`

## Dependencies

No `requirements.txt` yet. Core packages: `flask`, `sentence-transformers`, `qdrant-client`, `langchain-text-splitters`, `pypdf`, `pandas`.


## TODO: Agentic Upgrade Plan — LangGraph / LangChain

This plan transforms the current basic RAG pipeline into a multi-agent healthcare system using **LangGraph** for orchestration and **LangChain** for tool/chain composition. The goal is an intelligent assistant that can conduct patient intakes, answer medical questions with cited sources, explain uploaded documents, and help users find and schedule appointments with nearby providers.

### Phase 1: LLM Integration & Core Agent Infrastructure

**Goal:** Replace the placeholder `build_answer_from_chunks()` with a real LLM-powered generator and establish the agent framework.

#### 1.1 — Install dependencies and create `requirements.txt`

```
flask
sentence-transformers
qdrant-client
langchain
langchain-community
langchain-anthropic        # or langchain-openai
langgraph
langchain-text-splitters
pypdf
pandas
python-dotenv
```

Create a `.env` file (gitignored) for API keys:
```
ANTHROPIC_API_KEY=sk-...
# or OPENAI_API_KEY=sk-...
GOOGLE_MAPS_API_KEY=...          # Phase 4
ZOCDOC_API_KEY=...               # Phase 4 (or scraping fallback)
```

#### 1.2 — Implement `pipeline/generator.py` (LLM answer synthesis)

This is the first file to fill in. It takes retrieved chunks + user query and produces a grounded, plain-language medical answer.

**What to build:**
- A LangChain `ChatPromptTemplate` with a medical system prompt that enforces:
  - Plain-language explanations (8th-grade reading level)
  - Source attribution ("According to [Source X]...")
  - Disclaimer that this is not a substitute for professional advice
  - Emergency detection: if symptoms suggest emergency (chest pain + shortness of breath, stroke symptoms, etc.), prepend a bold warning to call 911
- A `generate_answer(query: str, chunks: list[dict], conversation_history: list[dict]) -> str` function
- Use local model llama.cpp
- Include conversation history for multi-turn context

**Prompt template structure:**
```
System: You are a medical information assistant. You answer questions using ONLY
the provided source context. Cite sources. Use plain language. If the user describes
emergency symptoms, warn them immediately. Always end with a disclaimer.

Context: {retrieved_chunks}
Conversation history: {history}
User question: {query}
```

**File:** `pipeline/generator.py`

#### 1.3 — Implement `pipeline/main.py` (LangGraph orchestrator)

This is the central state graph that routes user messages through the correct agent path.

**State schema:**
```python
class AgentState(TypedDict):
    messages: list                  # conversation history
    user_query: str                 # current user input
    intent: str                     # classified intent (intake, question, document, appointment, provider_search)
    retrieved_chunks: list[dict]    # from Qdrant
    generated_answer: str           # from generator
    sources: list[dict]             # formatted source cards
    intake_form: dict               # structured intake data (Phase 2)
    user_location: dict             # lat/lng (Phase 4)
    appointment_results: list       # found appointments (Phase 4)
    provider_results: list          # found providers (Phase 4)
    uploaded_document: dict         # document metadata + extracted text
    emergency_flag: bool            # true if emergency symptoms detected
```

**Graph nodes (build incrementally across phases):**

```
              +------------------+
              |  Intent Classifier|
              +--------+---------+
                       |
         +-------------+-------------+-------------+
         |             |             |             |
    [intake]     [question]    [document]    [appointment]
         |             |             |             |
  Intake Agent   Retrieval     Doc Analysis   Appointment
         |        + Generator       |          Finder
         |             |             |             |
         +-------------+-------------+-------------+
                       |
              +--------+---------+
              | Response Formatter|
              +------------------+
```

**File:** `pipeline/main.py`

#### 1.4 — Wire into Flask (`app.py`)

Update `/api/chat` to call the LangGraph orchestrator instead of the raw retriever + temp builder:

```python
# Replace:
chunks = retrieve_chunks(augmented_query, top_k=5)
answer = build_answer_from_chunks(user_message, chunks)
sources = convert_chunks_to_sources(chunks)

# With:
from pipeline.main import run_agent
result = run_agent(user_message, conversation_id, uploaded_document_id)
answer = result["generated_answer"]
sources = result["sources"]
```

---

### Phase 2: Patient Intake Agent

**Goal:** The landing page "Begin Intake" flow becomes a structured, multi-turn conversation that collects patient information and builds an intake form.

#### 2.1 — Intake state machine (`pipeline/agents/intake_agent.py`)

A LangGraph subgraph with its own state that guides the patient through intake:

**Intake flow (nodes in subgraph):**
0. PATIENT INTAKE IS OPTIONAL: user should be able to choose whether they'd like to fill out a sharable patient intake form or go straight to the regular chat and document upload interface 
1. **greeting** — "Hi! I'll help you create your intake form. Let's start with what's bringing you in today."
2. **symptom_collection** — Ask about primary symptoms. Use the LLM to ask clarifying follow-ups:
   - "When did this start?"
   - "On a scale of 1-10, how severe?"
   - "Is it constant or does it come and go?"
   - "What makes it better or worse?"
3. **history_collection** — Ask about:
   - Current medications
   - Known allergies
   - Pre-existing conditions
   - Recent surgeries or hospitalizations
   - Family history of relevant conditions
4. **lifestyle_collection** — Optional but useful:
   - Smoking/alcohol/exercise
   - Recent travel (if relevant to symptoms)
5. **summary_and_confirm** — Present a structured summary of everything collected. Ask the user to confirm or correct anything.
6. **emergency_check** — At every node, run an emergency classifier. If triggered, interrupt the flow with: "Based on what you've described, please seek immediate medical attention or call 911."

**Output:** A structured `intake_form` dict:
```python
{
    "chief_complaint": "persistent headaches for 2 weeks",
    "symptoms": [
        {"name": "headache", "severity": 8, "duration": "2 weeks", "frequency": "daily", "triggers": "stress, bright lights"}
    ],
    "medications": ["ibuprofen 400mg as needed"],
    "allergies": ["penicillin"],
    "conditions": ["migraine history"],
    "family_history": ["mother: hypertension"],
    "lifestyle": {"smoking": false, "exercise": "3x/week"},
    "emergency_flag": false,
    "timestamp": "2026-03-29T..."
}
```

#### 2.2 — New API endpoint

```
POST /api/intake
  Input:  {"message": str, "intake_session_id": str}
  Output: {"response": str, "intake_complete": bool, "intake_form": dict | null, "emergency": bool}
```

When `intake_complete` is true, the frontend transitions to the main app and the intake form is stored server-side and made available as context for all future queries in that session.

#### 2.3 — Frontend updates

- Landing page chat: connect to `/api/intake` instead of `/api/chat`
- Show progress indicator (step 1 of 5, step 2 of 5, etc.)
- On completion, display the intake summary card and "Continue to assistant" button
- Pass `intake_session_id` to main app so the intake context carries over

---

### Phase 3: Document Analysis Agent

**Goal:** When a user drops a medical document, the system extracts text, chunks it, and conducts an intelligent multi-part explanation.

#### 3.1 — Document processing (`pipeline/agents/document_agent.py`)

**Processing pipeline:**
1. **Extract text** — Use `pypdf` for PDFs, plain read for `.txt`, `python-docx` for `.docx`
2. **Chunk the document** — Use `RecursiveCharacterTextSplitter` (same settings as ingestion: 3000 chars, 250 overlap)
3. **Embed and store temporarily** — Either:
   - Create a temporary Qdrant collection per document (deleted after session), or
   - Store chunks in memory for the session
4. **Generate structured explanation** — Use the LLM with a specialized document analysis prompt:

**Analysis sections (each is a node in the subgraph):**
- **Overview** — What type of document is this? What's the main finding?
- **Key findings** — List and explain each significant finding in plain language
- **Medications** — Extract and explain any medications mentioned (dosage, purpose, side effects)
- **Action items** — What does the patient need to do? Follow-up appointments, lifestyle changes, medication schedules
- **Warning signs** — What should make the patient contact their doctor immediately?
- **Questions to ask** — Suggest questions the patient should ask at their next visit

**Output format:**
```python
{
    "document_type": "lab_results",
    "overview": "This is a blood panel from 2026-03-15...",
    "findings": [...],
    "medications": [...],
    "action_items": [...],
    "warning_signs": [...],
    "suggested_questions": [...],
    "full_text": "..."  # stored for follow-up chat queries
}
```

#### 3.2 — Update `/api/upload` endpoint

After file upload, trigger document processing pipeline. Return the structured analysis:

```
POST /api/upload
  Input:  FormData with file
  Output: {
    "document_id": str,
    "analysis": { overview, findings, medications, ... },
    "summary": str
  }
```

#### 3.3 — Conversational follow-up

After initial analysis, the user can ask follow-up questions in the chat about their document. The document chunks are included as additional context alongside the Qdrant retrieval results.

---

### Phase 4: Appointment & Provider Search Agents

**Goal:** Use the intake form and user location to find nearby medical professionals and help schedule appointments.

#### 4.1 — Location handling

Add a new API endpoint and frontend prompt:
```
POST /api/location
  Input:  {"zip_code": str} or {"lat": float, "lng": float}
  Output: {"location": {"lat": float, "lng": float, "city": str, "state": str}}
```

Frontend: After intake or on demand, ask user for zip code or request browser geolocation.

#### 4.2 — Provider search agent (`pipeline/agents/provider_agent.py`)

**LangGraph tool-using agent** that searches for medical providers. This agent has access to these LangChain tools:

**Tool 1: `search_providers`**
- Uses Google Maps Places API (or similar) to search for medical professionals
- Input: specialty (derived from symptoms), location, radius
- Query examples: "cardiologist near 10001", "primary care physician near Brooklyn, NY"
- Returns: list of providers with name, address, phone, rating, hours, distance

**Tool 2: `filter_providers`**
- Filters results by: insurance accepted (if known), rating threshold, distance, availability
- Takes the raw provider list and applies user preferences

**Tool 3: `get_provider_details`**
- Gets detailed info about a specific provider: reviews, specialties, accepted insurance, next available appointment
- Could use Google Places details API or scrape provider websites

**Specialty mapping logic:**
```python
SYMPTOM_TO_SPECIALTY = {
    "chest pain": ["cardiologist", "emergency medicine"],
    "headache": ["neurologist", "primary care"],
    "skin rash": ["dermatologist"],
    "joint pain": ["rheumatologist", "orthopedist"],
    "anxiety": ["psychiatrist", "psychologist"],
    "cough": ["pulmonologist", "primary care"],
    # ... comprehensive mapping
}
```

Use the LLM to map complex symptom descriptions to specialties when the lookup table isn't sufficient.

**Output:**
```python
{
    "recommended_specialty": "neurologist",
    "reasoning": "Based on your persistent headaches with visual disturbances...",
    "providers": [
        {
            "name": "Dr. Sarah Chen",
            "specialty": "Neurology",
            "address": "123 Medical Ave, New York, NY 10001",
            "phone": "(212) 555-0123",
            "distance": "0.8 miles",
            "rating": 4.7,
            "next_available": "2026-04-02",
            "accepts_insurance": ["Aetna", "Blue Cross", "United"]
        },
        ...
    ]
}
```

#### 4.3 — Appointment scheduling agent (`pipeline/agents/appointment_agent.py`)

**LangGraph tool-using agent** for appointment booking:

**Tool 1: `check_availability`**
- Checks available time slots for a specific provider
- Data sources: provider API integrations, or web scraping of booking pages
- Returns: list of available date/time slots

**Tool 2: `create_appointment_hold`**
- Places a tentative hold on a time slot
- Returns a confirmation link the user can click to finalize
- NOTE: Full booking requires authentication — for MVP, generate a deep link to the provider's booking page with pre-filled info

**Tool 3: `generate_booking_link`**
- For providers with online booking (Zocdoc, Healthgrades, provider websites)
- Generates a direct link with specialty, location, and date pre-filled
- Example: `https://www.zocdoc.com/search?specialist=neurologist&location=10001`

**Conversational flow:**
```
User: "Can you help me find a neurologist near me?"
Agent: "Based on your intake, I'd recommend seeing a neurologist for your headaches.
        I found 3 highly-rated neurologists within 5 miles:

        1. Dr. Sarah Chen — 4.7 stars, 0.8 mi — Next available: Apr 2
        2. Dr. Michael Park — 4.5 stars, 1.2 mi — Next available: Apr 5
        3. Dr. Lisa Wong — 4.8 stars, 3.1 mi — Next available: Apr 8

        Would you like to book with any of these? I can also filter by insurance."

User: "I have Blue Cross. Show me Dr. Chen's availability."
Agent: "Dr. Chen accepts Blue Cross. Here are her available slots this week:
        - Wed Apr 2, 10:00 AM
        - Wed Apr 2, 2:30 PM
        - Fri Apr 4, 9:00 AM

        [Book on Zocdoc] [Call office: (212) 555-0123]"
```

#### 4.4 — New API endpoints

```
POST /api/providers/search
  Input:  {"specialty": str, "location": str | {"lat": float, "lng": float}, "radius_miles": int, "insurance": str?}
  Output: {"providers": [...], "recommended_specialty": str, "reasoning": str}

POST /api/providers/{id}/availability
  Input:  {"date_range_start": str, "date_range_end": str}
  Output: {"slots": [{"datetime": str, "duration_min": int}]}

POST /api/appointments/book
  Input:  {"provider_id": str, "slot": str, "patient_info": dict}
  Output: {"booking_link": str, "confirmation": str}
```

#### 4.5 — Frontend updates

- Add a "Find providers" button/tab in the main app
- Provider search results displayed as cards with name, rating, distance, next available
- Clicking a provider shows details + available slots
- "Book appointment" opens external booking link or shows contact info
- Map view (optional, using Leaflet.js or Google Maps embed) showing provider locations

---

### Phase 5: Emergency Detection & Red Flags System

**Goal:** A cross-cutting concern that monitors all user input for emergency symptoms and interrupts the normal flow when detected.

#### 5.1 — Emergency classifier (`pipeline/agents/emergency_agent.py`)

**Runs as a check node before every other node in the main graph.**

**Two-layer detection:**
1. **Keyword match** (fast, no LLM call): Check against a curated list of emergency phrases
   - "can't breathe", "chest pain", "stroke", "seizure", "bleeding won't stop", "unconscious", "suicidal", "overdose"
2. **LLM classifier** (if keyword match is ambiguous): Ask the LLM to classify severity on a 1-5 scale

**Emergency response:**
- Severity 5 (life-threatening): Bold red banner — "CALL 911 IMMEDIATELY" — stop all other processing
- Severity 4 (urgent): "Please go to the nearest emergency room or urgent care"
- Severity 3 (needs attention): "Please contact your doctor within 24 hours"
- Severity 1-2: Continue normal flow

**Reference:** `archive/src/redflags.py` has an earlier version of this logic to build on.

---

### Phase 6: Conversation Memory & Context Management

**Goal:** Move from client-only localStorage to server-side conversation state with LangGraph checkpointing.

#### 6.1 — Server-side state store

Options (pick one):
- **SQLite** (simplest for dev): Store conversations, intake forms, user profiles
- **PostgreSQL** (production): Full relational storage
- **LangGraph MemorySaver / SqliteSaver**: Built-in checkpointing for agent state

**Schema:**
```sql
-- conversations
id UUID PRIMARY KEY,
created_at TIMESTAMP,
title TEXT,
intake_form JSONB,
user_location JSONB

-- messages
id UUID PRIMARY KEY,
conversation_id UUID REFERENCES conversations,
role TEXT,          -- user | assistant | system
content TEXT,
sources JSONB,
created_at TIMESTAMP

-- documents
id UUID PRIMARY KEY,
conversation_id UUID REFERENCES conversations,
filename TEXT,
file_path TEXT,
analysis JSONB,
uploaded_at TIMESTAMP
```

#### 6.2 — LangGraph checkpointing

Use `langgraph.checkpoint` to persist agent state between API calls:

```python
from langgraph.checkpoint.sqlite import SqliteSaver

memory = SqliteSaver.from_conn_string("checkpoints.db")
graph = graph_builder.compile(checkpointer=memory)

# Each API call resumes from the last checkpoint:
result = graph.invoke(input, config={"configurable": {"thread_id": conversation_id}})
```

This means the intake agent can pause between turns and resume exactly where it left off.

---

### Implementation Order & File Map

```
Phase 1 (LLM + framework):
  pipeline/generator.py          — LLM answer synthesis
  pipeline/main.py               — LangGraph orchestrator + intent classifier
  pipeline/tools/__init__.py     — Shared tool definitions
  pipeline/prompts.py            — All prompt templates
  .env                           — API keys
  requirements.txt               — All dependencies

Phase 2 (Intake agent):
  pipeline/agents/__init__.py
  pipeline/agents/intake_agent.py   — Multi-turn intake subgraph
  app.py                            — Add /api/intake endpoint
  frontend/app.js                   — Connect landing page to intake API

Phase 3 (Document analysis):
  pipeline/agents/document_agent.py — Document processing + explanation
  pipeline/utils/text_extract.py    — PDF/DOCX/TXT extraction helpers
  app.py                            — Update /api/upload to return analysis

Phase 4 (Provider search + appointments):
  pipeline/agents/provider_agent.py     — Provider search with Google Maps tools
  pipeline/agents/appointment_agent.py  — Availability checking + booking links
  pipeline/tools/maps_tools.py          — Google Maps API wrapper tools
  pipeline/tools/booking_tools.py       — Booking/scheduling tool definitions
  app.py                                — Add /api/providers/*, /api/appointments/*
  frontend/app.js                       — Provider cards, map view, booking UI

Phase 5 (Emergency detection):
  pipeline/agents/emergency_agent.py — Keyword + LLM emergency classifier
  pipeline/main.py                   — Wire emergency check into graph

Phase 6 (Persistence):
  pipeline/memory.py             — Conversation store + LangGraph checkpointing
  app.py                         — Replace in-memory state with DB
  db/schema.sql                  — Database schema
```

### External APIs & Services Required

| Service | Purpose | Phase | Free Tier |
|---------|---------|-------|-----------|
| Anthropic Claude API (or OpenAI) | LLM for generation, classification, intake | 1+ | Pay-per-token |
| Google Maps Places API | Provider search by location + specialty | 4 | $200/mo free credit |
| Google Maps Geocoding API | Zip code to lat/lng conversion | 4 | Included in Maps credit |
| Zocdoc / Healthgrades | Provider details, availability, booking links | 4 | Scraping or partnerships |
| Qdrant | Vector similarity search (already set up) | All | Self-hosted (free) |

### Key Design Principles

1. **Every answer is source-grounded.** The LLM must cite which retrieved chunk(s) support each claim. No hallucinated medical advice.
2. **Emergency detection is non-negotiable.** It runs on every user message, before any other processing. False positives are acceptable; false negatives are not.
3. **The system is an information tool, not a doctor.** Every response includes a disclaimer. The intake form is for the user's convenience, not a diagnosis.
4. **Graceful degradation.** If the LLM API is down, fall back to the current chunk-concatenation approach. If provider search fails, suggest the user search manually. Never show a blank error.
5. **Privacy first.** Intake forms, health data, and uploaded documents are stored locally (SQLite) and never sent to third-party analytics. Only the LLM API sees the text, and only as needed for the current query.

