import json
import os
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

# Configuration
COLLECTION_NAME = "medical_chunks"
QDRANT_HOST = "localhost"
QDRANT_PORT = 6333
CHUNKS_FILE = os.path.join(os.path.dirname(__file__), "..", "data_collection", "processed", "clean_chunks.json")
MODEL_NAME = "all-MiniLM-L6-v2"
BATCH_SIZE = 100

def main():
    print(f"Loading sentence transformer model: {MODEL_NAME}...")
    model = SentenceTransformer(MODEL_NAME)
    vector_size = model.get_sentence_embedding_dimension()
    print(f"Model loaded. Vector dimension: {vector_size}")

    print(f"Connecting to Qdrant at {QDRANT_HOST}:{QDRANT_PORT}...")
    client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)

    if not client.collection_exists(COLLECTION_NAME):
        print(f"Creating collection '{COLLECTION_NAME}'...")
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(
                size=vector_size,
                distance=Distance.COSINE,
            ),
        )
    else:
        print(f"Collection '{COLLECTION_NAME}' already exists.")

    print(f"Loading chunks from {CHUNKS_FILE}...")
    with open(CHUNKS_FILE, 'r', encoding='utf-8') as f:
        chunks = json.load(f)
    print(f"Loaded {len(chunks)} chunks.")

    print(f"Generating embeddings and uploading to Qdrant in batches of {BATCH_SIZE}...")
    point_id = 1
    
    for i in range(0, len(chunks), BATCH_SIZE):
        batch_chunks = chunks[i:i + BATCH_SIZE]
        print(f"Processing batch {i // BATCH_SIZE + 1}/{(len(chunks) + BATCH_SIZE - 1) // BATCH_SIZE} ({len(batch_chunks)} chunks)...")
        
        # Generate embeddings for the batch
        embeddings = model.encode(batch_chunks, show_progress_bar=False)
        
        # Prepare Qdrant points
        points = []
        for j, text in enumerate(batch_chunks):
            points.append(
                PointStruct(
                    id=point_id,
                    vector=embeddings[j].tolist(),
                    payload={"text": text}
                )
            )
            point_id += 1
            
        client.upsert(
            collection_name=COLLECTION_NAME,
            points=points
        )
        
    print(f"Successfully ingested {len(chunks)} chunks into Qdrant collection '{COLLECTION_NAME}'.")
    
    # Test a simple query to verify ingestion
    print("\n--- Testing Retrieval ---")
    query = "blood pressure medication"
    print(f"Querying for: '{query}'")
    query_vector = model.encode(query).tolist()
    
    search_result = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        limit=3,
    )
    
    for i, result in enumerate(search_result.points):
        print(f"\nResult {i+1} (Score: {result.score:.4f}):")
        text_preview = result.payload.get("text", "")[:200]
        print(f"{text_preview}...")

if __name__ == "__main__":
    main()