import json
import os
import re
import requests
from bs4 import BeautifulSoup

# Base URL for Alpha Coders Wallpapers
BASE_URL = "https://wall.alphacoders.com/"

# Request headers to mimic a browser request
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

def fetch_wallpaper_links(base_url, total_pages=2):
    """Scrapes wallpaper links from Alpha Coders across specified pages."""
    wallpaper_urls = []

    for page in range(1, total_pages + 1):
        target_url = f"{base_url}?page={page}" if page > 1 else base_url
        print(f"Fetching page {page}: {target_url}")

        try:
            response = requests.get(target_url, headers=HEADERS, timeout=15)
            response.raise_for_status()
        except requests.RequestException as err:
            print(f"Error fetching page {page}: {err}")
            continue

        soup = BeautifulSoup(response.text, "html.parser")

        # Find thumbnail containers on Alpha Coders
        containers = soup.select(".thumb-container-big, .thumb-container")

        for container in containers:
            # Locate individual wallpaper view link
            link_tag = container.find("a", href=re.compile(r"big\.php\?i="))
            img_tag = container.find("img")

            if link_tag and link_tag.get("href"):
                href = link_tag["href"]
                full_link = f"https://wall.alphacoders.com/{href}" if not href.startswith("http") else href
                wallpaper_urls.append(full_link)
            elif img_tag and (img_tag.get("src") or img_tag.get("data-src")):
                img_src = img_tag.get("data-src") or img_tag.get("src")
                wallpaper_urls.append(img_src)

    # Remove duplicates while maintaining order
    unique_links = list(dict.fromkeys(wallpaper_urls))
    return unique_links

def save_to_json(data, filename="links.json"):
    """Saves output links to JSON file."""
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Done! Saved {len(data)} links to {filename}")

if __name__ == "__main__":
    # Adjust total_pages as needed
    links = fetch_wallpaper_links(BASE_URL, total_pages=3)
    save_to_json(links, "links.json")
