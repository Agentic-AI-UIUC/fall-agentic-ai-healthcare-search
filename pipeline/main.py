from typing import TypedDict

from langgraph.graph import StateGraph, END

from pipeline.retriever import retrieve_chunks
from pipeline.generator import generate_answer, format_chunks_as_context, get_llm
from pipeline.prompts import intent_prompt
from pipeline.agents.scheduling_agent import is_scheduling_request


# ── Agent state ───────────────────────────────────────────────────────

class AgentState(TypedDict, total=False):
    user_query: str
    conversation_history: list[dict]
    uploaded_document_id: str | None
    intent: str
    retrieved_chunks: list[dict]
    generated_answer: str
    sources: list[dict]
    emergency_flag: bool
    app_mode: str  # "patient" | "doctor" — informational, patient graph ignores doctor mode


# ── Graph nodes ───────────────────────────────────────────────────────

def classify_intent(state: AgentState) -> dict:
    """Classify the user message into an intent category."""
    query = state["user_query"]

    # Fast keyword check for scheduling — avoid LLM call
    if is_scheduling_request(query):
        return {"intent": "appointment"}

    try:
        client = get_llm()
        prompt_str = intent_prompt.format(query=query)
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt_str}],
            temperature=0,
            max_tokens=20,
        )
        raw = (response.choices[0].message.content or "").strip().lower()

        # Extract a known intent from the LLM response
        for label in ("question", "document", "greeting", "other"):
            if label in raw:
                return {"intent": label}
        return {"intent": "question"}
    except (ValueError, Exception):
        # No API key or error — default to question so retrieval still works
        return {"intent": "question"}


def retrieve(state: AgentState) -> dict:
    """Embed the user query and retrieve relevant chunks from Qdrant."""
    chunks = retrieve_chunks(state["user_query"], top_k=5)
    return {"retrieved_chunks": chunks}


def generate(state: AgentState) -> dict:
    """Generate an LLM answer from retrieved chunks."""
    answer = generate_answer(
        query=state["user_query"],
        chunks=state.get("retrieved_chunks", []),
        conversation_history=state.get("conversation_history"),
    )

    # Simple emergency keyword check
    emergency_keywords = [
        "call 911", "emergency room", "urgent",
        "chest pain", "can't breathe", "cannot breathe",
        "stroke", "seizure", "unconscious", "suicidal", "overdose",
    ]
    query_lower = state["user_query"].lower()
    emergency = any(kw in query_lower for kw in emergency_keywords)

    return {"generated_answer": answer, "emergency_flag": emergency}


def handle_scheduling(state: AgentState) -> dict:
    """Respond to scheduling requests by directing patient to the booking form."""
    return {
        "generated_answer": (
            "I can help you book an appointment! Please use the **Book Appointment** "
            "form in the panel on the right. Fill in your name, email, preferred date "
            "and time, and reason for visit — I'll get that scheduled for you."
        ),
        "retrieved_chunks": [],
        "emergency_flag": False,
    }


def handle_greeting(state: AgentState) -> dict:
    """Respond to greetings without hitting the retrieval pipeline."""
    return {
        "generated_answer": (
            "Hello! I'm your healthcare assistant. You can ask me medical questions, "
            "upload a document for a plain-language explanation, or describe your symptoms "
            "and I'll help you understand them. How can I help you today?"
        ),
        "retrieved_chunks": [],
        "emergency_flag": False,
    }


def format_response(state: AgentState) -> dict:
    """Convert retrieved chunks into frontend source cards."""
    chunks = state.get("retrieved_chunks", [])
    sources = []
    for i, chunk in enumerate(chunks, start=1):
        text = chunk.get("text", "") or ""
        score = chunk.get("score")
        chunk_id = chunk.get("id")
        sources.append({
            "title": f"Retrieved Chunk {i}" + (f" (ID {chunk_id})" if chunk_id is not None else ""),
            "snippet": text[:350].strip(),
            "score": round(float(score), 4) if score is not None else None,
        })
    return {"sources": sources}


# ── Routing logic ─────────────────────────────────────────────────────

def route_by_intent(state: AgentState) -> str:
    """Route to the appropriate node based on classified intent."""
    intent = state.get("intent", "question")
    if intent == "greeting":
        return "handle_greeting"
    if intent == "appointment":
        return "handle_scheduling"
    return "retrieve"


# ── Build the graph ───────────────────────────────────────────────────

def build_graph() -> StateGraph:
    graph = StateGraph(AgentState)

    graph.add_node("classify_intent", classify_intent)
    graph.add_node("retrieve", retrieve)
    graph.add_node("generate", generate)
    graph.add_node("handle_greeting", handle_greeting)
    graph.add_node("handle_scheduling", handle_scheduling)
    graph.add_node("format_response", format_response)

    graph.set_entry_point("classify_intent")

    graph.add_conditional_edges("classify_intent", route_by_intent)

    graph.add_edge("retrieve", "generate")
    graph.add_edge("generate", "format_response")
    graph.add_edge("handle_greeting", "format_response")
    graph.add_edge("handle_scheduling", "format_response")
    graph.add_edge("format_response", END)

    return graph


_compiled_graph = None


def _get_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_graph().compile()
    return _compiled_graph


# ── Public entry point (called from app.py) ───────────────────────────

def run_agent(
    user_message: str,
    conversation_id: str | None = None,
    uploaded_document_id: str | None = None,
    conversation_history: list[dict] | None = None,
) -> dict:
    """
    Run the full agent pipeline and return a result dict with:
      - generated_answer: str
      - sources: list[dict]
      - emergency_flag: bool
    """
    graph = _get_graph()

    result = graph.invoke({
        "user_query": user_message,
        "conversation_history": conversation_history or [],
        "uploaded_document_id": uploaded_document_id,
    })

    return {
        "generated_answer": result.get("generated_answer", ""),
        "sources": result.get("sources", []),
        "emergency_flag": result.get("emergency_flag", False),
    }


# Alias expected by app.py import
run_pipeline = run_agent
