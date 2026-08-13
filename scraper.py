import json
import logging
import re
from pathlib import Path
from typing import Dict, List
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from bs4 import BeautifulSoup
from curl_cffi import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("AlphaCodersScraper")

LINKS_CONFIG_FILE = Path("links.json")
OUTPUT_FILE = Path("out/out.json")

# Number of pages to scrape per category link
MAX_PAGES = 3


class AlphaCodersScraper:
    def __init__(self):
        # Impersonate Chrome browser TLS fingerprint to bypass Cloudflare checks
        self.session = requests.Session(impersonate="chrome")

    @staticmethod
    def build_page_url(base_url: str, page_num: int) -> str:
        """Appends page query param cleanly regardless of existing query strings."""
        if page_num == 1:
            return base_url

        parsed = urlparse(base_url)
        query_dict = parse_qs(parsed.query)
        query_dict["page"] = [str(page_num)]

        new_query = urlencode(query_dict, doseq=True)
        return urlunparse((
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            new_query,
            parsed.fragment
        ))

    @staticmethod
    def get_full_res_url(thumb_url: str) -> str:
        """
        Converts AlphaCoders thumbnail links (e.g., .../thumb-350-12345.webp)
        to full resolution wallpaper links (e.g., .../12345.jpg or .png).
        """
        full_url = re.sub(r"/thumb(big)?(-\d+)?-", "/", thumb_url)
        return full_url

    def parse_listing_page(self, base_url: str, page_num: int) -> List[Dict]:
        page_url = self.build_page_url(base_url, page_num)
        logger.info(f"Fetching page {page_num}: {page_url}")

        try:
            resp = self.session.get(
                page_url, 
                timeout=20,
                headers={
                    "Referer": "https://wall.alphacoders.com/",
                    "Accept-Language": "en-US,en;q=0.9",
                }
            )
            resp.raise_for_status()
        except Exception as e:
            logger.error(f"Failed to fetch page {page_num}: {e}")
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        items = []

        cards = soup.select(".thumb-container-big, .thumb-container, .boxcard, div[class*='thumb']")
        if not cards:
            cards = [soup]

        for container in cards:
            img_tags = container.find_all(["img", "source"])

            for img in img_tags:
                raw_src = None
                if img.get("srcset"):
                    raw_src = img["srcset"].split(",")[0].strip().split(" ")[0]
                if not raw_src:
                    raw_src = img.get("data-src") or img.get("src") or img.get("data-original")

                if not raw_src:
                    continue

                if not re.search(r"(thumb|images|alphacoders)", raw_src, re.IGNORECASE):
                    continue
                if any(x in raw_src for x in ["avatar", "logo", "icon", "badge", "profile"]):
                    continue

                if raw_src.startswith("//"):
                    src = f"https:{raw_src}"
                elif raw_src.startswith("/"):
                    src = f"https://wall.alphacoders.com{raw_src}"
                elif not raw_src.startswith("http"):
                    src = f"https://images.alphacoders.com/{raw_src}"
                else:
                    src = raw_src

                title = img.get("alt") or img.get("title") or ""
                if not title and hasattr(container, "find"):
                    a_tag = container.find("a", title=True)
                    if a_tag:
                        title = a_tag["title"]

                title = title.strip() or "Alpha Coders Wallpaper"

                preview_url = src
                full_image_url = self.get_full_res_url(src)

                item = {
                    "name": title,
                    "url": full_image_url,
                    "previewUrl": preview_url
                }

                if not any(x["previewUrl"] == preview_url for x in items):
                    items.append(item)

        logger.info(f"Extracted {len(items)} wallpapers from page {page_num}")
        return items

    def scrape_url(self, target_url: str) -> List[Dict]:
        logger.info(f"--- Scraping URL: '{target_url}' ---")
        wallpapers = []

        for page in range(1, MAX_PAGES + 1):
            page_items = self.parse_listing_page(target_url, page)
            if not page_items:
                break
            wallpapers.extend(page_items)

        return wallpapers

    def run(self):
        if not LINKS_CONFIG_FILE.exists():
            logger.error(f"Configuration file '{LINKS_CONFIG_FILE}' not found!")
            return

        with open(LINKS_CONFIG_FILE, "r", encoding="utf-8") as f:
            category_links = json.load(f)

        if not isinstance(category_links, list) or not category_links:
            logger.error("links.json must contain a list of URLs.")
            return

        all_wallpapers = []
        for url in category_links:
            items = self.scrape_url(url)
            all_wallpapers.extend(items)

        unique_wallpapers = []
        seen_urls = set()
        for wp in all_wallpapers:
            if wp["previewUrl"] not in seen_urls:
                seen_urls.add(wp["previewUrl"])
                unique_wallpapers.append(wp)

        OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(unique_wallpapers, f, indent=2)

        logger.info(f"Successfully generated {OUTPUT_FILE} with {len(unique_wallpapers)} wallpapers.")


if __name__ == "__main__":
    scraper = AlphaCodersScraper()
    scraper.run()
