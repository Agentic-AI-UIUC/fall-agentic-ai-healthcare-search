import asyncio
import csv
import os
from selectolax.parser import HTMLParser
import httpx
import pandas as pd

INPUT_CSV = "msd_subtopics.csv"
OUTPUT_CSV = "msd_articles.csv"
BASE = "https://www.msdmanuals.com"
SOURCE = "MSD"
SAVE_INTERVAL = 50  # save after every N articles
CONCURRENCY = 20

# Selector for the content container: look for first div under main with content (class names randomized)
CONTENT_SELECTOR = "main > div:nth-of-type(1) > div > div > div > div:nth-of-type(1) > div:nth-of-type(2)"

# --- Load links ---
df_links = pd.read_csv(INPUT_CSV)
urls_to_fetch = df_links["url"].tolist()

# --- Progress management ---
existing_data = []
if os.path.exists(OUTPUT_CSV):
    print(f"Resuming from existing file {OUTPUT_CSV}")
    existing_data = pd.read_csv(OUTPUT_CSV).to_dict("records")
    fetched_urls = set(row["url"] for row in existing_data)
    urls_to_fetch = [u for u in urls_to_fetch if u not in fetched_urls]
else:
    fetched_urls = set()

print(f"Total URLs to fetch: {len(urls_to_fetch)}")

# --- Async fetch ---
async def fetch_content(client, row):
    url = row["url"]
    try:
        r = await client.get(url, timeout=20)
        r.raise_for_status()
        tree = HTMLParser(r.text)
        # content extraction using relative container
        container = tree.css_first(CONTENT_SELECTOR)
        content = container.text(separator="\n", strip=True) if container else ""
        return {
            "title": row["title"],
            "source": SOURCE,
            "url": url,
            "content": content,
        }
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None

async def worker(sem, client, row, results):
    async with sem:
        res = await fetch_content(client, row)
        if res:
            results.append(res)

async def main():
    sem = asyncio.Semaphore(CONCURRENCY)
    results = existing_data.copy()
    async with httpx.AsyncClient(http2=False, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0"}) as client:
        tasks = []
        for idx, row in enumerate(df_links.to_dict("records")):
            if row["url"] in fetched_urls:
                continue
            tasks.append(worker(sem, client, row, results))

            # Save periodically
            if len(tasks) >= SAVE_INTERVAL:
                await asyncio.gather(*tasks)
                print(f"Saved progress after {len(results)} articles")
                # Write to CSV
                pd.DataFrame(results).to_csv(OUTPUT_CSV, index=False)
                tasks = []

        # Final batch
        if tasks:
            await asyncio.gather(*tasks)
            print(f"Saving final batch, total articles: {len(results)}")
            pd.DataFrame(results).to_csv(OUTPUT_CSV, index=False)

    print("All done!")

if __name__ == "__main__":
    asyncio.run(main())
