"""Color extraction and WCAG accessibility analysis module.

Extracts quantized color palettes, relative luminance, semantic UI roles (60-30-10),
and WCAG contrast ratios from local image files or Pinterest image URLs using Pillow.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any
import httpx
from PIL import Image


def normalize_hex(hex_str: str) -> str:
    """Normalize 3-character or 6-character hex string to uppercase #RRGGBB."""
    clean = hex_str.strip().lstrip("#")
    if len(clean) == 3:
        clean = "".join(c * 2 for c in clean)
    if len(clean) != 6:
        raise ValueError(f"Invalid hex color: {hex_str}")
    return f"#{clean.upper()}"


def hex_to_rgb(hex_str: str) -> tuple[int, int, int]:
    """Convert hex string to (R, G, B) tuple."""
    normalized = normalize_hex(hex_str).lstrip("#")
    return (
        int(normalized[0:2], 16),
        int(normalized[2:4], 16),
        int(normalized[4:6], 16),
    )


def rgb_to_hex(r: int, g: int, b: int) -> str:
    """Convert (R, G, B) tuple to #RRGGBB."""
    return f"#{r:02X}{g:02X}{b:02X}"


def get_relative_luminance(hex_str: str) -> float:
    """Calculate WCAG 2.1 relative luminance for a given hex color.

    Formula: L = 0.2126 * R + 0.7152 * G + 0.0722 * B
    where each channel is gamma-corrected.
    """
    r, g, b = hex_to_rgb(hex_str)
    channels = []
    for c in (r, g, b):
        c_norm = c / 255.0
        if c_norm <= 0.04045:
            channels.append(c_norm / 12.92)
        else:
            channels.append(((c_norm + 0.055) / 1.055) ** 2.4)
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def calculate_contrast_ratio(fg_hex: str, bg_hex: str) -> dict[str, Any]:
    """Calculate WCAG 2.1 contrast ratio and compliance levels between two colors.

    Ratio formula: (L1 + 0.05) / (L2 + 0.05) where L1 is the lighter luminance.
    """
    fg_clean = normalize_hex(fg_hex)
    bg_clean = normalize_hex(bg_hex)

    l1 = get_relative_luminance(fg_clean)
    l2 = get_relative_luminance(bg_clean)

    lighter = max(l1, l2)
    darker = min(l1, l2)

    ratio = (lighter + 0.05) / (darker + 0.05)
    ratio_rounded = round(ratio, 2)

    pass_aa_normal = ratio >= 4.5
    pass_aa_large = ratio >= 3.0
    pass_aaa_normal = ratio >= 7.0
    pass_aaa_large = ratio >= 4.5
    pass_ui = ratio >= 3.0

    if pass_aaa_normal:
        status = "AAA_ENHANCED"
    elif pass_aa_normal:
        status = "AA_COMPLIANT"
    elif pass_aa_large:
        status = "AA_LARGE_TEXT_ONLY"
    else:
        status = "FAIL"

    return {
        "foreground": fg_clean,
        "background": bg_clean,
        "contrast_ratio": ratio_rounded,
        "contrast_display": f"{ratio_rounded}:1",
        "compliance": {
            "wcag_aa_normal_text": pass_aa_normal,
            "wcag_aa_large_text": pass_aa_large,
            "wcag_aaa_normal_text": pass_aaa_normal,
            "wcag_aaa_large_text": pass_aaa_large,
            "ui_components_and_graphics": pass_ui,
        },
        "status": status,
    }


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


def extract_color_palette(
    image_path_or_url: str,
    num_colors: int = 5,
) -> dict[str, Any]:
    """Extract dominant quantized color palette from image and generate semantic UI tokens.

    Args:
        image_path_or_url: Absolute/relative path or HTTP/HTTPS URL of image.
        num_colors: Number of distinct colors to extract (clamped between 3 and 10).

    Returns:
        Dict containing extracted colors with percentage share, relative luminance,
        semantic 60-30-10 assignments, contrast against canvas, and Tailwind CSS code snippet.
    """
    clamped_num = max(3, min(10, int(num_colors)))
    img = load_image(image_path_or_url)

    # Downscale for high-speed quantization (< 100ms)
    img_thumb = img.copy()
    img_thumb.thumbnail((200, 200), Image.Resampling.LANCZOS)

    # Quantize using median cut
    quantized = img_thumb.quantize(colors=clamped_num, method=Image.Quantize.MEDIANCUT)
    palette_raw = quantized.getpalette()[: clamped_num * 3]  # [r, g, b, r, g, b, ...]

    color_counts = quantized.getcolors() or []
    # Sort by frequency descending
    color_counts.sort(key=lambda x: x[0], reverse=True)
    total_pixels = sum(count for count, _ in color_counts) or 1

    extracted_colors: list[dict[str, Any]] = []
    seen_hex = set()

    for count, idx in color_counts:
        r = palette_raw[idx * 3]
        g = palette_raw[idx * 3 + 1]
        b = palette_raw[idx * 3 + 2]
        hex_code = rgb_to_hex(r, g, b)

        if hex_code in seen_hex:
            continue
        seen_hex.add(hex_code)

        pct = round((count / total_pixels) * 100, 1)
        lum = round(get_relative_luminance(hex_code), 4)

        extracted_colors.append({
            "hex": hex_code,
            "rgb": [r, g, b],
            "percentage": pct,
            "relative_luminance": lum,
            "is_dark": lum < 0.2,
        })

    if not extracted_colors:
        # Fallback if image was empty or pure white
        extracted_colors = [{
            "hex": "#121418",
            "rgb": [18, 20, 24],
            "percentage": 100.0,
            "relative_luminance": 0.005,
            "is_dark": True,
        }]

    # Assign 60-30-10 semantic roles
    canvas_color = extracted_colors[0]["hex"]
    surface_color = (
        extracted_colors[1]["hex"]
        if len(extracted_colors) > 1
        else extracted_colors[0]["hex"]
    )

    # Pick the most saturated/distinct color for Accent
    accent_color = None
    for color in extracted_colors[1:]:
        r, g, b = color["rgb"]
        max_c = max(r, g, b)
        min_c = min(r, g, b)
        saturation = (max_c - min_c) / max_c if max_c > 0 else 0
        if saturation > 0.25:
            accent_color = color["hex"]
            break
    if not accent_color:
        accent_color = (
            extracted_colors[2]["hex"]
            if len(extracted_colors) > 2
            else extracted_colors[-1]["hex"]
        )

    # Calculate contrast matrix against the main canvas
    contrast_analysis = []
    for c in extracted_colors:
        cr = calculate_contrast_ratio(c["hex"], canvas_color)
        contrast_analysis.append({
            "hex": c["hex"],
            "contrast_against_canvas": cr["contrast_display"],
            "wcag_aa_compliant": cr["compliance"]["wcag_aa_normal_text"],
        })

    # Generate Tailwind CSS @theme snippet
    tailwind_snippet = f"""@theme {{
  --color-brand-canvas: {canvas_color};
  --color-brand-surface: {surface_color};
  --color-brand-accent: {accent_color};
}}"""

    return {
        "total_colors_extracted": len(extracted_colors),
        "canvas_ground_60": canvas_color,
        "surface_structure_30": surface_color,
        "high_impact_accent_10": accent_color,
        "palette": extracted_colors,
        "contrast_analysis": contrast_analysis,
        "tailwind_config_snippet": tailwind_snippet,
    }
