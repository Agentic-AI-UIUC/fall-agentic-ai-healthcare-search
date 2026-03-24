"""
RAG Pipeline Orchestrator

Connects the retriever (Qdrant vector search) to the generator (Ollama LLM)
to answer medical questions grounded in the knowledge base.
"""

from pipeline.retriever import retrieve_chunks
from pipeline.generator import GroqGenerator


def run_pipeline(query: str, top_k: int = 5, model: str = "llama-3.3-70b-versatile") -> dict:
    """
    Full RAG pipeline: query -> retrieve chunks -> generate answer.

    Returns a dict with the answer and the sources used.
    """
    # 1. Retrieve relevant chunks from Qdrant
    chunks = retrieve_chunks(query, top_k=top_k)

    if not chunks:
        return {
            "query": query,
            "answer": "No relevant medical information found in the knowledge base.",
            "sources": [],
        }

    # 2. Generate answer using the LLM with retrieved context
    generator = GroqGenerator(model=model)
    answer = generator.generate(query, chunks)

    return {
        "query": query,
        "answer": answer,
        "sources": chunks,
    }


def main():
    print("=== Medical RAG Pipeline ===\n")

    query = input("Enter a medical question: ").strip()
    if not query:
        print("No query entered.")
        return

    print(f"\nSearching knowledge base...")
    result = run_pipeline(query)

    print(f"\n--- Answer ---\n")
    print(result["answer"])

    print(f"\n--- Sources ({len(result['sources'])}) ---\n")
    for i, src in enumerate(result["sources"], 1):
        print(f"  [{i}] (score: {src['score']:.4f}) {src['text'][:150]}...")
        print()


if __name__ == "__main__":
    main()
