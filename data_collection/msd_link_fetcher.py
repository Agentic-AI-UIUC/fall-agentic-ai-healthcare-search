import asyncio
import csv
from playwright.async_api import async_playwright

BASE = "https://www.msdmanuals.com"
START_URL = f"{BASE}/professional/health-topics"
OUTPUT_FILE = "msd_subtopics.csv"

async def get_section_links(page):
    """Extract all section URLs from the health-topics page"""
    await page.goto(START_URL, wait_until="networkidle")
    
    # Wait for the links to load
    await page.wait_for_selector('main a[href]', timeout=10000)
    
    links = await page.locator('//main//div//a[@href]').all()
    section_urls = []
    for link in links:
        href = await link.get_attribute('href')
        if href and href.startswith('/'):
            section_urls.append(BASE + href)
    
    return list(set(section_urls))  # Remove duplicates

async def get_first_level_subtopics(page, section_url):
    """Extract only the first-level subtopic links from a section page"""
    await page.goto(section_url, wait_until="networkidle")
    
    # Wait for content to load
    await page.wait_for_selector('main', timeout=10000)
    await asyncio.sleep(2)  # Extra wait for JS to render content
    
    # XPath for first-level subtopics
    links = await page.locator(
        '//main/div[1]/div/div/div[2]/div[1]/div/div[2]/div/div/div/ul/li/div/a'
    ).all()
    
    urls = []
    for link in links:
        href = await link.get_attribute('href')
        title = await link.inner_text()
        if href:
            if href.startswith('/'):
                full_url = BASE + href
            elif not href.startswith('http'):
                full_url = BASE + '/' + href.lstrip('/')
            else:
                full_url = href
            urls.append({"title": title.strip(), "section": section_url, "url": full_url, "source": "MSD"})
    
    return urls

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        section_urls = await get_section_links(page)
        print(f"Found {len(section_urls)} sections")
        
        all_links = []
        for section_url in section_urls:  # remove slicing when ready for all
            try:
                subtopics = await get_first_level_subtopics(page, section_url)
                print(f"{section_url} → {len(subtopics)} subtopics")
                all_links.extend(subtopics)
            except Exception as e:
                print(f"Error in {section_url}: {e}")
        
        await browser.close()
        
        print(f"\nTotal subtopic links found: {len(all_links)}")
        
        # Save to CSV
        with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["title", "source", "section", "url"])
            writer.writeheader()
            for row in all_links:
                writer.writerow({
                    "title": row["title"],
                    "source": row["source"],
                    "section": row["section"],
                    "url": row["url"]
                })
        
        print(f"Saved subtopics to {OUTPUT_FILE}")

if __name__ == "__main__":
    asyncio.run(main())