import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("AlphaCodersScraper")

LINKS_CONFIG_FILE = Path("links.json")
OUTPUT_FILE = Path("out/out.json")

# Number of pages to scrape per link
MAX_PAGES = 3


class AlphaCodersScraper:
    def __init__(self):
        self.session = self._init_session()

    def _init_session(self) -> requests.Session:
        session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=2,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://wall.alphacoders.com/",
        })
        return session

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
        # Replace thumbnail prefix patterns like thumb-350- or thumbbig-
        full_url = re.sub(r"/thumb(big)?(-\d+)?-", "/", thumb_url)
        return full_url

    def parse_listing_page(self, base_url: str, page_num: int) -> List[Dict]:
        page_url = self.build_page_url(base_url, page_num)
        logger.info(f"Fetching page {page_num}: {page_url}")

        try:
            resp = self.session.get(page_url, timeout=15)
            resp.raise_for_status()
        except requests.RequestException as e:
            logger.error(f"Failed to fetch page {page_num}: {e}")
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        items = []

        # AlphaCoders images are usually wrapped inside container divs/cards
        img_tags = soup.find_all("img")

        for img in img_tags:
            # Look for thumbnail image sources
            src = (
                img.get("data-src") or 
                img.get("src") or 
                img.get("data-original")
            )

            if not src or "alphacoders.com" not in src:
                continue

            # Ensure image link has protocol
            if src.startswith("//"):
                src = f"https:{src}"
            elif not src.startswith("http"):
                src = f"https://images.alphacoders.com/{src.lstrip('/')}"

            # Only target actual wallpaper asset URLs
            if not re.search(r"/(thumb|images)/", src):
                continue

            # Extract title / name
            title = img.get("alt") or img.get("title") or "Alpha Coders Wallpaper"
            title = title.strip()

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

        # Remove duplicates
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
