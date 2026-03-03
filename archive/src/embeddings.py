from sentence_transformers import util
import pandas as pd
import embeddings
from sentence_transformers import SentenceTransformer, util

# Function to get top 3 most similar content items to a user query
def get_top_k_similar_content(query, content_embeddings, content_list, model, k=3):
    # Embed the query
    query_embedding = model.encode([query])
    # Compute cosine similarity
    cosine_scores = util.cos_sim(query_embedding, content_embeddings)[0]
    print(util.cos_sim(query_embedding, content_embeddings))
    # Get top k indices
    top_k_indices = cosine_scores.argsort(descending=True)[:k]
    print(top_k_indices)
    # Return the corresponding content
    return [content_list[i] for i in top_k_indices]


if __name__ == "__main__":
    # Make sure to cd to src to run this script
    df = pd.read_csv('illness.csv')
    sentences = df['Content'].tolist()

    model = SentenceTransformer("sentence-transformers/all-MiniLM-L12-v2")
    embeddings1 = model.encode(embeddings.sentences)

    encodings = model.encode(sentences)

    query = "My head hurts"
    sentences = get_top_k_similar_content(query,encodings,sentences, model)
    for i,sentence in enumerate(sentences):
        print(f"{i}. {sentence}")