"""Unit and integration tests for layout detector and visual diff modules."""

import io
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image, ImageDraw

from src.layout_detector import (
    _detect_header,
    _detect_sidebar,
    _estimate_card_columns,
    detect_layout_regions,
    load_image as load_layout_image,
)
from src.server import (
    compare_visual_diff as server_compare_visual_diff,
    detect_layout_regions as server_detect_layout_regions,
    mcp,
)
from src.visual_diff import (
    COMMON_RESOLUTION,
    compare_visual_diff,
    load_image as load_diff_image,
)

SHOWCASE_DIR = Path(__file__).parent.parent / "showcase"
DASHBOARD_PIN_1 = SHOWCASE_DIR / "dashboard" / "pin_dash_1.jpg"
DASHBOARD_SHOWCASE = SHOWCASE_DIR / "dashboard-showcase-desktop.png"


@pytest.fixture
def synthetic_dashboard_image(tmp_path: Path) -> Path:
    """Create a synthetic dashboard image (1000x700) with a dark sidebar, header, and 3-column cards."""
    width, height = 1000, 700
    img = Image.new("RGB", (width, height), color=(240, 243, 246))  # Light canvas
    draw = ImageDraw.Draw(img)

    # 1. Dark left sidebar: x: 0..180 (18% width)
    draw.rectangle([0, 0, 180, height], fill=(26, 32, 44))

    # 2. Header navbar: x: 180..1000, y: 0..70 (70px height)
    draw.rectangle([180, 0, width, 70], fill=(255, 255, 255))
    draw.line([180, 70, width, 70], fill=(226, 232, 240), width=2)

    # 3. Content area: 3 columns of cards
    # Main area x: 210..970 (width=760), y: 100..650
    gutter = 20
    col_w = (760 - 2 * gutter) // 3
    start_x = 210

    for i in range(3):
        cx = start_x + i * (col_w + gutter)
        # Top KPI card
        draw.rectangle([cx, 100, cx + col_w, 220], fill=(255, 255, 255), outline=(203, 213, 225), width=2)
        # Main chart/content card
        draw.rectangle([cx, 250, cx + col_w, 650], fill=(255, 255, 255), outline=(203, 213, 225), width=2)

    dest = tmp_path / "synthetic_dashboard.png"
    img.save(dest, format="PNG")
    return dest


@pytest.fixture
def synthetic_sidebar_only_image(tmp_path: Path) -> Path:
    """Create an image with only a dark vertical sidebar and flat content."""
    width, height = 800, 600
    img = Image.new("RGB", (width, height), color=(245, 245, 245))
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, 160, height], fill=(30, 30, 35))

    dest = tmp_path / "synthetic_sidebar.png"
    img.save(dest, format="PNG")
    return dest


@pytest.fixture
def synthetic_header_only_image(tmp_path: Path) -> Path:
    """Create an image with only a distinct top header and flat content."""
    width, height = 800, 600
    img = Image.new("RGB", (width, height), color=(250, 250, 250))
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, width, 60], fill=(20, 25, 30))

    dest = tmp_path / "synthetic_header.png"
    img.save(dest, format="PNG")
    return dest


@pytest.fixture
def synthetic_uniform_image(tmp_path: Path) -> Path:
    """Create a completely uniform solid image with no UI structure."""
    img = Image.new("RGB", (600, 400), color=(245, 245, 245))
    dest = tmp_path / "synthetic_uniform.png"
    img.save(dest, format="PNG")
    return dest


# =========================================================================
# 1. Tests for detect_layout_regions
# =========================================================================

def test_detect_layout_synthetic_dashboard(synthetic_dashboard_image: Path):
    """Test full dashboard layout detection: sidebar, header, and multi-column grid."""
    result = detect_layout_regions(str(synthetic_dashboard_image))

    assert result["sidebar_detected"] is True
    assert 16.0 <= result["sidebar_width_pct"] <= 20.0
    assert 160 <= result["sidebar_width_px"] <= 200

    assert result["header_detected"] is True
    assert 60 <= result["header_height_px"] <= 80

    assert result["layout_type"] == "full_dashboard"
    assert result["main_grid_bounding_box"][0] == result["sidebar_width_px"]
    assert result["main_grid_bounding_box"][1] == result["header_height_px"]
    assert result["estimated_card_columns"] >= 2
    assert "sidebar" in result["recommendation"].lower()


def test_detect_layout_synthetic_sidebar_only(synthetic_sidebar_only_image: Path):
    """Test sidebar detection when no top header is present."""
    result = detect_layout_regions(str(synthetic_sidebar_only_image))

    assert result["sidebar_detected"] is True
    assert 18.0 <= result["sidebar_width_pct"] <= 22.0
    assert result["header_detected"] is False
    assert result["layout_type"] == "sidebar_and_grid"


def test_detect_layout_synthetic_header_only(synthetic_header_only_image: Path):
    """Test header detection when no left sidebar is present."""
    result = detect_layout_regions(str(synthetic_header_only_image))

    assert result["sidebar_detected"] is False
    assert result["header_detected"] is True
    assert 50 <= result["header_height_px"] <= 70
    assert result["layout_type"] == "header_and_grid"


