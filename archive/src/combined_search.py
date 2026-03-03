from sentence_transformers import SentenceTransformer
import pandas as pd
from sentence_transformers import SentenceTransformer
import pandas as pd
from keybert import KeyBERT
from nltk.stem import WordNetLemmatizer
from nltk.tokenize import word_tokenize

lemmatizer = WordNetLemmatizer()
kw_model = KeyBERT()
encoding_model = SentenceTransformer('sentence-transformers/LaBSE')

CSV_FILE_LOCATION = "/Users/benlozzano/VS-Code-RSO/RAG-AI-Healthcare-2025-Fall/src/illness.csv"
SAMPLE_QUERY = "My head really, really, feels kinda bad"

original_df = pd.read_csv(CSV_FILE_LOCATION)
original_df = original_df.apply(lambda x: x.str.lower() if x.dtype == 'object' else x)

def lemmatize_text(text):
    tokens = word_tokenize(text)

    lemmatized_tokens = [lemmatizer.lemmatize(token) for token in tokens]
    return ' '.join(lemmatized_tokens)

def combined_search(query):
    df = original_df.copy()
    new_series = pd.concat([original_df["Content"],pd.Series([query],index=[len(original_df["Content"])])])
    print(new_series)
    embeddings = encoding_model.encode(new_series)

    x = encoding_model.similarity(embeddings,embeddings)

    df["Encoding_Scores"] = x[-1][:-1]

    return df

def main(original_df, query):
    '''
        original_df: The lematized csv
        query: user query
    '''
    df = combined_search(query)

    original_df['Content'] = original_df['Content'].apply(lemmatize_text)
    original_df['Title'] = original_df['Title'].apply(lemmatize_text)

    df["Scores"] = pd.Series([0] * len(df))


    keywords = kw_model.extract_keywords(SAMPLE_QUERY)

    for word, score in keywords:
        word = lemmatizer.lemmatize(word.lower(), 'v')
            
        df["Body_Count"] = original_df["Content"].str.count(word)

        df["Title_Count"] = original_df["Title"].str.count(word)

        df["Scores"] += df["Body_Count"] * score + df["Title_Count"] * score * 2

    df["Scores"] = df["Encoding_Scores"] * df["Scores"]
    df = df.sort_values("Scores", ascending=False).reset_index(drop=True)
    to_return = df.head(min(10,len(df)))[["Content","URL"]]
    return to_return

if __name__ == "__main__":
    first_ten_df = main(original_df,SAMPLE_QUERY)
    print(first_ten_df)