import json
import pandas as pd
from langchain_text_splitters import RecursiveCharacterTextSplitter

MSD_CSV = "data_collection/msd_articles.csv"
PDF_CHUNKS_JSON = "data_collection/processed/clean_chunks.json"

OUT_KB_JSON = "data_collection/knowledge_base.json"
OUT_KB_TXT = "data_collection/knowledge_base_preview.txt"

def main():
    splitter = RecursiveCharacterTextSplitter(chunk_size=3000, chunk_overlap=250)

    kb = []

    # -----------------------------
    # 1) Load PDF chunks (already chunked)
    # -----------------------------
    with open(PDF_CHUNKS_JSON, "r", encoding="utf-8") as f:
        pdf_chunks = json.load(f)

    for i, c in enumerate(pdf_chunks, start=1):
        c = (c or "").strip()
        if not c:
            continue
        kb.append({
            "id": f"pdf_{i}",
            "source": "PDF",
            "doc": "symptoms_to_diagnosis.pdf",
            "title": "Symptoms to Diagnosis (PDF)",
            "url": None,
            "text": c
        })

    # -----------------------------
    # 2) Load MSD articles and chunk their content
    # -----------------------------
    df = pd.read_csv(MSD_CSV)

    msd_count = 0
    for idx, row in df.iterrows():
        title = str(row.get("title", "")).strip()
        url = str(row.get("url", "")).strip()
        content = str(row.get("content", "")).strip()

        if not content or len(content) < 200:
            continue

        chunks = splitter.split_text(content)

        for j, c in enumerate(chunks, start=1):
            c = (c or "").strip()
            if not c:
                continue
            msd_count += 1
            kb.append({
                "id": f"msd_{idx}_{j}",
                "source": "MSD",
                "doc": None,
                "title": title,
                "url": url,
                "text": c
            })

    # -----------------------------
    # 3) Save combined KB
    # -----------------------------
    with open(OUT_KB_JSON, "w", encoding="utf-8") as f:
        json.dump(kb, f, ensure_ascii=False, indent=2)

    # small human preview
    with open(OUT_KB_TXT, "w", encoding="utf-8") as f:
        f.write(f"TOTAL ENTRIES: {len(kb)}\n")
        f.write(f"PDF CHUNKS: {len([x for x in kb if x['source']=='PDF'])}\n")
        f.write(f"MSD CHUNKS: {len([x for x in kb if x['source']=='MSD'])}\n\n")
        for k in kb[:5]:
            f.write(f"--- {k['id']} ({k['source']}) {k['title']} ---\n")
            f.write(k["text"][:800] + "\n\n")

    print("Saved:", OUT_KB_JSON)
    print("Saved preview:", OUT_KB_TXT)
    print("Total entries:", len(kb))
    print("PDF chunks:", len([x for x in kb if x["source"] == "PDF"]))
    print("MSD chunks:", len([x for x in kb if x["source"] == "MSD"]))

if __name__ == "__main__":
    main()