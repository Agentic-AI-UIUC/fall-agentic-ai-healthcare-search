from sentence_transformers import SentenceTransformer
import chromadb
import uuid
import datetime

from transformers import pipeline

class Classifier:
    def __init__(
        self, labels: list, positive_index: int = 0, threshold: float = 0.6
    ) -> None:
        self.classifier = pipeline(
            "zero-shot-classification", model="facebook/bart-large-mnli"
        )
        self.candidate_labels = labels
        self.positive_index = positive_index
        self.threshold = threshold

    def fits(self, text: str, verbose: bool = False) -> bool:
        result = self.classifier(text, self.candidate_labels)
        if verbose:
            print(result["scores"])

        max_in_list = max(result["scores"])
        max_index = result["scores"].index(max_in_list)

        return self.positive_index == max_index and max_in_list > self.threshold

embed_model = SentenceTransformer("sentence-transformers/all-MiniLM-L12-v2")
client = chromadb.PersistentClient(path="./convo-history")
classifier = Classifier(["the writer is describing a symptom of a physical or mental illness","the writer is writing a follow up response"])


collection = client.get_or_create_collection(
    name="chat_history",
    embedding_function=None
)

def embed_text(text: str):
    vec = embed_model.encode(text, convert_to_numpy=True)
    return vec.tolist()

def store_message(convo_id: str, role: str, text: str):
    emb = embed_text(text)
    # get unique id
    user_desc_type = "symptoms" if role == "user" and classifier.fits(text) else "other"
    print(user_desc_type)
        
    message_id = str(uuid.uuid4())
    metadata = {
        "convo_id": convo_id,
        "message_id": message_id,
        "role": role,
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "text": text,
        "user_desc_type": user_desc_type
    }
    collection.add(
        documents=[text],
        embeddings=[emb],
        metadatas=[metadata],
        ids=[message_id]
    )

# query by specific conversation id and related stuff in it
def retrieve_similar(convo_id: str, text: str, top_k: int = 5):
    query_emb = embed_text(text)
    results = collection.query(
        query_embeddings=[query_emb],
        where = {
            "$and": [
                {"convo_id": convo_id},
                {"role": "user"},
                {"user_desc_type": "symptoms"}
            ]
        },
        n_results=top_k,
    )
    return results

if __name__ == "__main__":
    convo_id = "session-124"
    store_message(convo_id, "user", "My leg really really hurts")
    store_message(convo_id, "assistant", "Kinda sucks ngl")
    store_message(convo_id, "user", "I know, it kind of does")

    new_prompt = "Why is my leg broken?"
    sims = retrieve_similar(convo_id, new_prompt, top_k=3)
    print("Similar past pieces:", sims["metadatas"])
