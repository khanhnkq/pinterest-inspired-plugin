"""Pinterest Mobile SSR Scraper Engine.

Extracts visual inspiration (high-resolution image URLs, preview URLs,
dominant color hex, dimensions, and aspect ratio) by scraping Pinterest's
server-side rendered mobile state (<script id="__PWS_INITIAL_PROPS__">)
without requiring browser binaries or API tokens.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
import urllib.parse
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

# Default Mobile User-Agent (iPhone Safari) triggers Pinterest SSR payload
MOBILE_USER_AGENT = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)

DEFAULT_CACHE_DIR = ".pinterest_cache"
DEFAULT_TIMEOUT = 15.0
CACHE_TTL_SECONDS = 900  # 15 minutes


class PinterestScraperError(Exception):
    """Base exception for Pinterest scraper errors."""
    pass


class PinterestRateLimitError(PinterestScraperError):
    """Raised when Pinterest returns HTTP 429 or 403 rate limit / block."""
    pass


@dataclass
class PinInspiration:
    """Visual design reference extracted from Pinterest."""

    id: str
    dominant_color: str
    aspect_ratio: float
    image_url: str
    preview_url: str
    width: int
    height: int
    query: str = ""
    title: str = ""
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return asdict(self)


class QueryCache:
    """Thread-safe in-memory cache with TTL for query results."""

    def __init__(self, ttl_seconds: float = CACHE_TTL_SECONDS) -> None:
        self.ttl_seconds = ttl_seconds
        self._store: dict[str, tuple[float, list[dict[str, Any]]]] = {}

    def get(self, key: str) -> Optional[list[dict[str, Any]]]:
        if key in self._store:
            timestamp, data = self._store[key]
            if time.time() - timestamp < self.ttl_seconds:
                return [dict(item) for item in data]
            del self._store[key]
        return None

    def set(self, key: str, value: list[dict[str, Any]]) -> None:
        self._store[key] = (time.time(), [dict(item) for item in value])

    def clear(self) -> None:
        self._store.clear()


# Global query cache instance
_query_cache = QueryCache()


def _sanitize_color(color_raw: Optional[str]) -> str:
    """Normalize dominant color string into a valid #RRGGBB hex."""
    if not color_raw:
        return "#000000"
    color = str(color_raw).strip()
    if not color.startswith("#"):
        color = f"#{color}"
    if re.fullmatch(r"#[0-9a-fA-F]{6}", color) or re.fullmatch(r"#[0-9a-fA-F]{3}", color):
        return color.lower()
    return "#000000"


def _extract_pin_data(raw_pin: dict[str, Any], query: str = "") -> Optional[PinInspiration]:
    """Parse a single raw pin dictionary into a PinInspiration object."""
    if not isinstance(raw_pin, dict):
        return None

    pin_id = str(raw_pin.get("id") or raw_pin.get("node_id") or "")
    if not pin_id:
        return None

    images = raw_pin.get("images", {})
    if not isinstance(images, dict) or not images:
        return None

    # Retrieve images in order of preference
    orig = images.get("orig") or {}
    p736 = images.get("736x") or {}
    p474 = images.get("474x") or {}
    p236 = images.get("236x") or {}

    image_url = (
        orig.get("url")
        or p736.get("url")
        or p474.get("url")
        or p236.get("url")
        or ""
    )
    if not image_url:
        return None

    preview_url = (
        p736.get("url")
        or p474.get("url")
        or p236.get("url")
        or image_url
    )

    width = orig.get("width") or p736.get("width") or p474.get("width") or 0
    height = orig.get("height") or p736.get("height") or p474.get("height") or 0

    try:
        width = int(width)
        height = int(height)
    except (ValueError, TypeError):
        width = 0
        height = 0

    aspect_ratio = round(width / height, 2) if (width > 0 and height > 0) else 1.0
    dominant_color = _sanitize_color(raw_pin.get("dominant_color"))

    title = str(raw_pin.get("title") or raw_pin.get("grid_title") or "").strip()
    description = str(raw_pin.get("description") or "").strip()

    return PinInspiration(
        id=pin_id,
        dominant_color=dominant_color,
        aspect_ratio=aspect_ratio,
        image_url=image_url,
        preview_url=preview_url,
        width=width,
        height=height,
        query=query,
        title=title,
        description=description,
    )


