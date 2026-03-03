import embeddings
from sentence_transformers import SentenceTransformer, util
import time

#COMPARING 3 MODELS
#tied between MiniLM and MPNet for fastest encoding, it alternates between the 2 for the fastest everytime i run it.

def test_model(model_name: str, verbose: int = 1) -> dict:
    model = SentenceTransformer(model_name)
    embeddings1 = model.encode(embeddings.sentences)

    start = time.time()
    _ = model.encode(embeddings.sentences)
    encode_time_labse = time.time() - start

    start = time.time()
    similarities = model.similarity(embeddings1, embeddings1)
    similarity_time_labse = time.time() - start

    if verbose:
        print(f"{model_name} encoding time: {encode_time_labse:.4f} seconds")
        print(f"{model_name} similarity time: {similarity_time_labse:.4f} seconds")
        print(f"{model_name} similarities:")
        print(similarities)
    return {"Encoding Time":encode_time_labse,"Similarity Time":similarity_time_labse}

if __name__ == "__main__":
    # LaBSE model timing currently at: around 8 seconds encoding
    # 0.0114 seconds similarity run time
    
    #LaBSE Encoding Timing
    test_model('sentence-transformers/LaBSE')

    # MiniLM model timing
    # MINILM model timing currently at: around 3 seconds encoding
    # 0.0001 seconds similarity run time
    test_model("sentence-transformers/all-MiniLM-L12-v2")

    # all-mpnet-base-v2 model timing
    # all-mpnet-base-v2 model timing currently at: around 3 seconds encoding
    # 0.0189 seconds similarity run time
    test_model("sentence-transformers/all-mpnet-base-v2")