def test_detect_layout_synthetic_uniform(synthetic_uniform_image: Path):
    """Test uniform canvas with no distinct layout elements."""
    result = detect_layout_regions(str(synthetic_uniform_image))

    assert result["sidebar_detected"] is False
    assert result["header_detected"] is False
    assert result["estimated_card_columns"] == 1
    assert result["layout_type"] == "single_column"


def test_detect_layout_small_image_edge_case():
    """Test small image edge cases (<150px) return gracefully without crashing."""
    img = Image.new("RGB", (100, 80), color=(20, 20, 20))
    gray = img.convert("L")

    sidebar_detected, sw, sp = _detect_sidebar(gray, 100, 80)
    assert sidebar_detected is False
    assert sw == 0

    header_detected, hh, hp = _detect_header(gray, 100, 80)
    assert header_detected is False
    assert hh == 0

    cols = _estimate_card_columns(gray, 0, 0, 100, 80)
    assert cols == 1


def test_detect_layout_file_not_found():
    """Verify FileNotFoundError on missing local file."""
    with pytest.raises(FileNotFoundError, match="Image not found"):
        detect_layout_regions("/nonexistent/path/layout_image.png")


def test_detect_layout_remote_url(synthetic_dashboard_image: Path):
    """Verify loading and detecting layout from HTTP URL."""
    with open(synthetic_dashboard_image, "rb") as f:
        img_bytes = f.read()

    mock_resp = MagicMock()
    mock_resp.content = img_bytes
    mock_resp.raise_for_status.return_value = None

    with patch("httpx.get", return_value=mock_resp) as mock_get:
        result = detect_layout_regions("https://example.com/dashboard.png")
        assert result["sidebar_detected"] is True
        assert result["layout_type"] == "full_dashboard"
        mock_get.assert_called_once()


def test_detect_layout_real_showcase_image():
    """Verify layout detection on real Pinterest reference image."""
    assert DASHBOARD_PIN_1.is_file(), f"Missing reference image: {DASHBOARD_PIN_1}"

    result = detect_layout_regions(str(DASHBOARD_PIN_1))

    expected_keys = {
        "sidebar_detected",
        "sidebar_width_pct",
        "sidebar_width_px",
        "header_detected",
        "header_height_px",
        "header_height_pct",
        "main_grid_bounding_box",
        "estimated_card_columns",
        "layout_type",
        "image_dimensions",
        "recommendation",
    }
    assert expected_keys.issubset(result.keys())
    assert result["image_dimensions"]["width"] > 0
    assert result["image_dimensions"]["height"] > 0
    assert result["layout_type"] in [
        "full_dashboard",
        "sidebar_and_grid",
        "header_and_grid",
        "grid_only",
        "single_column",
    ]
    assert len(result["main_grid_bounding_box"]) == 4


# =========================================================================
# 2. Tests for compare_visual_diff
# =========================================================================

def test_visual_diff_identical_images(tmp_path: Path):
    """Test comparison between identical images yields 100% similarity."""
    img = Image.new("RGB", (400, 300), color=(120, 150, 180))
    p1 = tmp_path / "img1.png"
    p2 = tmp_path / "img2.png"
    img.save(p1)
    img.save(p2)

    diff_path = tmp_path / "identical_diff.png"
    result = compare_visual_diff(str(p1), str(p2), threshold=80.0, output_diff_path=str(diff_path))

    assert result["similarity_score_pct"] == 100.0
    assert result["passed"] is True
    assert result["mean_channel_diff"] == 0.0
    assert result["threshold"] == 80.0
    assert Path(result["diff_image_path"]).is_file()
    assert "PASSED" in result["analysis"]


def test_visual_diff_opposite_images(tmp_path: Path):
    """Test comparison between black and white images yields 0% similarity."""
    black = Image.new("RGB", (400, 300), color=(0, 0, 0))
    white = Image.new("RGB", (400, 300), color=(255, 255, 255))
    p_black = tmp_path / "black.png"
    p_white = tmp_path / "white.png"
    black.save(p_black)
    white.save(p_white)

    diff_path = tmp_path / "opposite_diff.png"
    result = compare_visual_diff(str(p_black), str(p_white), threshold=80.0, output_diff_path=str(diff_path))

    assert result["similarity_score_pct"] == 0.0
    assert result["passed"] is False
    assert result["mean_channel_diff"] == 255.0
    assert Path(result["diff_image_path"]).is_file()
    assert "FAILED" in result["analysis"]


def test_visual_diff_threshold_evaluation(tmp_path: Path):
    """Test custom threshold behavior (e.g. 50% vs 95%)."""
    # Base image: gray (128, 128, 128), Target: lighter gray (180, 180, 180)
    # Diff = 52 / 255 = ~20.4%, Similarity = ~79.6%
    img1 = Image.new("RGB", (400, 300), color=(128, 128, 128))
    img2 = Image.new("RGB", (400, 300), color=(180, 180, 180))
    p1 = tmp_path / "gray1.png"
    p2 = tmp_path / "gray2.png"
    img1.save(p1)
    img2.save(p2)

    res_lenient = compare_visual_diff(str(p1), str(p2), threshold=70.0)
    assert res_lenient["passed"] is True

    res_strict = compare_visual_diff(str(p1), str(p2), threshold=90.0)
    assert res_strict["passed"] is False