def extract_pins_from_html(html: str, query: str = "", limit: int = 10) -> list[dict[str, Any]]:
    """Extract pins from Pinterest Mobile SSR HTML.

    Args:
        html: Raw HTML string from Pinterest search page.
        query: Search query string for context tracking.
        limit: Max number of pins to extract (capped at 10).

    Returns:
        List of pin inspiration dictionaries.
    """
    if not html or not isinstance(html, str):
        return []

    limit = max(1, min(limit, 10))

    # Match __PWS_INITIAL_PROPS__, with fallback to __PWS_DATA__ or any __PWS_ script
    script_patterns = [
        r"<script\s+id=[\"']__PWS_INITIAL_PROPS__[\"'][^>]*>(.*?)</script>",
        r"<script\s+id=[\"']__PWS_DATA__[\"'][^>]*>(.*?)</script>",
        r"<script\s+id=[\"'](__PWS_[^\"']+)[\"'][^>]*>(.*?)</script>",
    ]

    json_str: Optional[str] = None
    for pattern in script_patterns:
        match = re.search(pattern, html, re.DOTALL)
        if match:
            # If pattern has 2 capture groups (3rd pattern), get the second group
            json_str = match.group(2) if match.lastindex == 2 else match.group(1)
            if json_str:
                break

    if not json_str:
        logger.warning("No Pinterest SSR data script tag found in HTML response.")
        return []

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as exc:
        logger.warning(f"Failed to decode Pinterest SSR JSON: {exc}")
        return []

    redux_state = data.get("initialReduxState") if isinstance(data, dict) else {}
    if not isinstance(redux_state, dict):
        redux_state = {}

    pins_list: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    # Strategy 1: Extract from BaseSearchResource in resources
    resources = redux_state.get("resources", {})
    if isinstance(resources, dict):
        base_search = resources.get("BaseSearchResource", {})
        if isinstance(base_search, dict):
            for entry in base_search.values():
                if isinstance(entry, dict):
                    entry_data = entry.get("data", {})
                    if isinstance(entry_data, dict):
                        results = entry_data.get("results", [])
                        if isinstance(results, list):
                            for item in results:
                                if isinstance(item, dict):
                                    pin = _extract_pin_data(item, query=query)
                                    if pin and pin.id not in seen_ids:
                                        seen_ids.add(pin.id)
                                        pins_list.append(pin.to_dict())
                                        if len(pins_list) >= limit:
                                            return pins_list

    # Strategy 2: Extract from initialReduxState.pins
    redux_pins = redux_state.get("pins", {})
    if isinstance(redux_pins, dict):
        for raw_pin in redux_pins.values():
            if isinstance(raw_pin, dict):
                pin = _extract_pin_data(raw_pin, query=query)
                if pin and pin.id not in seen_ids:
                    seen_ids.add(pin.id)
                    pins_list.append(pin.to_dict())
                    if len(pins_list) >= limit:
                        return pins_list

    # Strategy 3: Deep search in JSON data if neither returned pins
    if not pins_list:
        pins_list = _deep_search_pins(data, query=query, limit=limit)

    return pins_list[:limit]


def _deep_search_pins(obj: Any, query: str = "", limit: int = 10) -> list[dict[str, Any]]:
    """Traverse arbitrary JSON to locate pin-like objects with images and colors."""
    found: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    def _traverse(node: Any) -> None:
        if len(found) >= limit:
            return
        if isinstance(node, dict):
            if "images" in node and isinstance(node["images"], dict):
                pin = _extract_pin_data(node, query=query)
                if pin and pin.id not in seen_ids:
                    seen_ids.add(pin.id)
                    found.append(pin.to_dict())
                    if len(found) >= limit:
                        return
            for val in node.values():
                _traverse(val)
        elif isinstance(node, list):
            for item in node:
                _traverse(item)

    _traverse(obj)
    return found


def _build_search_url(query: str) -> str:
    """Encode query and format Pinterest search URL."""
    clean_query = query.strip()
    encoded_query = urllib.parse.quote(clean_query)
    return f"https://www.pinterest.com/search/pins/?q={encoded_query}"


def _get_headers() -> dict[str, str]:
    """Default HTTP headers mimicking mobile Safari."""
    return {
        "User-Agent": MOBILE_USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
    }


