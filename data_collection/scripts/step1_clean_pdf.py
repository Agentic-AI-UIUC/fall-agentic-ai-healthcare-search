from pypdf import PdfReader
from langchain_text_splitters import RecursiveCharacterTextSplitter
import re
import json
import os

PDF_DIR = "data_collection/sources/pdfs"

# stuff to remove 
junk_signals = [
    "copyright",
    "all rights reserved",
    "isbn",
    "mhid",
    "mcgraw-hill",
    "bulksales@",
    "terms of use",
    "this page intentionally left blank",
    "color insert appears",
    "appears between pages",
    "contributing authors",
    "preface",
    "acknowledgments",
    "acknowledgements",
    "table of contents",
]

def looks_like_toc(chunk: str) -> bool:
    low = chunk.lower()

    front_matter_context = (
        "contents" in low
        or "table of contents" in low
        or "contributing authors" in low
        or "preface" in low
        or "acknowledg" in low
        or "index" in low
    )

    dot_leaders = (chunk.count(". .") > 10) or ("..." in chunk)
    digit_heavy = sum(ch.isdigit() for ch in chunk) > 120

    return front_matter_context and (dot_leaders or digit_heavy)


removed_by_junk = 0
removed_by_toc = 0
clean_chunks = []

for filename in os.listdir(PDF_DIR):
    if filename.endswith(".pdf"):
        pdf_path = os.path.join(PDF_DIR, filename)
        print(f"Reading {filename}...")
        reader = PdfReader(pdf_path)

        full_text_list = []
        #Extract raw text from every page
        for i, page in enumerate(reader.pages):
            text = page.extract_text()

            if text:
                # Replace line breaks with spaces
                full_text_list.append(text.replace("\n", " "))
            
            if (i + 1) % 100 == 0:
                print(f"  Processed {i + 1} pages...")

        full_text = " ".join(full_text_list)
        
        #clean hyphens or extra whitespaces 
        full_text = re.sub(r"(\w)-\s+(\w)", r"\1\2", full_text) 
        full_text = re.sub(r"\s+", " ", full_text).strip()      

        #300–500 word chunks
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=3000,   # target chunk length (characters, not words)
            chunk_overlap=250  # overlap so important info near boundaries isn’t lost
        )

        #list of chunk strings
        chunks = splitter.split_text(full_text)

        for c in chunks:
            low = c.lower()

            if any(sig in low for sig in junk_signals):
                removed_by_junk += 1
                continue
            if looks_like_toc(c):
                removed_by_toc += 1
                continue

            clean_chunks.append({
                "text": c,
                "source": filename
            })

#quality check 
print("Finished reading all PDFs. Grouping and cleaning text...")
print(f"Total clean chunks: {len(clean_chunks)}")
print(f"Removed by junk_signals: {removed_by_junk}")
print(f"Removed by looks_like_toc: {removed_by_toc}")

for i, chunk_dict in enumerate(clean_chunks[:3]):
    print(f"\n--- Clean Chunk {i+1} ---\n")
    print(chunk_dict["text"][:400])

#save outputs
with open("data_collection/processed/clean_chunks.txt", "w", encoding="utf-8") as f:
    for i, c_dict in enumerate(clean_chunks, start=1):
        f.write(f"--- CHUNK {i} ({c_dict['source']}) ---\n{c_dict['text']}\n\n")

with open("data_collection/processed/clean_chunks.json", "w", encoding="utf-8") as f:
    json.dump(clean_chunks, f, ensure_ascii=False, indent=2)

print("\nSaved clean_chunks.txt and clean_chunks.json")
