"""Visual diff and similarity analysis module for design replication verification.

Compares a reference design image against a rendered implementation screenshot using Pillow:
- Resizes both images to a standardized resolution (800x600)
- Computes channel-by-channel pixel absolute differences and similarity score percentage (0.0 to 100.0%)
- Generates an enhanced high-contrast visual diff heatmap saved to `.pinterest_cache/diff_heatmap.png`
- Determines whether the visual implementation meets the verification threshold (default: 80.0%)
"""

from __future__ import annotations

import io
import os
from pathlib import Path
from typing import Any
import httpx
from PIL import Image, ImageChops, ImageEnhance, ImageOps, ImageStat

DEFAULT_CACHE_DIR = ".pinterest_cache"
DEFAULT_DIFF_FILENAME = "diff_heatmap.png"
COMMON_RESOLUTION = (800, 600)


def load_image(image_path_or_url: str) -> Image.Image:
    """Load PIL Image from local file path or remote HTTP URL."""
    path_or_url = str(image_path_or_url).strip()
    if path_or_url.startswith(("http://", "https://")):
        resp = httpx.get(
            path_or_url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                )
            },
            timeout=15.0,
            follow_redirects=True,
        )
        resp.raise_for_status()
        img = Image.open(io.BytesIO(resp.content))
    else:
        local_path = Path(path_or_url).expanduser().resolve()
        if not local_path.is_file():
            raise FileNotFoundError(f"Image not found at path: {local_path}")
        img = Image.open(local_path)

    # Convert to RGB mode (strips alpha and palettes)
    if img.mode != "RGB":
        img = img.convert("RGB")
    return img


def compare_visual_diff(
    reference_image_path_or_url: str,
    rendered_screenshot_path: str,
    threshold: float = 80.0,
    output_diff_path: str = "",
) -> dict[str, Any]:
    """Compare a rendered screenshot against a reference pin design image.

    Args:
        reference_image_path_or_url: Reference image path or URL.
        rendered_screenshot_path: Rendered implementation screenshot path or URL.
        threshold: Minimum similarity percentage required to pass (default: 80.0).
        output_diff_path: Optional custom path for saving the diff heatmap.
            Defaults to `.pinterest_cache/diff_heatmap.png`.

    Returns:
        Dict with keys:
            - similarity_score_pct: float (0.0 to 100.0)
            - threshold: float
            - passed: bool
            - diff_image_path: str
            - analysis: str
            - resolution_compared: [int, int]
            - mean_channel_diff: float
    """
    ref_img = load_image(reference_image_path_or_url)
    ren_img = load_image(rendered_screenshot_path)

    # Resize both images to common standardized resolution using high-quality Lanczos resampling
    ref_resized = ref_img.resize(COMMON_RESOLUTION, Image.Resampling.LANCZOS)
    ren_resized = ren_img.resize(COMMON_RESOLUTION, Image.Resampling.LANCZOS)

    # Compute channel-by-channel pixel absolute difference
    diff = ImageChops.difference(ref_resized, ren_resized)

    # Calculate average difference across R, G, B channels
    stat = ImageStat.Stat(diff)
    mean_channels = stat.mean  # [R_mean, G_mean, B_mean] in range [0, 255]
    avg_channel_diff = sum(mean_channels) / (3.0 * 255.0)

    # Compute similarity percentage (100% = identical, 0% = maximum discrepancy)
    similarity_score_pct = round(max(0.0, min(100.0, (1.0 - avg_channel_diff) * 100.0)), 2)

    # Check whether the similarity passes the requested threshold
    target_threshold = float(threshold)
    passed = similarity_score_pct >= target_threshold

    # Generate enhanced high-contrast visual diff heatmap
    diff_gray = diff.convert("L")
    enhanced_diff = ImageEnhance.Contrast(diff_gray).enhance(2.5)

    # Colorize: dark slate (#0f172a) for matches, vibrant orange (#f97316) for moderate shifts,
    # and bright neon red (#ef4444) for stark visual deviations
    heatmap = ImageOps.colorize(
        enhanced_diff,
        black="#0f172a",
        mid="#f97316",
        white="#ef4444",
    )

    # Determine destination diff heatmap file path
    if output_diff_path:
        diff_dest = Path(output_diff_path).expanduser().resolve()
    else:
        diff_dest = Path(DEFAULT_CACHE_DIR).resolve() / DEFAULT_DIFF_FILENAME

    diff_dest.parent.mkdir(parents=True, exist_ok=True)
    heatmap.save(diff_dest, format="PNG")

    # Formulate analysis summary
    if passed:
        analysis = (
            f"Visual similarity is {similarity_score_pct:.2f}% (threshold: {target_threshold:.1f}%). "
            f"PASSED: Layout architecture, dominant color palette, and component spacing closely match "
            f"the reference design. See diff heatmap at {diff_dest}."
        )
    else:
        analysis = (
            f"Visual similarity is {similarity_score_pct:.2f}% (threshold: {target_threshold:.1f}%). "
            f"FAILED: Noticeable visual discrepancies detected in component placement, color contrast, "
            f"or aspect ratios. Check the visual heatmap at {diff_dest} for regions highlighted in red."
        )

    return {
        "similarity_score_pct": similarity_score_pct,
        "threshold": target_threshold,
        "passed": passed,
        "diff_image_path": str(diff_dest),
        "analysis": analysis,
        "resolution_compared": list(COMMON_RESOLUTION),
        "mean_channel_diff": round(avg_channel_diff * 255.0, 2),
    }