def search_pinterest_inspiration(
    query: str,
    limit: int = 8,
    use_cache: bool = True,
    timeout: float = DEFAULT_TIMEOUT,
) -> list[dict[str, Any]]:
    """Fetch visual inspiration pins from Pinterest Mobile SSR.

    Args:
        query: Search keywords (e.g. 'minimalist modern architecture', 'bento grid ui').
        limit: Number of pins to retrieve (1-10, default 8).
        use_cache: Whether to check and store results in in-memory cache.
        timeout: Network request timeout in seconds.

    Returns:
        List of dicts containing id, dominant_color, aspect_ratio, image_url, preview_url, width, height.

    Raises:
        ValueError: If query is empty or whitespace.
        PinterestRateLimitError: If Pinterest returns HTTP 429 or 403.
        PinterestScraperError: For other network or scraping failures.
    """
    clean_query = (query or "").strip()
    if not clean_query:
        raise ValueError("Search query cannot be empty.")

    clamped_limit = max(1, min(limit, 10))
    cache_key = f"{clean_query.lower()}:{clamped_limit}"

    if use_cache:
        cached = _query_cache.get(cache_key)
        if cached is not None:
            logger.debug(f"Cache hit for query: '{clean_query}'")
            return cached

    url = _build_search_url(clean_query)
    headers = _get_headers()

    try:
        with httpx.Client(headers=headers, follow_redirects=True, timeout=timeout) as client:
            response = client.get(url)

            if response.status_code in (403, 429):
                raise PinterestRateLimitError(
                    f"Pinterest returned HTTP {response.status_code}. "
                    "Rate limit reached or access temporarily blocked. Please wait a moment."
                )

            response.raise_for_status()
            html_text = response.text

    except httpx.HTTPStatusError as exc:
        raise PinterestScraperError(f"HTTP error fetching Pinterest: {exc.response.status_code}") from exc
    except httpx.RequestError as exc:
        raise PinterestScraperError(f"Network error connecting to Pinterest: {exc}") from exc

    pins = extract_pins_from_html(html_text, query=clean_query, limit=clamped_limit)

    if use_cache and pins:
        _query_cache.set(cache_key, pins)

    return pins


# Alias for backward/forward compatibility
scrape_pinterest_inspiration = search_pinterest_inspiration


async def async_search_pinterest_inspiration(
    query: str,
    limit: int = 8,
    use_cache: bool = True,
    timeout: float = DEFAULT_TIMEOUT,
) -> list[dict[str, Any]]:
    """Asynchronous version of search_pinterest_inspiration."""
    clean_query = (query or "").strip()
    if not clean_query:
        raise ValueError("Search query cannot be empty.")

    clamped_limit = max(1, min(limit, 10))
    cache_key = f"{clean_query.lower()}:{clamped_limit}"

    if use_cache:
        cached = _query_cache.get(cache_key)
        if cached is not None:
            return cached

    url = _build_search_url(clean_query)
    headers = _get_headers()

    try:
        async with httpx.AsyncClient(headers=headers, follow_redirects=True, timeout=timeout) as client:
            response = await client.get(url)

            if response.status_code in (403, 429):
                raise PinterestRateLimitError(
                    f"Pinterest returned HTTP {response.status_code}. Rate limit reached or access blocked."
                )

            response.raise_for_status()
            html_text = response.text

    except httpx.HTTPStatusError as exc:
        raise PinterestScraperError(f"HTTP error fetching Pinterest: {exc.response.status_code}") from exc
    except httpx.RequestError as exc:
        raise PinterestScraperError(f"Network error connecting to Pinterest: {exc}") from exc

    pins = extract_pins_from_html(html_text, query=clean_query, limit=clamped_limit)

    if use_cache and pins:
        _query_cache.set(cache_key, pins)

    return pins


def _sanitize_filename(url: str) -> str:
    """Generate a safe, unique filename based on image URL."""
    parsed = urllib.parse.urlparse(url)
    basename = os.path.basename(parsed.path)

    # Determine extension
    ext = os.path.splitext(basename)[1].lower()
    if ext not in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
        ext = ".jpg"

    # Clean name or generate SHA-256 hash prefix
    stem = os.path.splitext(basename)[0]
    safe_stem = re.sub(r"[^a-zA-Z0-9_-]", "", stem)
    if not safe_stem:
        safe_stem = hashlib.sha256(url.encode()).hexdigest()[:16]

    return f"{safe_stem}{ext}"


