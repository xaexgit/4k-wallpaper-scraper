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

# Configure logging
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

# Configurable scraper options
MAX_PAGES = 3            # Adjust page depth as needed
DELAY_BETWEEN_REQ = 1.5  # Rate limit delay in seconds


class WallpaperScraper:
    def __init__(self, output_dir: Path = DOWNLOAD_DIR):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.session = self._init_session()

    def _init_session(self) -> requests.Session:
        """Initializes a resilient HTTP session with retry strategies."""
        session = requests.Session()
        retry_strategy = Retry(
            total=4,
            backoff_factor=2,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        })
        return session

    def get_wallpaper_links(self, page_num: int) -> List[str]:
        """Scrapes item detail page URLs from category listing."""
        url = CATEGORY_URL if page_num == 1 else f"{CATEGORY_URL}?page={page_num}"
        logger.info(f"Fetching listing page {page_num}: {url}")

        try:
            resp = self.session.get(url, timeout=15)
            resp.raise_for_status()
        except requests.RequestException as e:
            logger.error(f"Failed to fetch listing page {page_num}: {e}")
            return []

        soup = BeautifulSoup(resp.text, "lxml")
        links = []
        
        # 4kwallpapers container links
        for a_tag in soup.select("#list_wallpapers .wallpapers__item a[href]"):
            href = a_tag["href"]
            if href.startswith("/"):
                href = f"{BASE_URL}{href}"
            if href not in links:
                links.append(href)

        logger.info(f"Found {len(links)} wallpaper links on page {page_num}.")
        return links

    def parse_wallpaper_detail(self, detail_url: str) -> Optional[Dict]:
        """Parses individual detail page to extract high-res image source and title."""
        logger.info(f"Parsing detail page: {detail_url}")
        try:
            resp = self.session.get(detail_url, timeout=15)
            resp.raise_for_status()
        except requests.RequestException as e:
            logger.error(f"Failed to fetch detail page {detail_url}: {e}")
            return None

        soup = BeautifulSoup(resp.text, "lxml")

        # High-res image download button/link
        download_btn = (
            soup.select_one("a#download") or 
            soup.select_one("a[download]") or 
            soup.select_one("a.download")
        )
        
        img_url = None
        if download_btn and download_btn.get("href"):
            img_url = download_btn["href"]
        else:
            # Fallback to main preview image tag
            img_tag = soup.select_one("#wallpaper")
            if img_tag and img_tag.get("src"):
                img_url = img_tag["src"]

        if not img_url:
            logger.warning(f"Could not find download URL on {detail_url}")
            return None

        if img_url.startswith("/"):
            img_url = f"{BASE_URL}{img_url}"

        # Extract title & quality tag
        title_el = soup.find("h1")
        title = title_el.text.strip() if title_el else "Wallpaper"
        
        quality = "4K" if "4k" in title.lower() or "3840" in resp.text else "HD"

        return {
            "title": title,
            "source_page": detail_url,
            "img_url": img_url,
            "quality": quality,
        }

    def download_file(self, url: str, filename: str) -> Optional[Path]:
        """Downloads image binary stream cleanly to disk."""
        file_path = self.output_dir / filename
        if file_path.exists():
            logger.info(f"File already exists: {filename}")
            return file_path

        try:
            with self.session.get(url, stream=True, timeout=30) as r:
                r.raise_for_status()
                with open(file_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
            logger.info(f"Successfully downloaded: {filename}")
            return file_path
        except Exception as e:
            logger.error(f"Failed downloading {url}: {e}")
            if file_path.exists():
                file_path.unlink()
            return None

    def run(self) -> List[Dict]:
        metadata = []
        for page in range(1, MAX_PAGES + 1):
            detail_links = self.get_wallpaper_links(page)
            if not detail_links:
                break

            for link in detail_links:
                time.sleep(DELAY_BETWEEN_REQ)
                detail = self.parse_wallpaper_detail(link)
                if not detail:
                    continue

                # Generate clean filename
                raw_filename = detail["img_url"].split("/")[-1].split("?")[0]
                clean_filename = re.sub(r"[^\w\-.]", "_", raw_filename)

                time.sleep(DELAY_BETWEEN_REQ)
                saved_path = self.download_file(detail["img_url"], clean_filename)

                if saved_path:
                    detail["local_file"] = clean_filename
                    metadata.append(detail)

        # Save raw extraction metadata
        with open(METADATA_FILE, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

        return metadata


if __name__ == "__main__":
    scraper = WallpaperScraper()
    scraped_items = scraper.run()
    logger.info(f"Scraping finished. Downloaded {len(scraped_items)} wallpapers.")
