"""
I completed the retrieval module for Week 3 by embedding user queries 
with the same sentence-transformers model used during ingestion and using
Qdrant similarity search to return the top 5 relevant chunks from the real 
medical dataset. This replaces the earlier dummy-vector test from Week 2 
and gives the integration step a working retrieval function to plug into 
the rest of the RAG pipeline.
"""



# Import the embedding models used to convert text into vectors and rerank
from sentence_transformers import SentenceTransformer, CrossEncoder

# Import the Qdrant client so Python can talk to the vector database
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue


# -------------------------------
# Configuration settings
# -------------------------------

# Name of the collection (table) inside Qdrant where our chunks are stored
# Name of the collection (table) inside Qdrant where our chunks are stored
COLLECTION_NAME = "medical_chunks_hybrid_fast"

# Where the Qdrant database is running
QDRANT_HOST = "localhost"
QDRANT_PORT = 6333

BGE_MODEL_NAME = "BAAI/bge-small-en-v1.5"
PUBMED_MODEL_NAME = "pritamdeka/S-PubMedBert-MS-MARCO"
CROSS_ENCODER_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"

# Number of results we want Qdrant to return
TOP_K = 5

# -------------------------------
# Load models + connect to Qdrant
# -------------------------------

print(f"Loading embedding model: {BGE_MODEL_NAME}...")
bge_model = SentenceTransformer(BGE_MODEL_NAME)

print(f"Loading embedding model: {PUBMED_MODEL_NAME}...")
pubmed_model = SentenceTransformer(PUBMED_MODEL_NAME)

print(f"Loading Cross-Encoder model: {CROSS_ENCODER_NAME}...")
cross_encoder = CrossEncoder(CROSS_ENCODER_NAME)

# Connect to the Qdrant vector database
client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)


# -------------------------------
# Retrieval function
# -------------------------------

def retrieve_chunks(query_text: str, top_k: int = TOP_K, source_filter: str | None = None):
    """
    Takes a user's question, creates two dense vectors, searches Qdrant,
    fuses results with Reciprocal Rank Fusion (RRF), and re-ranks with a CrossEncoder.
    """

    # BGE asks for a prefix instruction
    bge_query = "Represent this sentence for searching relevant passages: " + query_text
    bge_vector = bge_model.encode(bge_query).tolist()
    
    pubmed_vector = pubmed_model.encode(query_text).tolist()

    # Optional metadata filter setup
    query_filter = None
    if source_filter:
        query_filter = Filter(
            must=[FieldCondition(key="source", match=MatchValue(value=source_filter))]
        )

    # 1. Broad retrieval phase - Get top 15 from both embeddings
    candidate_limit = 15

    bge_result = client.query_points(
        collection_name=COLLECTION_NAME,
        query=bge_vector,
        using="bge",
        query_filter=query_filter,
        limit=candidate_limit,
    )

    pubmed_result = client.query_points(
        collection_name=COLLECTION_NAME,
        query=pubmed_vector,
        using="pubmedbert",
        query_filter=query_filter,
        limit=candidate_limit,
    )

    # 2. Reciprocal Rank Fusion (RRF)
    rrf_pool = {}
    
    def add_to_pool(search_result):
        for rank, point in enumerate(search_result.points):
            if point.id not in rrf_pool:
                rrf_pool[point.id] = {
                    "id": point.id,
                    "text": point.payload.get("text", ""),
                    "source": point.payload.get("source", "Unknown Document"),
                    "score": 0.0
                }
            # RRF formula: 1 / (k + rank) where k is typically 60
            rrf_pool[point.id]["score"] += 1.0 / (60.0 + rank)
            
    add_to_pool(bge_result)
    add_to_pool(pubmed_result)
    
    fused_candidates = list(rrf_pool.values())
    # Sort by RRF score descending
    fused_candidates.sort(key=lambda x: x["score"], reverse=True)
    
    # We'll take the top 15 fused candidates to re-rank
    top_fused = fused_candidates[:candidate_limit]

    # If no results found, return empty
    if not top_fused:
        return []

    # 3. Cross-Encoder Re-Ranking phase
    # The cross-encoder takes pairs of (query, document) to evaluate semantic relevance highly accurately.
    cross_input = [[query_text, candidate["text"]] for candidate in top_fused]
    cross_scores = cross_encoder.predict(cross_input)
    
    # Update scores with cross-encoder scores
    for candidate, x_score in zip(top_fused, cross_scores):
        candidate["score"] = float(x_score)
        
    # Sort again based directly on CrossEncoder precision score
    top_fused.sort(key=lambda x: x["score"], reverse=True)

    return top_fused[:top_k]


# -------------------------------
# Main program (runs when script starts)
# -------------------------------

def main():

    # Ask the user to type a question
    query = input("Enter a medical question: ").strip()

    # If the user didn't type anything, stop the program
    if not query:
        print("No query entered.")
        return

    # Run the retrieval function
    results = retrieve_chunks(query)

    # Print the retrieved chunks
    print(f"\nTop {len(results)} retrieved chunks:\n")

    for i, result in enumerate(results, start=1):
        print(f"Result {i}")
        print(f"ID: {result['id']}")
        print(f"Score: {result['score']:.4f}")

        # Print only the first 500 characters so output isn't huge
        print(f"Text: {result['text'][:500]}")

        print("-" * 80)


# -------------------------------
# Entry point
# -------------------------------

# This ensures main() runs only when the script is executed directly
if __name__ == "__main__":
    main()