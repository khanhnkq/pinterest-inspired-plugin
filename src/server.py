"""Pinterest Inspiration FastMCP Server.

Exposes tools for searching visual design inspiration from Pinterest and
downloading reference images to local storage for AI agents (Antigravity,
Claude Code, OpenAI Codex, Cursor/Windsurf).
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any, List, Optional

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    # Fallback for alternative MCP SDK packaging
    try:
        from mcp.server.mcpserver import MCPServer as FastMCP  # type: ignore
    except ImportError as err:
        raise ImportError(
            "Could not import FastMCP from mcp.server.fastmcp or MCPServer from mcp.server.mcpserver. "
            "Please ensure mcp is installed via `uv sync`."
        ) from err

# Configure logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("pinterest-inspiration-mcp")

# Read host, port and transport configuration from environment
MCP_HOST = os.getenv("MCP_HOST", "0.0.0.0")
MCP_PORT = int(os.getenv("MCP_PORT", "8000"))

# Initialize FastMCP Server
mcp = FastMCP("pinterest-inspiration", host=MCP_HOST, port=MCP_PORT)


def _get_scraper_module():
    """Lazily import the scraper module with graceful fallback."""
    try:
        from src import pinterest_scraper
        return pinterest_scraper
    except ImportError:
        try:
            import pinterest_scraper  # type: ignore
            return pinterest_scraper
        except ImportError:
            logger.warning("pinterest_scraper module not available yet.")
            return None


@mcp.tool()
def search_pinterest_inspiration(query: str, limit: int = 8) -> List[dict[str, Any]]:
    """Search Pinterest for visual inspiration images, dominant colors, and dimensions.

    Scrapes Pinterest's mobile SSR state without requiring an API key or browser binary.
    Extracts high-resolution original image URLs, 736x preview URLs, dominant color hex
    codes, and aspect ratios. Useful for UI styling (Tailwind/CSS), moodboards, and AI image prompts.

    Args:
        query: Search keywords or visual theme (e.g. 'minimalist bento grid dashboard',
            'cyberpunk brutalist typography', 'warm editorial magazine layout').
        limit: Number of visual inspirations to retrieve (1 to 10, default 8).

    Returns:
        A list of pin objects, each containing:
            - id: Unique Pinterest pin identifier.
            - dominant_color: Primary hex color code (e.g. '#2b3a4a').
            - aspect_ratio: Float ratio of width / height (e.g. 1.5).
            - image_url: Full high-resolution original image URL.
            - preview_url: 736px optimized preview image URL.
            - width: Original image width in pixels.
            - height: Original image height in pixels.
            - query: Search query used.
    """
    clean_query = (query or "").strip()
    if not clean_query:
        raise ValueError("Search query cannot be empty.")

    clamped_limit = max(1, min(int(limit), 10))
    scraper = _get_scraper_module()

    if scraper is not None:
        search_fn = (
            getattr(scraper, "search_pinterest_inspiration", None)
            or getattr(scraper, "scrape_pinterest_inspiration", None)
            or getattr(scraper, "search_pinterest", None)
        )
        if callable(search_fn):
            return search_fn(clean_query, limit=clamped_limit)

    raise RuntimeError(
        "Pinterest scraper engine is currently unavailable. "
        "Please ensure `src.pinterest_scraper` is implemented and functional."
    )


@mcp.tool()
def download_pin_image(image_url: str, output_path: str = "") -> str:
    """Download a Pinterest inspiration image to local workspace disk.

    Saves the image to a specified directory/file path or default `.pinterest_cache/`
    so AI agents can inspect it with vision models or save as project assets.

    Args:
        image_url: Direct URL of the image to download (from search_pinterest_inspiration).
        output_path: Optional custom file or directory path. Defaults to saving in
            `.pinterest_cache/<filename>` in the current workspace.

    Returns:
        The absolute local file path where the downloaded image is saved.
    """
    clean_url = (image_url or "").strip()
    if not clean_url or not clean_url.startswith(("http://", "https://")):
        raise ValueError(f"Invalid image URL: '{image_url}'")

    scraper = _get_scraper_module()

    if scraper is not None:
        download_fn = (
            getattr(scraper, "download_pin_image", None)
            or getattr(scraper, "download_image", None)
        )
        if callable(download_fn):
            return download_fn(clean_url, output_path=output_path)

    # Fallback built-in downloader if scraper module is missing
    import hashlib
    import os
    import urllib.parse
    from pathlib import Path
    import httpx

    parsed = urllib.parse.urlparse(clean_url)
    basename = os.path.basename(parsed.path)
    ext = os.path.splitext(basename)[1].lower()
    if ext not in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
        ext = ".jpg"

    safe_stem = hashlib.sha256(clean_url.encode()).hexdigest()[:16]
    filename = f"{safe_stem}{ext}"

    if not output_path:
        target_dir = Path(".pinterest_cache").resolve()
        target_file = target_dir / filename
    else:
        raw = Path(output_path).resolve()
        if output_path.endswith(("/", "\\")) or (raw.exists() and raw.is_dir()):
            target_dir = raw
            target_file = target_dir / filename
        else:
            target_dir = raw.parent
            target_file = raw

    target_dir.mkdir(parents=True, exist_ok=True)
    if target_file.exists() and target_file.stat().st_size > 0:
        return str(target_file)

    with httpx.Client(follow_redirects=True, timeout=15.0) as client:
        resp = client.get(clean_url)
        resp.raise_for_status()
        target_file.write_bytes(resp.content)

    return str(target_file)


def main() -> None:
    """Run FastMCP server on configured transport (stdio or sse / streamable-http)."""
    transport = os.getenv("MCP_TRANSPORT", "stdio").lower().strip()
    if transport in ("sse", "streamable-http"):
        logger.info(f"Starting FastMCP server with transport={transport} on {MCP_HOST}:{MCP_PORT}")
        mcp.run(transport=transport)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
