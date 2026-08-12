import os
import json
import mimetypes
import logging
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ReleaseGenerator")

DOWNLOAD_DIR = Path("downloads")
SCRAPED_METADATA = Path("scraped_metadata.json")
OUTPUT_JSON = Path("wall.json")

def format_bytes(size: int) -> str:
    """Formats bytes into human-readable string."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} TB"

def generate_wall_json():
    if not SCRAPED_METADATA.exists():
        logger.error(f"Metadata file {SCRAPED_METADATA} not found!")
        raise FileNotFoundError(f"{SCRAPED_METADATA} does not exist.")

    with open(SCRAPED_METADATA, "r", encoding="utf-8") as f:
        scraped_items = json.load(f)

    repo_slug = os.getenv("GITHUB_REPOSITORY", "user/repo")
    tag_name = os.getenv("RELEASE_TAG", f"v{datetime.now(timezone.utc).strftime('%Y.%m.%d-%H%M')}")
    created_at = datetime.now(timezone.utc).isoformat()

    wallpapers = []
    
    for item in scraped_items:
        file_name = item.get("local_file")
        file_path = DOWNLOAD_DIR / file_name

        if not file_path.exists():
            logger.warning(f"File {file_name} missing from disk, skipping metadata inclusion.")
            continue

        file_bytes = file_path.stat().st_size
        mime_type, _ = mimetypes.guess_type(file_path)
        file_ext = file_path.suffix.lstrip(".").lower()

        # Build GitHub Release Asset URL structure
        asset_url = f"https://github.com/{repo_slug}/releases/download/{tag_name}/{file_name}"

        wallpapers.append({
            "name": file_name,
            "title": item.get("title", "4K Nature Wallpaper"),
            "quality": item.get("quality", "4K"),
            "file_type": mime_type or f"image/{file_ext}",
            "file_extension": file_ext,
            "file_size_bytes": file_bytes,
            "file_size_formatted": format_bytes(file_bytes),
            "source_url": item.get("source_page"),
            "asset_download_url": asset_url
        })

    payload = {
        "release": {
            "tag_name": tag_name,
            "repository": repo_slug,
            "created_at": created_at,
            "total_images": len(wallpapers),
            "wall_json_asset_url": f"https://github.com/{repo_slug}/releases/download/{tag_name}/wall.json"
        },
        "wallpapers": wallpapers
    }

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    logger.info(f"Successfully generated {OUTPUT_JSON} with {len(wallpapers)} wallpaper assets.")

if __name__ == "__main__":
    generate_wall_json()
