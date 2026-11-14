"""Unit and integration tests for color extractor and OCR tools."""

import io
from pathlib import Path
import pytest
from PIL import Image

from src.color_extractor import (
    calculate_contrast_ratio,
    extract_color_palette,
    get_relative_luminance,
    hex_to_rgb,
    normalize_hex,
    rgb_to_hex,
)
from src.ocr_extractor import extract_text_and_ocr, find_tesseract_binary
from src.server import (
    calculate_wcag_contrast,
    extract_color_palette as server_extract_color,
    extract_text_and_ocr as server_extract_ocr,
)


def test_normalize_hex():
    assert normalize_hex("#fff") == "#FFFFFF"
    assert normalize_hex("121418") == "#121418"
    assert normalize_hex("#0b0d10") == "#0B0D10"
    with pytest.raises(ValueError):
        normalize_hex("invalid")


def test_hex_rgb_conversions():
    rgb = hex_to_rgb("#FFFFFF")
    assert rgb == (255, 255, 255)
    assert rgb_to_hex(255, 255, 255) == "#FFFFFF"

    black_rgb = hex_to_rgb("#000000")
    assert black_rgb == (0, 0, 0)
    assert rgb_to_hex(0, 0, 0) == "#000000"


def test_relative_luminance():
    # Pure white has luminance 1.0, black has 0.0
    lum_white = get_relative_luminance("#FFFFFF")
    lum_black = get_relative_luminance("#000000")
    assert pytest.approx(lum_white, 0.01) == 1.0
    assert pytest.approx(lum_black, 0.01) == 0.0


def test_calculate_contrast_ratio():
    # Black on white: 21:1
    res = calculate_contrast_ratio("#000000", "#FFFFFF")
    assert res["contrast_ratio"] == 21.0
    assert res["status"] == "AAA_ENHANCED"
    assert res["compliance"]["wcag_aa_normal_text"] is True
    assert res["compliance"]["wcag_aaa_normal_text"] is True

    # Low contrast: #888888 on #777777 fails
    low_res = calculate_contrast_ratio("#888888", "#777777")
    assert low_res["contrast_ratio"] < 3.0
    assert low_res["status"] == "FAIL"
    assert low_res["compliance"]["wcag_aa_normal_text"] is False


def test_extract_color_palette_synthetic(tmp_path: Path):
    # Create a 100x100 synthetic test image with two distinct colors
    test_img = Image.new("RGB", (100, 100), color=(16, 20, 26))
    for x in range(30):
        for y in range(30):
            test_img.putpixel((x, y), (16, 185, 129))  # Emerald

    img_path = tmp_path / "test_synth.png"
    test_img.save(img_path)

    result = extract_color_palette(str(img_path), num_colors=3)
    assert result["total_colors_extracted"] >= 2
    assert "canvas_ground_60" in result
    assert "surface_structure_30" in result
    assert "palette" in result
    assert len(result["palette"]) >= 2
    assert "@theme" in result["tailwind_config_snippet"]


def test_extract_color_palette_real_image():
    sample_pin = Path("showcase/dashboard/pin_dash_1.jpg")
    if sample_pin.exists():
        result = extract_color_palette(str(sample_pin), num_colors=5)
        assert result["total_colors_extracted"] == 5
        assert result["canvas_ground_60"].startswith("#")
        assert len(result["contrast_analysis"]) == 5


def test_ocr_extractor_real_image():
    sample_pin = Path("showcase/dashboard/pin_dash_1.jpg")
    if sample_pin.exists():
        result = extract_text_and_ocr(str(sample_pin))
        if find_tesseract_binary():
            assert result["success"] is True
            assert len(result["lines"]) > 0
            assert len(result["numerical_metrics"]) > 0
            # Confirm that key metrics like 129 or 24 or 30,240 or percentages were captured
            metrics_joined = " ".join(result["numerical_metrics"])
            assert any(num in metrics_joined for num in ["129", "24", "30", "80%", "20%"])
        else:
            assert result["success"] is False
            assert "Tesseract binary not found" in result["error"]


def test_server_tools_integration():
    sample_pin = Path("showcase/dashboard/pin_dash_1.jpg")
    if sample_pin.exists():
        pal = server_extract_color(str(sample_pin), num_colors=4)
        assert pal["total_colors_extracted"] == 4

        contrast = calculate_wcag_contrast("#FFFFFF", "#16191F")
        assert contrast["contrast_ratio"] > 14.0
        assert contrast["status"] == "AAA_ENHANCED"

        ocr_res = server_extract_ocr(str(sample_pin))
        assert "raw_text" in ocr_res
