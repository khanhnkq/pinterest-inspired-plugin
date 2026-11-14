"""OCR and UI Layout Text Extraction Module.

Extracts text, numbers, metrics, navigation labels, and UI headers from
downloaded inspiration pins or image URLs using Tesseract OCR.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any
import httpx


def find_tesseract_binary() -> str | None:
    """Find the path to the tesseract CLI binary on the system."""
    # Check standard PATH
    path_bin = shutil.which("tesseract")
    if path_bin and os.path.isfile(path_bin):
        return path_bin

    # Check common absolute paths across macOS and Linux
    common_paths = [
        "/opt/homebrew/bin/tesseract",
        "/usr/local/bin/tesseract",
        "/usr/bin/tesseract",
        "/bin/tesseract",
    ]
    for p in common_paths:
        if os.path.isfile(p) and os.access(p, os.X_OK):
            return p
    return None


def extract_text_and_ocr(image_path_or_url: str) -> dict[str, Any]:
    """Extract raw text, numerical metrics, headers, and navigation tokens from an image.

    Args:
        image_path_or_url: Local file path or HTTP/HTTPS image URL.

    Returns:
        Structured dict with:
          - raw_text: Unformatted OCR text
          - lines: Non-empty cleaned lines
          - numerical_metrics: Extracted stats (e.g., "$30,240", "129", "24%", "14d")
          - detected_navigation: Common UI nav items detected
          - detected_headings: Candidate section headers and tabs
    """
    path_or_url = str(image_path_or_url).strip()
    temp_path: Path | None = None

    try:
        if path_or_url.startswith(("http://", "https://")):
            # Download to a temporary file
            resp = httpx.get(
                path_or_url,
                headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"},
                timeout=15.0,
                follow_redirects=True,
            )
            resp.raise_for_status()
            cache_dir = Path(".pinterest_cache")
            cache_dir.mkdir(parents=True, exist_ok=True)
            temp_path = cache_dir / "temp_ocr_image.jpg"
            temp_path.write_bytes(resp.content)
            target_file = str(temp_path.resolve())
        else:
            local_path = Path(path_or_url).expanduser().resolve()
            if not local_path.is_file():
                raise FileNotFoundError(f"Image not found at path: {local_path}")
            target_file = str(local_path)

        tesseract_bin = find_tesseract_binary()
        if not tesseract_bin:
            return {
                "success": False,
                "error": "Tesseract binary not found on host. Install via 'brew install tesseract' or 'apt-get install tesseract-ocr'.",
                "raw_text": "",
                "lines": [],
                "numerical_metrics": [],
                "detected_headings": [],
                "detected_navigation": [],
            }

        # Run Tesseract with page segmentation mode 6 (assume uniform block of text)
        result = subprocess.run(
            [tesseract_bin, target_file, "stdout", "--psm", "6"],
            capture_output=True,
            text=True,
            timeout=15,
        )

        raw_output = result.stdout.strip()
        lines = [
            line.strip()
            for line in raw_output.splitlines()
            if line.strip() and len(line.strip()) > 1
        ]

        # Extract numerical metrics (currency, percentages, counts, ratios)
        # Matches patterns like $30,240, 24%, 129, +8, 14d, 95%
        metric_pattern = re.compile(
            r"([$€£¥]?\s*[-+]?\d{1,3}(?:,\d{3})*(?:\.\d+)?\s*(?:%|[kdhmb]|vs\s+last\s+\w+)?|\b\d{1,4}\s*(?:leads|users|items|orders|pts)?\b)",
            re.IGNORECASE,
        )
        found_metrics: list[str] = []
        for line in lines:
            matches = metric_pattern.findall(line)
            for m in matches:
                clean_m = m.strip()
                if (
                    len(clean_m) >= 2
                    and any(char.isdigit() for char in clean_m)
                    and clean_m not in found_metrics
                ):
                    found_metrics.append(clean_m)

        # Detect candidate headings and tabs
        common_ui_keywords = {
            "dashboard",
            "overview",
            "analytics",
            "reports",
            "leads",
            "contacts",
            "deals",
            "settings",
            "workflows",
            "calendar",
            "status",
            "sources",
            "qualification",
            "retention",
            "revenue",
            "conversion",
            "customizer",
            "search",
            "help",
            "documentation",
        }

        detected_headings: list[str] = []
        detected_nav: list[str] = []

        for line in lines:
            lower = line.lower()
            # If line is short and matches keywords or title case
            if len(line.split()) <= 4:
                for kw in common_ui_keywords:
                    if kw in lower and line not in detected_headings:
                        if kw in {"platform", "system", "dashboard", "contacts", "deals", "settings", "workflows"}:
                            detected_nav.append(line)
                        else:
                            detected_headings.append(line)

        return {
            "success": True,
            "tesseract_version": "Tesseract OCR",
            "image_source": target_file,
            "raw_text": raw_output,
            "lines": lines,
            "numerical_metrics": found_metrics,
            "detected_headings": list(dict.fromkeys(detected_headings)),
            "detected_navigation": list(dict.fromkeys(detected_nav)),
        }

    finally:
        # Clean up temporary download file if created
        if temp_path and temp_path.is_file():
            try:
                temp_path.unlink()
            except OSError:
                pass
