import os

from dotenv import load_dotenv
from groq import Groq

from pipeline.prompts import MEDICAL_SYSTEM_PROMPT

load_dotenv()

# ── Groq configuration ──────────────────────────────────────────────

_client = None
MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")


def _get_client():
    global _client
    if _client is not None:
        return _client

    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY environment variable is not set")

    _client = Groq(api_key=api_key)
    return _client


def get_llm():
    """Return the Groq client. Used by pipeline/main.py for intent classification."""
    return _get_client()


def format_chunks_as_context(chunks: list[dict]) -> str:
    """Turn retrieved chunks into a numbered source block for the prompt."""
    if not chunks:
        return "No relevant sources found."

    parts = []
    for i, chunk in enumerate(chunks, start=1):
        text = chunk.get("text", "").strip()
        score = chunk.get("score")
        score_str = f" (relevance: {score:.4f})" if score is not None else ""
        parts.append(f"Source {i}{score_str}:\n{text}")
    return "\n\n".join(parts)


def generate_answer(
    query: str,
    chunks: list[dict],
    conversation_history: list[dict] | None = None,
    intake_form: dict | None = None,
) -> str:
    """Generate a grounded medical answer using Groq."""
    context = format_chunks_as_context(chunks)
    
    profile_text = "No patient profile provided."
    if intake_form:
        profile_parts = []
        keys_to_extract = ["chief_complaint", "demographics", "history", "family_history", "lifestyle", "medications", "allergies"]
        for k in keys_to_extract:
            val = intake_form.get(k)
            if val and str(val).strip():
                clean_k = k.replace("_", " ").title()
                profile_parts.append(f"- {clean_k}: {str(val).strip()}")
        if profile_parts:
            profile_text = "\n".join(profile_parts)

    try:
        client = _get_client()
    except ValueError:
        return _fallback_answer(chunks)

    system_prompt = MEDICAL_SYSTEM_PROMPT.format(
        context=context,
        patient_profile=profile_text,
    )

    messages = [{"role": "system", "content": system_prompt}]

    # Add conversation history if present
    for msg in (conversation_history or []):
        role = msg.get("role", "")
        text = msg.get("text", "")
        if role in ("user", "assistant"):
            messages.append({"role": role, "content": text})

    messages.append({"role": "user", "content": query})

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            temperature=0.3,
            max_tokens=1024,
        )
        return response.choices[0].message.content or ""
    except Exception as e:
        return f"Error communicating with Groq: {str(e)}"


def _fallback_answer(chunks: list[dict]) -> str:
    """Chunk-concatenation fallback when Groq is not available."""
    if not chunks:
        return (
            "I could not find relevant medical context for that question. "
            "Try rewording your question or make sure the Qdrant collection is populated."
        )

    top = chunks[0].get("text", "").strip()[:700]
    second = chunks[1].get("text", "").strip()[:400] if len(chunks) > 1 else ""

    parts = [
        "Here is information from the most relevant medical source:",
        "",
        top,
    ]
    if second:
        parts.extend(["", "Additional context:", second])

    parts.extend([
        "",
        "_Note: GROQ_API_KEY is not set. Set it in your .env file for full LLM answers._",
    ])
    return "\n".join(parts)
