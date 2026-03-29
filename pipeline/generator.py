import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_community.llms import LlamaCpp
from langchain_core.messages import HumanMessage, AIMessage

from pipeline.prompts import chat_prompt

load_dotenv()

# ── Model configuration ──────────────────────────────────────────────
# Point MODEL_PATH to any GGUF file. Override via .env or environment variable.
# Recommended: Mistral-7B-Instruct, Llama-3-8B-Instruct, or BioMistral-7B in GGUF format.
MODEL_PATH = os.getenv(
    "LLAMA_MODEL_PATH",
    str(Path(__file__).resolve().parent.parent / "models" / "model.gguf"),
)

_llm = None


def get_llm():
    """Lazy-load the LLM so the model file is only read once."""
    global _llm
    if _llm is not None:
        return _llm

    if not Path(MODEL_PATH).exists():
        raise FileNotFoundError(
            f"Model file not found at {MODEL_PATH}. "
            "Download a GGUF model and set LLAMA_MODEL_PATH in your .env file. "
            "Example: LLAMA_MODEL_PATH=/path/to/mistral-7b-instruct.Q4_K_M.gguf"
        )

    _llm = LlamaCpp(
        model_path=MODEL_PATH,
        n_ctx=4096,
        n_gpu_layers=-1,        # use GPU if available, 0 for CPU-only
        temperature=0.3,
        max_tokens=1024,
        verbose=False,
    )
    return _llm


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


def format_history(conversation_history: list[dict]) -> list:
    """Convert raw history dicts into LangChain message objects."""
    messages = []
    for msg in conversation_history:
        role = msg.get("role", "")
        text = msg.get("text", "")
        if role == "user":
            messages.append(HumanMessage(content=text))
        elif role == "assistant":
            messages.append(AIMessage(content=text))
    return messages


def generate_answer(
    query: str,
    chunks: list[dict],
    conversation_history: list[dict] | None = None,
) -> str:
    """
    Generate a grounded medical answer using the local LLM.

    Falls back to a simple chunk summary if the model is not available.
    """
    context = format_chunks_as_context(chunks)

    try:
        llm = get_llm()
    except FileNotFoundError:
        return _fallback_answer(chunks)

    history = format_history(conversation_history or [])

    prompt_value = chat_prompt.format_messages(
        context=context,
        history=history,
        query=query,
    )

    # LlamaCpp expects a single string prompt
    prompt_str = "\n".join(m.content for m in prompt_value)
    answer = llm.invoke(prompt_str)
    return answer.strip()


def _fallback_answer(chunks: list[dict]) -> str:
    """Chunk-concatenation fallback when the LLM model file is missing."""
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
        "_Note: Running without an LLM model. Install a GGUF model for full answers. "
        "See CLAUDE.md Phase 1 for setup instructions._",
    ])
    return "\n".join(parts)
