import json
import logging
import mimetypes
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("WallpaperLinkScraper")

BASE_URL = "https://4kwallpapers.com"
CATEGORY_URL = f"{BASE_URL}/nature/"
OUTPUT_JSON = Path("wall.json")

# Number of listing pages to scrape (adjust as needed)
MAX_PAGES = 3
DELAY_BETWEEN_REQ = 1.0


class WallpaperLinkScraper:
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
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Referer": "https://4kwallpapers.com/",
        })
        return session

    def get_wallpaper_links(self, page_num: int) -> List[str]:
        url = CATEGORY_URL if page_num == 1 else f"{CATEGORY_URL}?page={page_num}"
        logger.info(f"Fetching page {page_num}: {url}")

        try:
            resp = self.session.get(url, timeout=15)
            resp.raise_for_status()
        except requests.RequestException as e:
            logger.error(f"Failed to fetch page {page_num}: {e}")
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        links = []

        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            if "/nature/" in href and href.endswith(".html") and href != "/nature/":
                full_url = href if href.startswith("http") else f"{BASE_URL}{href}"
                if full_url not in links:
                    links.append(full_url)

        logger.info(f"Found {len(links)} wallpaper pages on page {page_num}")
        return links

    def parse_wallpaper_detail(self, detail_url: str) -> Optional[Dict]:
        logger.info(f"Parsing detail page: {detail_url}")
        try:
            resp = self.session.get(detail_url, timeout=15)
            resp.raise_for_status()
        except requests.RequestException as e:
            logger.error(f"Failed to fetch {detail_url}: {e}")
            return None

        soup = BeautifulSoup(resp.text, "html.parser")

        # Extract title
        h1 = soup.find("h1")
        title = h1.text.strip() if h1 else "4K Nature Wallpaper"

        # Find direct high-res image link
        img_url = None
        download_a = soup.find("a", id="download") or soup.find("a", class_=re.compile(r"download", re.I))
        if download_a and download_a.get("href"):
            img_url = download_a["href"]

        if not img_url:
            img_tag = soup.find("img", id="wallpaper") or soup.find("img", class_=re.compile(r"wallpaper", re.I))
            if img_tag and img_tag.get("src"):
                img_url = img_tag["src"]

        if not img_url:
            logger.warning(f"No image link found on {detail_url}")
            return None

        if img_url.startswith("/"):
            img_url = f"{BASE_URL}{img_url}"

        raw_filename = img_url.split("/")[-1].split("?")[0]
        ext = raw_filename.split(".")[-1].lower() if "." in raw_filename else "jpg"
        mime_type, _ = mimetypes.guess_type(raw_filename)
        quality = "4K" if "4k" in title.lower() or "3840" in resp.text else "HD"

        return {
            "name": raw_filename,
            "title": title,
            "quality": quality,
            "image_url": img_url,
            "source_page": detail_url,
            "file_type": mime_type or f"image/{ext}",
            "file_extension": ext
        }

    def run(self):
        wallpapers = []
        for page in range(1, MAX_PAGES + 1):
            detail_links = self.get_wallpaper_links(page)
            if not detail_links:
                break

            for link in detail_links:
                time.sleep(DELAY_BETWEEN_REQ)
                item = self.parse_wallpaper_detail(link)
                if item and item not in wallpapers:
                    wallpapers.append(item)

        payload = {
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            "category": "nature",
            "total_wallpapers": len(wallpapers),
            "wallpapers": wallpapers
        }

        with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

        logger.info(f"Successfully generated {OUTPUT_JSON} with {len(wallpapers)} live links.")


if __name__ == "__main__":
    scraper = WallpaperLinkScraper()
    scraper.run()
