from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

client = QdrantClient(host="localhost", port=6333)

collection_name = "my_collection"

# Create collection
if not client.collection_exists(collection_name):
    client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(
            size=4,  # match dummy vectors
            distance=Distance.COSINE,
        ),
    )

# Insert dummy vectors
points = [
    PointStruct(id=1, vector=[0.1, 0.2, 0.3, 0.4], payload={"label": "A"}),
    PointStruct(id=2, vector=[0.9, 0.1, 0.1, 0.2], payload={"label": "B"}),
    PointStruct(id=3, vector=[0.2, 0.8, 0.2, 0.1], payload={"label": "C"}),
]

client.upsert(
    collection_name=collection_name,
    points=points,
)

print("Inserted vectors!")

# Define query vector
query_vector = [0.1, 0.2, 0.3, 0.4]

# Search
search_result = client.query_points(
    collection_name=collection_name,
    query=query_vector,
    limit=5,
)

print("\nSearch Results:")
for result in search_result.points:
    print(result)