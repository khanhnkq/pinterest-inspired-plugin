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


@mcp.tool()
def extract_color_palette(image_path_or_url: str, num_colors: int = 5) -> dict[str, Any]:
    """Extract dominant quantized color palette, relative luminance, and 60-30-10 semantic roles.

    Analyzes a local image file or Pinterest image URL using Pillow median-cut quantization.
    Calculates percentage share, WCAG relative luminance, contrast matrix against the canvas,
    and returns a ready-to-paste Tailwind CSS theme snippet.

    Args:
        image_path_or_url: Local file path or HTTP/HTTPS image URL.
        num_colors: Number of distinct colors to extract (3 to 10, default 5).

    Returns:
        Dict containing total colors extracted, canvas 60% color, surface 30% color,
        high-impact accent 10% color, palette list, contrast analysis, and Tailwind snippet.
    """
    try:
        from src.color_extractor import extract_color_palette as _extract
    except ImportError:
        from color_extractor import extract_color_palette as _extract  # type: ignore

    return _extract(image_path_or_url, num_colors=num_colors)


@mcp.tool()
def calculate_wcag_contrast(foreground_hex: str, background_hex: str) -> dict[str, Any]:
    """Calculate WCAG 2.1 contrast ratio and accessibility compliance between any two hex colors.

    Verifies whether a color combination meets WCAG AA (>= 4.5:1 for normal text, >= 3.0:1 for large text)
    and WCAG AAA (>= 7.0:1 for normal text, >= 4.5:1 for large text) standards.

    Args:
        foreground_hex: Hex code of text/foreground (e.g. '#F3F4F6' or '#FFFFFF').
        background_hex: Hex code of canvas/surface background (e.g. '#0B0D10').

    Returns:
        Dict with contrast ratio (e.g. '17.6:1'), compliance flags, and overall rating.
    """
    try:
        from src.color_extractor import calculate_contrast_ratio as _calc
    except ImportError:
        from color_extractor import calculate_contrast_ratio as _calc  # type: ignore

    return _calc(foreground_hex, background_hex)


@mcp.tool()
def extract_text_and_ocr(image_path_or_url: str) -> dict[str, Any]:
    """Extract text, numbers, metrics, navigation labels, and UI headers from an image via OCR.

    Analyzes reference pins using Tesseract OCR to extract exact stats, currencies,
    percentages (e.g. '$30,240', '129', '24%', '14d'), headings, and navigation labels
    so generated UI code faithfully mirrors the content of the reference image.

    Args:
        image_path_or_url: Local file path or HTTP/HTTPS image URL.

    Returns:
        Dict with raw text, cleaned lines, numerical metrics, detected headings, and navigation items.
    """
    try:
        from src.ocr_extractor import extract_text_and_ocr as _ocr
    except ImportError:
        from ocr_extractor import extract_text_and_ocr as _ocr  # type: ignore

    return _ocr(image_path_or_url)


@mcp.tool()
def detect_layout_regions(image_path_or_url: str) -> dict[str, Any]:
    """Detect structural UI regions from a reference design or screenshot.

    Calculates horizontal and vertical luminance projections to detect sidebars,
    top navigation headers, main content canvas bounding box, and estimated card grid columns.
    Enables AI agents to replicate layout geometry faithfully without guessing.

    Args:
        image_path_or_url: Absolute or relative local path, or HTTP/HTTPS image URL.

    Returns:
        Dict containing:
            - sidebar_detected: bool (True if distinct vertical boundary in left 4-35%)
            - sidebar_width_pct: float (e.g. 18.5)
            - sidebar_width_px: int
            - header_detected: bool (True if distinct horizontal boundary in top 3-25%)
            - header_height_px: int (e.g. 64)
            - header_height_pct: float
            - main_grid_bounding_box: [x, y, w, h] pixel coordinates of content canvas
            - estimated_card_columns: int (estimated grid columns: 1, 2, 3, or 4)
            - layout_type: str ("full_dashboard", "sidebar_and_grid", "header_and_grid", "grid_only", "single_column")
            - image_dimensions: {"width": int, "height": int}
            - recommendation: actionable design layout guidance
    """
    try:
        from src.layout_detector import detect_layout_regions as _detect
    except ImportError:
        from layout_detector import detect_layout_regions as _detect  # type: ignore

    return _detect(image_path_or_url)


@mcp.tool()
def compare_visual_diff(
    reference_image_path_or_url: str,
    rendered_screenshot_path: str,
    threshold: float = 80.0,
    output_diff_path: str = "",
) -> dict[str, Any]:
    """Compare a rendered UI screenshot against a reference pin design image for visual fidelity.

    Performs automated computer-vision visual difference evaluation between a reference design
    and a rendered implementation screenshot. Resizes to standard resolution, computes channel-by-channel
    pixel absolute differences, generates a diff heatmap, and checks against the pass threshold.

    Args:
        reference_image_path_or_url: Reference design pin image path or URL.
        rendered_screenshot_path: Rendered UI implementation screenshot path or URL.
        threshold: Minimum similarity percentage required to pass (0.0 to 100.0, default 80.0).
        output_diff_path: Optional custom path for saving the diff heatmap image.
            Defaults to `.pinterest_cache/diff_heatmap.png`.

    Returns:
        Dict containing:
            - similarity_score_pct: float (0.0 to 100.0)
            - threshold: float (e.g. 80.0)
            - passed: bool (True if similarity_score_pct >= threshold)
            - diff_image_path: str path to generated heatmap image
            - analysis: detailed breakdown of visual similarity and discrepancies
            - resolution_compared: [width, height]
            - mean_channel_diff: float average per-channel pixel difference
    """
    try:
        from src.visual_diff import compare_visual_diff as _compare
    except ImportError:
        from visual_diff import compare_visual_diff as _compare  # type: ignore

    return _compare(
        reference_image_path_or_url,
        rendered_screenshot_path,
        threshold=threshold,
        output_diff_path=output_diff_path,
    )


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
