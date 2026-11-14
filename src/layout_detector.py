"""Layout detection module for UI references and screenshots.

Analyzes image luminance projections (horizontal & vertical) to automatically detect:
- Sidebar presence and width percentage
- Top header/navbar presence and height in pixels
- Main content grid bounding box [x, y, w, h]
- Estimated card columns in the grid (e.g. 1, 2, 3, 4)
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any
import httpx
from PIL import Image


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


def _detect_sidebar(
    gray_img: Image.Image,
    width: int,
    height: int,
) -> tuple[bool, int, float]:
    """Detect vertical sidebar boundary in the left 4% - 35% region of the image."""
    if width < 200 or height < 100:
        return False, 0, 0.0

    step_y = max(1, height // 150)
    samples_y = max(1, len(range(0, height, step_y)))

    # Compute column-wise average luminance across image
    col_lum: list[float] = []
    for x in range(width):
        s = sum(gray_img.getpixel((x, y)) for y in range(0, height, step_y))
        col_lum.append(s / samples_y)

    min_x = max(5, int(width * 0.04))
    max_x = int(width * 0.35)

    best_split_x = 0
    max_contrast_diff = 0.0

    for x in range(min_x, max_x):
        window = min(15, x - min_x + 1, max_x - x)
        if window < 3:
            continue
        left_vals = col_lum[x - window : x]
        right_vals = col_lum[x : x + window]
        l_mean = sum(left_vals) / len(left_vals)
        r_mean = sum(right_vals) / len(right_vals)
        diff = abs(r_mean - l_mean)

        if diff > max_contrast_diff:
            max_contrast_diff = diff
            best_split_x = x

    # Threshold for a distinct sidebar boundary
    if max_contrast_diff >= 4.0 and best_split_x > 0:
        pct = round((best_split_x / width) * 100.0, 1)
        return True, best_split_x, pct

    return False, 0, 0.0


def _detect_header(
    gray_img: Image.Image,
    width: int,
    height: int,
    sidebar_x: int = 0,
) -> tuple[bool, int, float]:
    """Detect top header/navbar boundary in the top 3% - 25% region of the image."""
    if height < 150 or width < 150:
        return False, 0, 0.0

    step_x = max(1, width // 150)
    samples_x = max(1, len(range(0, width, step_x)))

    # Compute row-wise average luminance across image
    row_lum: list[float] = []
    for y in range(height):
        s = sum(gray_img.getpixel((x, y)) for x in range(0, width, step_x))
        row_lum.append(s / samples_x)

    min_y = max(4, int(height * 0.03))
    max_y = int(height * 0.25)

    best_split_y = 0
    max_contrast_diff = 0.0

    for y in range(min_y, max_y):
        window = min(12, y - min_y + 1, max_y - y)
        if window < 3:
            continue
        top_vals = row_lum[y - window : y]
        bottom_vals = row_lum[y : y + window]
        t_mean = sum(top_vals) / len(top_vals)
        b_mean = sum(bottom_vals) / len(bottom_vals)
        diff = abs(b_mean - t_mean)

        if diff > max_contrast_diff:
            max_contrast_diff = diff
            best_split_y = y

    # Threshold for a distinct header boundary
    if max_contrast_diff >= 4.0 and best_split_y > 0:
        pct = round((best_split_y / height) * 100.0, 1)
        return True, best_split_y, pct

    return False, 0, 0.0


def _estimate_card_columns(
    gray_img: Image.Image,
    gx: int,
    gy: int,
    gw: int,
    gh: int,
) -> int:
    """Estimate the number of card columns (1, 2, 3, or 4) inside the main grid bounding box."""
    if gw < 300 or gh < 150:
        return 1

    step_y = max(1, gh // 60)
    samples_y = max(1, len(range(gy, gy + gh, step_y)))

    col_lum: list[float] = []
    for x in range(gx, gx + gw):
        val = sum(gray_img.getpixel((x, y)) for y in range(gy, gy + gh, step_y)) / samples_y
        col_lum.append(val)

    mean_lum = sum(col_lum) / len(col_lum)
    variance = sum((c - mean_lum) ** 2 for c in col_lum) / len(col_lum)

    # Flat or uniform surface has no card columns
    if variance < 3.0:
        return 1

    # First derivative (edge transitions between cards/gutters)
    diffs = [abs(col_lum[i] - col_lum[i - 1]) for i in range(1, len(col_lum))]
    if not diffs:
        return 1

    max_edge = max(diffs)
    gutter_threshold = max(2.0, max_edge * 0.35)
    window = max(5, int(gw * 0.04))

    # Evaluate candidate column counts (4, 3, 2)
    # Check if all expected internal gutter positions have a corresponding edge peak
    for k in [4, 3, 2]:
        all_gutters_found = True
        for i in range(1, k):
            expected_x = int(gw * (i / k))
            local_region = diffs[max(0, expected_x - window) : min(len(diffs), expected_x + window)]
            if not local_region or max(local_region) < gutter_threshold:
                all_gutters_found = False
                break
        if all_gutters_found:
            return k

    # If no periodic gutters detected but width is wide, check general aspect ratio
    if gw >= 900 and variance > 10.0:
        return 3
    elif gw >= 550 and variance > 8.0:
        return 2

    return 1


def detect_layout_regions(image_path_or_url: str) -> dict[str, Any]:
    """Detect structural UI regions from a reference design or screenshot.

    Calculates horizontal and vertical luminance projections to detect sidebars,
    top navigation headers, main content bounding box, and estimated card columns.

    Args:
        image_path_or_url: Absolute or relative local path, or HTTP/HTTPS image URL.

    Returns:
        Dict with keys:
            - sidebar_detected: bool
            - sidebar_width_pct: float (e.g. 18.5)
            - sidebar_width_px: int
            - header_detected: bool
            - header_height_px: int
            - header_height_pct: float
            - main_grid_bounding_box: [x, y, w, h]
            - estimated_card_columns: int (e.g. 1, 2, 3, 4)
            - layout_type: str ("full_dashboard", "sidebar_and_grid", "header_and_grid", "grid_only", "single_column")
            - image_dimensions: {"width": int, "height": int}
            - recommendation: str
    """
    img = load_image(image_path_or_url)
    width, height = img.size

    # Convert to grayscale for fast luminance projection
    gray_img = img.convert("L")

    # Detect sidebar and header
    sidebar_detected, sidebar_w_px, sidebar_w_pct = _detect_sidebar(gray_img, width, height)
    header_detected, header_h_px, header_h_pct = _detect_header(
        gray_img, width, height, sidebar_x=sidebar_w_px
    )

    # Compute main grid bounding box [x, y, w, h]
    gx = sidebar_w_px if sidebar_detected else 0
    gy = header_h_px if header_detected else 0
    gw = max(1, width - gx)
    gh = max(1, height - gy)
    main_grid_box = [gx, gy, gw, gh]

    # Estimate card columns in main grid
    columns = _estimate_card_columns(gray_img, gx, gy, gw, gh)

    # Classify layout archetype
    if sidebar_detected and header_detected:
        layout_type = "full_dashboard"
        rec = (
            f"Desktop application/dashboard with a navigation sidebar ({sidebar_w_pct}% width, {sidebar_w_px}px), "
            f"a top header bar ({header_h_px}px), and a {columns}-column card grid in the main workspace."
        )
    elif sidebar_detected:
        layout_type = "sidebar_and_grid"
        rec = (
            f"Sidebar navigation layout ({sidebar_w_pct}% width, {sidebar_w_px}px) "
            f"with a {columns}-column main workspace."
        )
    elif header_detected:
        layout_type = "header_and_grid"
        rec = (
            f"Top navigation navbar ({header_h_px}px) with a centered {columns}-column card grid."
        )
    elif columns > 1:
        layout_type = "grid_only"
        rec = f"Multi-column card grid ({columns} columns) spanning the full canvas."
    else:
        layout_type = "single_column"
        rec = "Single-column editorial or hero layout with unified content flow."

    return {
        "sidebar_detected": sidebar_detected,
        "sidebar_width_pct": sidebar_w_pct,
        "sidebar_width_px": sidebar_w_px,
        "header_detected": header_detected,
        "header_height_px": header_h_px,
        "header_height_pct": header_h_pct,
        "main_grid_bounding_box": main_grid_box,
        "estimated_card_columns": columns,
        "layout_type": layout_type,
        "image_dimensions": {"width": width, "height": height},
        "recommendation": rec,
    }
