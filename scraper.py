import os
import re
import time
import json
import logging
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
logger = logging.getLogger("WallpaperScraper")

BASE_URL = "https://4kwallpapers.com"
CATEGORY_URL = f"{BASE_URL}/nature/"
DOWNLOAD_DIR = Path("downloads")
METADATA_FILE = Path("scraped_metadata.json")

MAX_PAGES = 2
DELAY_BETWEEN_REQ = 2.0


class WallpaperScraper:
    def __init__(self, output_dir: Path = DOWNLOAD_DIR):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.session = self._init_session()

    def _init_session(self) -> requests.Session:
        session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=3,
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

        # Target link elements on 4kwallpapers grid
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            # Detail page URLs usually follow pattern: /nature/title-1234.html
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

        # Locate high-resolution image link
        img_url = None
        
        # 1. Look for direct download link tag
        download_a = soup.find("a", id="download") or soup.find("a", class_=re.compile(r"download", re.I))
        if download_a and download_a.get("href"):
            img_url = download_a["href"]

        # 2. Fallback to main preview image tag src
        if not img_url:
            img_tag = soup.find("img", id="wallpaper") or soup.find("img", class_=re.compile(r"wallpaper", re.I))
            if img_tag and img_tag.get("src"):
                img_url = img_tag["src"]

        if not img_url:
            logger.warning(f"No image link found on {detail_url}")
            return None

        if img_url.startswith("/"):
            img_url = f"{BASE_URL}{img_url}"

        quality = "4K" if "4k" in title.lower() or "3840" in resp.text else "HD"

        return {
            "title": title,
            "source_page": detail_url,
            "img_url": img_url,
            "quality": quality,
        }

    def download_file(self, url: str, filename: str) -> Optional[Path]:
        file_path = self.output_dir / filename
        try:
            with self.session.get(url, stream=True, timeout=30) as r:
                r.raise_for_status()
                with open(file_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
            logger.info(f"Downloaded: {filename}")
            return file_path
        except Exception as e:
            logger.error(f"Failed to download {url}: {e}")
            if file_path.exists():
                file_path.unlink()
            return None

    def run(self) -> List[Dict]:
        metadata = []
        for page in range(1, MAX_PAGES + 1):
            detail_links = self.get_wallpaper_links(page)
            if not detail_links:
                continue

            for link in detail_links:
                time.sleep(DELAY_BETWEEN_REQ)
                detail = self.parse_wallpaper_detail(link)
                if not detail:
                    continue

                raw_filename = detail["img_url"].split("/")[-1].split("?")[0]
                clean_filename = re.sub(r"[^\w\-.]", "_", raw_filename)

                time.sleep(DELAY_BETWEEN_REQ)
                saved = self.download_file(detail["img_url"], clean_filename)
                if saved:
                    detail["local_file"] = clean_filename
                    metadata.append(detail)

        with open(METADATA_FILE, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

        return metadata


if __name__ == "__main__":
    scraper = WallpaperScraper()
    items = scraper.run()
    logger.info(f"Finished scraping. Total downloaded: {len(items)}")
