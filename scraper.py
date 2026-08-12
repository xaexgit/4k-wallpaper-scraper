import json
import logging
import mimetypes
import re
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

# Number of listing pages to scrape
MAX_PAGES = 3


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
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://4kwallpapers.com/",
        })
        return session

    def parse_listing_page(self, page_num: int) -> List[Dict]:
        url = CATEGORY_URL if page_num == 1 else f"{CATEGORY_URL}?page={page_num}"
        logger.info(f"Fetching listing page {page_num}: {url}")

        try:
            resp = self.session.get(url, timeout=15)
            resp.raise_for_status()
        except requests.RequestException as e:
            logger.error(f"Failed to fetch page {page_num}: {e}")
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        items = []

        # Find all wallpaper item containers or anchor links on the listing grid
        # 4kwallpapers uses links wrapping picture/img tags for each wallpaper card
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            
            # Filter for wallpaper detail links (e.g. /nature/mountain-landscape-26973.html)
            if not ("/nature/" in href and href.endswith(".html") and href != "/nature/"):
                continue

            full_detail_url = href if href.startswith("http") else f"{BASE_URL}{href}"

            # Look for preview image inside this card (img, picture > source, etc.)
            img_tag = a_tag.find("img")
            source_tag = a_tag.find("source")

            raw_img_src = None

            # 1. Try <source srcset="...">
            if source_tag and source_tag.get("srcset"):
                raw_img_src = source_tag["srcset"].split(",")[0].strip().split(" ")[0]

            # 2. Try <img src="..."> or data-src
            if not raw_img_src and img_tag:
                raw_img_src = (
                    img_tag.get("src") or 
                    img_tag.get("data-src") or 
                    img_tag.get("srcset")
                )

            if not raw_img_src:
                continue

            # Ensure image link is absolute
            image_url = raw_img_src if raw_img_src.startswith("http") else f"{BASE_URL}{raw_img_src}"

            # Extract Title & ID
            title = "4K Nature Wallpaper"
            if img_tag and img_tag.get("alt"):
                title = img_tag["alt"].strip()
            elif a_tag.get("title"):
                title = a_tag["title"].strip()

            id_match = re.search(r"-(\d+)\.html$", href)
            wallpaper_id = id_match.group(1) if id_match else None

            filename = image_url.split("/")[-1].split("?")[0]
            ext = filename.split(".")[-1].lower() if "." in filename else "jpg"
            mime_type, _ = mimetypes.guess_type(filename)

            item = {
                "id": wallpaper_id,
                "title": title,
                "quality": "4K" if "4k" in title.lower() else "HD",
                "image_url": image_url,  # ACTUAL LIVE PREVIEW LINK FROM DOM
                "source_page": full_detail_url,
                "file_type": mime_type or f"image/{ext}",
                "file_extension": ext
            }

            # Avoid duplicates
            if not any(x["image_url"] == image_url for x in items):
                items.append(item)

        logger.info(f"Extracted {len(items)} live wallpaper links from page {page_num}")
        return items

    def run(self):
        all_wallpapers = []
        for page in range(1, MAX_PAGES + 1):
            items = self.parse_listing_page(page)
            if not items:
                break
            all_wallpapers.extend(items)

        payload = {
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            "category": "nature",
            "total_wallpapers": len(all_wallpapers),
            "wallpapers": all_wallpapers
        }

        with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

        logger.info(f"Successfully generated {OUTPUT_JSON} with {len(all_wallpapers)} REAL live links.")


if __name__ == "__main__":
    scraper = WallpaperLinkScraper()
    scraper.run()
