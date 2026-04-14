What I built
I created a data ingestion pipeline that combines:

medical PDFs (cleaned + chunked)

MSD Manual articles (scraped)

Final output used for RAG:
data_collection/processed/knowledge_base.json

What you need to do

Setup (once)
uv sync
uv run playwright install

(Optional) Re-scrape MSD
uv run python data_collection/scripts/msd_link_fetcher.py
uv run python data_collection/scripts/msd_content_fetcher.py

Add PDFs
Put new textbooks in:
data_collection/sources/pdfs/

Then run:
uv run python data_collection/scripts/step1_clean_pdf.py

Build knowledge base
uv run python data_collection/scripts/build_knowledge_base.py

Use this file for embeddings / vector DB:
data_collection/processed/knowledge_base.json

processed/ is git-ignored so you generate it locally.
