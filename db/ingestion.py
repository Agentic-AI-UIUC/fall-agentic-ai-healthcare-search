import json
import os
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

# Configuration
COLLECTION_NAME = "medical_chunks_hybrid_fast"
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", 6333))
CHUNKS_FILE = os.path.join(os.path.dirname(__file__), "..", "data_collection", "processed", "clean_chunks.json")

PUBMED_MODEL_NAME = "pritamdeka/S-PubMedBert-MS-MARCO"
BGE_MODEL_NAME = "BAAI/bge-small-en-v1.5"
BATCH_SIZE = 16

def main():

    # Determine the best device (CUDA for NVIDIA, DirectML for Intel Arc/AMD, else CPU)
    import torch
    device = "cpu"
    if torch.cuda.is_available():
        device = "cuda"
        print(f"Hardware Acceleration enabled: CUDA ({torch.cuda.get_device_name()})")
    else:
        try:
            import torch_directml
            if torch_directml.is_available():
                device = torch_directml.device()
                print(f"Hardware Acceleration enabled: DirectML ({torch_directml.device_name(0)})")
        except ImportError:
            print("Running on CPU. Consider installing torch-directml for Intel Arc GPU support.")

    print(f"Loading PubMedBERT model: {PUBMED_MODEL_NAME}...")
    pubmed_model = SentenceTransformer(PUBMED_MODEL_NAME, device=device)
    pubmed_size = pubmed_model.get_sentence_embedding_dimension()
    print(f"PubMedBERT loaded. Vector dimension: {pubmed_size}")

    print(f"Loading BGE Small model: {BGE_MODEL_NAME}...")
    bge_model = SentenceTransformer(BGE_MODEL_NAME, device=device)
    bge_size = bge_model.get_sentence_embedding_dimension()
    print(f"BGE Small loaded. Vector dimension: {bge_size}")

    print(f"Connecting to Qdrant at {QDRANT_HOST}:{QDRANT_PORT}...")
    client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)

    if not client.collection_exists(COLLECTION_NAME):
        print(f"Creating hybrid collection '{COLLECTION_NAME}'...")
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config={
                "pubmedbert": VectorParams(
                    size=pubmed_size,
                    distance=Distance.COSINE,
                ),
                "bge": VectorParams(
                    size=bge_size,
                    distance=Distance.COSINE,
                )
            }
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
        print("  Generating PubMedBERT embeddings...")
        pubmed_embeddings = pubmed_model.encode(batch_chunks, show_progress_bar=True)
        
        # Format for BGE as per documentation (typically BGE requires adding an instruction for retrieving, but for passages simply encoding is fine)
        print("  Generating BGE Small embeddings...")
        bge_embeddings = bge_model.encode(batch_chunks, show_progress_bar=True)
        
        # Prepare Qdrant points
        points = []
        for j, text in enumerate(batch_chunks):
            points.append(
                PointStruct(
                    id=point_id,
                    vector={
                        "pubmedbert": pubmed_embeddings[j].tolist(),
                        "bge": bge_embeddings[j].tolist()
                    },
                    payload={"text": text}
                )
            )
            point_id += 1
            
        client.upsert(
            collection_name=COLLECTION_NAME,
            points=points
        )
        
    print(f"Successfully ingested {len(chunks)} chunks into Qdrant collection '{COLLECTION_NAME}'.")
    
    # Test simple query using both models
    print("\n--- Testing Retrieval (PubMedBERT vs BGE Small) ---")
    query = "blood pressure medication"
    print(f"Querying for: '{query}'")
    
    pubmed_query_vector = pubmed_model.encode(query).tolist()
    # BGE asks to prefix queries with "Represent this sentence for searching relevant passages: " for retrieval
    bge_query = "Represent this sentence for searching relevant passages: " + query
    bge_query_vector = bge_model.encode(bge_query).tolist()
    
    pubmed_result = client.query_points(
        collection_name=COLLECTION_NAME,
        query=pubmed_query_vector,
        using="pubmedbert",
        limit=2,
    )
    
    print("\nPubMedBERT Top Results:")
    for i, result in enumerate(pubmed_result.points):
        print(f"Result {i+1} (Score: {result.score:.4f}):")
        text_preview = result.payload.get("text", "")[:100].replace("\n", " ")
        print(f"{text_preview}...")

    bge_result = client.query_points(
        collection_name=COLLECTION_NAME,
        query=bge_query_vector,
        using="bge",
        limit=2,
    )
    
    print("\nBGE Small Top Results:")
    for i, result in enumerate(bge_result.points):
        print(f"Result {i+1} (Score: {result.score:.4f}):")
        text_preview = result.payload.get("text", "")[:100].replace("\n", " ")
        print(f"{text_preview}...")

if __name__ == "__main__":
    main()