def download_pin_image(
    image_url: str,
    output_path: str = "",
    timeout: float = DEFAULT_TIMEOUT,
) -> str:
    """Download a pin image to local disk.

    Args:
        image_url: Direct URL of the image to download.
        output_path: Optional destination directory or file path.
            Defaults to saving under `.pinterest_cache/` in the working directory.
        timeout: Network request timeout in seconds.

    Returns:
        Absolute string path to the saved local image file.

    Raises:
        ValueError: If image_url is empty, invalid, or path traversal is detected.
        PinterestScraperError: If downloading fails or server returns non-200.
    """
    clean_url = (image_url or "").strip()
    if not clean_url or not clean_url.startswith(("http://", "https://")):
        raise ValueError(f"Invalid image URL: '{image_url}'")

    filename = _sanitize_filename(clean_url)

    # Determine destination directory and file path safely
    if not output_path:
        target_dir = Path(DEFAULT_CACHE_DIR).resolve()
        target_file = target_dir / filename
    else:
        raw_target = Path(output_path).resolve()
        # If output_path is an existing directory, ends with slash, or has no file extension
        is_dir = (
            output_path.endswith(("/", "\\"))
            or (raw_target.exists() and raw_target.is_dir())
            or not raw_target.suffix
        )
        if is_dir:
            target_dir = raw_target
            target_file = target_dir / filename
        else:
            target_dir = raw_target.parent
            target_file = raw_target

    # Create destination directory
    target_dir.mkdir(parents=True, exist_ok=True)

    # Check if file already exists with content
    if target_file.exists() and target_file.stat().st_size > 0:
        return str(target_file)

    headers = {
        "User-Agent": MOBILE_USER_AGENT,
        "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
        "Referer": "https://www.pinterest.com/",
    }

    try:
        with httpx.Client(headers=headers, follow_redirects=True, timeout=timeout) as client:
            response = client.get(clean_url)

            if response.status_code != 200:
                raise PinterestScraperError(
                    f"Failed to download image (HTTP {response.status_code}): {clean_url}"
                )

            content_type = response.headers.get("content-type", "")
            if not (content_type.startswith("image/") or "octet-stream" in content_type):
                logger.warning(f"Unexpected content-type '{content_type}' for image URL: {clean_url}")

            image_bytes = response.content
            if not image_bytes:
                raise PinterestScraperError(f"Downloaded empty image payload from: {clean_url}")

            # Write file atomically via temp file
            temp_file = target_file.with_suffix(f"{target_file.suffix}.tmp")
            temp_file.write_bytes(image_bytes)
            temp_file.replace(target_file)

    except httpx.HTTPError as exc:
        raise PinterestScraperError(f"Network error downloading image {clean_url}: {exc}") from exc

    return str(target_file)


async def async_download_pin_image(
    image_url: str,
    output_path: str = "",
    timeout: float = DEFAULT_TIMEOUT,
) -> str:
    """Asynchronous version of download_pin_image."""
    clean_url = (image_url or "").strip()
    if not clean_url or not clean_url.startswith(("http://", "https://")):
        raise ValueError(f"Invalid image URL: '{image_url}'")

    filename = _sanitize_filename(clean_url)

    if not output_path:
        target_dir = Path(DEFAULT_CACHE_DIR).resolve()
        target_file = target_dir / filename
    else:
        raw_target = Path(output_path).resolve()
        is_dir = (
            output_path.endswith(("/", "\\"))
            or (raw_target.exists() and raw_target.is_dir())
            or not raw_target.suffix
        )
        if is_dir:
            target_dir = raw_target
            target_file = target_dir / filename
        else:
            target_dir = raw_target.parent
            target_file = raw_target

    target_dir.mkdir(parents=True, exist_ok=True)

    if target_file.exists() and target_file.stat().st_size > 0:
        return str(target_file)

    headers = {
        "User-Agent": MOBILE_USER_AGENT,
        "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
        "Referer": "https://www.pinterest.com/",
    }

    try:
        async with httpx.AsyncClient(headers=headers, follow_redirects=True, timeout=timeout) as client:
            response = await client.get(clean_url)

            if response.status_code != 200:
                raise PinterestScraperError(
                    f"Failed to download image (HTTP {response.status_code}): {clean_url}"
                )

            image_bytes = response.content
            if not image_bytes:
                raise PinterestScraperError(f"Downloaded empty image payload from: {clean_url}")

            temp_file = target_file.with_suffix(f"{target_file.suffix}.tmp")
            temp_file.write_bytes(image_bytes)
            temp_file.replace(target_file)

    except httpx.HTTPError as exc:
        raise PinterestScraperError(f"Network error downloading image {clean_url}: {exc}") from exc

    return str(target_file)


def clear_query_cache() -> None:
    """Clear all entries in the search query cache."""
    _query_cache.clear()