def test_visual_diff_default_cache_dir(tmp_path: Path):
    """Test diff heatmap defaults to .pinterest_cache/diff_heatmap.png."""
    img1 = Image.new("RGB", (200, 200), color=(100, 100, 100))
    img2 = Image.new("RGB", (200, 200), color=(110, 110, 110))
    p1 = tmp_path / "cache1.png"
    p2 = tmp_path / "cache2.png"
    img1.save(p1)
    img2.save(p2)

    result = compare_visual_diff(str(p1), str(p2))
    assert result["diff_image_path"].endswith("diff_heatmap.png")
    assert Path(result["diff_image_path"]).is_file()


def test_visual_diff_file_not_found():
    """Verify FileNotFoundError when input image path is missing."""
    with pytest.raises(FileNotFoundError, match="Image not found"):
        compare_visual_diff("/missing/ref.png", "/missing/ren.png")


def test_visual_diff_remote_url(tmp_path: Path):
    """Verify visual diff when loading one or both images from HTTP URL."""
    img = Image.new("RGB", (300, 200), color=(50, 100, 150))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    img_bytes = buf.getvalue()

    local_path = tmp_path / "local.png"
    img.save(local_path)

    mock_resp = MagicMock()
    mock_resp.content = img_bytes
    mock_resp.raise_for_status.return_value = None

    with patch("httpx.get", return_value=mock_resp) as mock_get:
        result = compare_visual_diff("https://example.com/remote.png", str(local_path))
        assert result["similarity_score_pct"] == 100.0
        assert result["passed"] is True
        mock_get.assert_called_once()


def test_visual_diff_real_showcase_images():
    """Verify visual comparison on real reference pin and rendered showcase screenshot."""
    assert DASHBOARD_PIN_1.is_file(), f"Missing reference: {DASHBOARD_PIN_1}"
    assert DASHBOARD_SHOWCASE.is_file(), f"Missing showcase screenshot: {DASHBOARD_SHOWCASE}"

    result = compare_visual_diff(
        str(DASHBOARD_PIN_1),
        str(DASHBOARD_SHOWCASE),
        threshold=80.0,
    )

    assert result["similarity_score_pct"] >= 80.0
    assert result["passed"] is True
    assert result["resolution_compared"] == list(COMMON_RESOLUTION)
    assert Path(result["diff_image_path"]).is_file()
    assert "PASSED" in result["analysis"]


# =========================================================================
# 3. Tests for Server FastMCP Tool Registration & Invocations
# =========================================================================

def test_server_detect_layout_regions_tool(synthetic_dashboard_image: Path):
    """Test calling detect_layout_regions through the server tool function."""
    res = server_detect_layout_regions(str(synthetic_dashboard_image))
    assert res["sidebar_detected"] is True
    assert res["layout_type"] == "full_dashboard"


def test_server_compare_visual_diff_tool(tmp_path: Path):
    """Test calling compare_visual_diff through the server tool function."""
    img = Image.new("RGB", (200, 200), color=(10, 20, 30))
    p1 = tmp_path / "s1.png"
    p2 = tmp_path / "s2.png"
    img.save(p1)
    img.save(p2)

    res = server_compare_visual_diff(str(p1), str(p2), threshold=85.0)
    assert res["similarity_score_pct"] == 100.0
    assert res["passed"] is True


@pytest.mark.asyncio
async def test_fastmcp_call_tool_detect_layout_and_diff(synthetic_dashboard_image: Path, tmp_path: Path):
    """Test FastMCP protocol call_tool execution for both new tools."""
    # Test detect_layout_regions via protocol
    detect_res = await mcp.call_tool(
        "detect_layout_regions",
        {"image_path_or_url": str(synthetic_dashboard_image)},
    )
    assert len(detect_res) > 0
    # In FastMCP, call_tool returns (content_list, extra)
    content = detect_res[0] if isinstance(detect_res, list) else detect_res[0]
    first_item = content[0] if isinstance(content, list) else content
    assert "sidebar_detected" in first_item.text

    # Test compare_visual_diff via protocol
    img = Image.new("RGB", (200, 200), color=(50, 60, 70))
    p1 = tmp_path / "proto1.png"
    p2 = tmp_path / "proto2.png"
    img.save(p1)
    img.save(p2)

    diff_res = await mcp.call_tool(
        "compare_visual_diff",
        {"reference_image_path_or_url": str(p1), "rendered_screenshot_path": str(p2), "threshold": 80.0},
    )
    assert len(diff_res) > 0
    diff_content = diff_res[0] if isinstance(diff_res, list) else diff_res[0]
    diff_first_item = diff_content[0] if isinstance(diff_content, list) else diff_content
    assert "similarity_score_pct" in diff_first_item.text
    assert "passed" in diff_first_item.text
