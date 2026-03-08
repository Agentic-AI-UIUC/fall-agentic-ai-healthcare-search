"""
I completed the retrieval module for Week 3 by embedding user queries 
with the same sentence-transformers model used during ingestion and using
Qdrant similarity search to return the top 5 relevant chunks from the real 
medical dataset. This replaces the earlier dummy-vector test from Week 2 
and gives the integration step a working retrieval function to plug into 
the rest of the RAG pipeline.
"""



# Import the embedding model used to convert text into vectors
from sentence_transformers import SentenceTransformer

# Import the Qdrant client so Python can talk to the vector database
from qdrant_client import QdrantClient


# -------------------------------
# Configuration settings
# -------------------------------

# Name of the collection (table) inside Qdrant where our chunks are stored
COLLECTION_NAME = "medical_chunks"

# Where the Qdrant database is running
QDRANT_HOST = "localhost"
QDRANT_PORT = 6333

# Embedding model used for both ingestion AND query embedding
MODEL_NAME = "all-MiniLM-L6-v2"

# Number of results we want Qdrant to return
TOP_K = 5


# -------------------------------
# Load model + connect to Qdrant
# -------------------------------

# Load the embedding model (this converts text into vectors)
print(f"Loading embedding model: {MODEL_NAME}...")
model = SentenceTransformer(MODEL_NAME)

# Connect to the Qdrant vector database
client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)


# -------------------------------
# Retrieval function
# -------------------------------

def retrieve_chunks(query_text: str, top_k: int = TOP_K):
    """
    Takes a user's question and returns the most semantically similar
    chunks from the vector database.
    """

    # Convert the user query into a vector using the same embedding model
    query_vector = model.encode(query_text).tolist()

    # Ask Qdrant to find the most similar stored vectors
    search_result = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        limit=top_k,  # number of results we want back
    )

    # Format the results so they are easier to work with
    results = []

    for point in search_result.points:
        results.append({
            "id": point.id,                     # ID assigned during ingestion
            "score": point.score,               # similarity score
            "text": point.payload.get("text", "")  # the original chunk text
        })

    return results


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