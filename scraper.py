import json
import requests
from bs4 import BeautifulSoup

# Base URL set to the main Alpha Coders portal
BASE_URL = "https://alphacoders.com/"

# Standard headers to prevent 403 Forbidden errors
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

def fetch_alpha_coders_links(base_url, total_pages=2):
    """Scrapes content links from the main Alpha Coders hub across specified pages."""
    item_urls = []

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

        # Select thumbnail containers used across Alpha Coders portals
        containers = soup.select(".thumb-container-big, .thumb-container, .item, .thumb")

        for container in containers:
            link_tag = container.find("a", href=True)
            img_tag = container.find("img")

            if link_tag and link_tag.get("href"):
                href = link_tag["href"]
                # Resolve protocol-relative and root-relative URLs
                if href.startswith("//"):
                    href = f"https:{href}"
                elif href.startswith("/"):
                    href = f"https://alphacoders.com{href}"
                
                item_urls.append(href)
            elif img_tag:
                img_src = img_tag.get("data-src") or img_tag.get("src")
                if img_src:
                    if img_src.startswith("//"):
                        img_src = f"https:{img_src}"
                    item_urls.append(img_src)

    # Deduplicate list while preserving order
    unique_links = list(dict.fromkeys(item_urls))
    return unique_links

def save_to_json(data, filename="links.json"):
    """Saves output links into a JSON file."""
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Done! Saved {len(data)} links to {filename}")

if __name__ == "__main__":
    links = fetch_alpha_coders_links(BASE_URL, total_pages=3)
    save_to_json(links, "links.json")
