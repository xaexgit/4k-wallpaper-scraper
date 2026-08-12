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
OUTPUT_JSON = Path("4k_nature.json")

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
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
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
        
        # Extract wallpaper numeric ID from URL (e.g., 'mountain-landscape-26973.html' -> '26973')
        id_match = re.search(r"-(\d+)\.html$", detail_url)
        wallpaper_id = id_match.group(1) if id_match else None

        img_url = None
        title = "4K Nature Wallpaper"

        try:
            resp = self.session.get(detail_url, timeout=15)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            # Extract Title
            h1 = soup.find("h1")
            if h1:
                title = h1.text.strip()

            # Strategy 1: Check HTML elements (img tags, source tags, picture elements)
            img_tag = (
                soup.find("img", id="wallpaper") or
                soup.find("img", class_=re.compile(r"wallpaper", re.I)) or
                soup.select_one("picture img")
            )
            
            if img_tag:
                img_url = img_tag.get("src") or img_tag.get("data-src")

        except requests.RequestException as e:
            logger.warning(f"Error requesting page {detail_url}, using ID fallback: {e}")

        # Strategy 2: Fallback to URL pattern logic using extracted ID
        if not img_url and wallpaper_id:
            img_url = f"https://4kwallpapers.com/images/walls/thumbs_3t/{wallpaper_id}.png"

        if not img_url:
            logger.warning(f"Could not determine image link for {detail_url}")
            return None

        if img_url.startswith("/"):
            img_url = f"{BASE_URL}{img_url}"

        # Clean filename extraction
        raw_filename = f"{wallpaper_id}.png" if wallpaper_id else img_url.split("/")[-1].split("?")[0]
        ext = raw_filename.split(".")[-1].lower() if "." in raw_filename else "png"
        mime_type, _ = mimetypes.guess_type(raw_filename)
        quality = "4K" if "4k" in title.lower() else "HD"

        return {
            "id": wallpaper_id,
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
