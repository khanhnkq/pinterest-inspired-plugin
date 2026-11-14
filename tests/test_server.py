"""Tests for the FastMCP Pinterest Inspiration server."""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.server import download_pin_image, mcp, search_pinterest_inspiration


def test_server_tool_registration():
    """Verify all 7 tools are properly registered on the FastMCP instance."""
    tool_names = [tool.name for tool in mcp._tool_manager.list_tools()]
    expected_tools = [
        "search_pinterest_inspiration",
        "download_pin_image",
        "extract_color_palette",
        "calculate_wcag_contrast",
        "extract_text_and_ocr",
        "detect_layout_regions",
        "compare_visual_diff",
    ]
    for tool_name in expected_tools:
        assert tool_name in tool_names, f"Missing tool: {tool_name}"


def test_search_pinterest_inspiration_empty_query():
    """Verify search raises ValueError for empty query."""
    with pytest.raises(ValueError, match="Search query cannot be empty"):
        search_pinterest_inspiration("")

    with pytest.raises(ValueError, match="Search query cannot be empty"):
        search_pinterest_inspiration("   ")


def test_search_pinterest_inspiration_success():
    """Verify search calls scraper and returns list of pin dicts."""
    mock_results = [
        {
            "id": "pin123",
            "dominant_color": "#1e293b",
            "aspect_ratio": 1.5,
            "image_url": "https://i.pinimg.com/originals/12/34/56/pin123.jpg",
            "preview_url": "https://i.pinimg.com/736x/12/34/56/pin123.jpg",
            "width": 1200,
            "height": 800,
            "query": "minimalist design",
        }
    ]

    with patch("src.pinterest_scraper.search_pinterest_inspiration") as mock_search:
        mock_search.return_value = mock_results
        results = search_pinterest_inspiration("minimalist design", limit=5)

        assert results == mock_results
        mock_search.assert_called_once_with("minimalist design", limit=5)


def test_download_pin_image_invalid_url():
    """Verify download raises ValueError for invalid URL."""
    with pytest.raises(ValueError, match="Invalid image URL"):
        download_pin_image("ftp://invalid-url.com/img.jpg")

    with pytest.raises(ValueError, match="Invalid image URL"):
        download_pin_image("")


def test_download_pin_image_success(tmp_path: Path):
    """Verify download delegates to scraper or saves to expected path."""
    test_url = "https://i.pinimg.com/originals/12/34/56/test_pin.jpg"
    expected_path = str(tmp_path / "test_pin.jpg")

    with patch("src.pinterest_scraper.download_pin_image") as mock_dl:
        mock_dl.return_value = expected_path
        res = download_pin_image(test_url, output_path=str(tmp_path))
        assert res == expected_path
        mock_dl.assert_called_once_with(test_url, output_path=str(tmp_path))


@pytest.mark.asyncio
async def test_fastmcp_call_tool_search():
    """Verify calling search_pinterest_inspiration via FastMCP protocol."""
    mock_results = [
        {
            "id": "pin_abc",
            "dominant_color": "#ff007f",
            "aspect_ratio": 0.75,
            "image_url": "https://i.pinimg.com/originals/ab/cd/ef/pin_abc.jpg",
            "preview_url": "https://i.pinimg.com/736x/ab/cd/ef/pin_abc.jpg",
            "width": 600,
            "height": 800,
            "query": "cyberpunk",
        }
    ]

    with patch("src.pinterest_scraper.search_pinterest_inspiration") as mock_search:
        mock_search.return_value = mock_results
        result = await mcp.call_tool(
            "search_pinterest_inspiration", {"query": "cyberpunk", "limit": 4}
        )
        assert len(result) >= 1
        # The result content should include pin details
        content_text = result[0][0].text
        assert "pin_abc" in content_text
        assert "#ff007f" in content_text


@pytest.mark.asyncio
async def test_fastmcp_call_tool_download():
    """Verify calling download_pin_image via FastMCP protocol."""
    test_url = "https://i.pinimg.com/originals/ab/cd/ef/sample.jpg"
    test_dest = "/tmp/sample.jpg"

    with patch("src.pinterest_scraper.download_pin_image") as mock_dl:
        mock_dl.return_value = test_dest
        result = await mcp.call_tool("download_pin_image", {"image_url": test_url})
        assert len(result) >= 1
        content_text = result[0][0].text
        assert content_text == test_dest


@pytest.mark.asyncio
async def test_fastmcp_call_tool_detect_layout():
    """Verify calling detect_layout_regions via FastMCP protocol."""
    mock_layout = {
        "sidebar_detected": True,
        "sidebar_width_pct": 18.5,
        "header_detected": True,
        "header_height_px": 64,
        "main_grid_bounding_box": [148, 64, 652, 536],
        "estimated_card_columns": 3,
        "layout_type": "full_dashboard",
    }

    with patch("src.layout_detector.detect_layout_regions") as mock_det:
        mock_det.return_value = mock_layout
        result = await mcp.call_tool("detect_layout_regions", {"image_path_or_url": "test.jpg"})
        assert len(result) >= 1
        assert "sidebar_detected" in result[0][0].text
        assert "full_dashboard" in result[0][0].text


@pytest.mark.asyncio
async def test_fastmcp_call_tool_compare_diff():
    """Verify calling compare_visual_diff via FastMCP protocol."""
    mock_diff = {
        "similarity_score_pct": 88.5,
        "threshold": 80.0,
        "passed": True,
        "diff_image_path": "/path/to/diff.png",
        "analysis": "PASSED with 88.5%",
    }

    with patch("src.visual_diff.compare_visual_diff") as mock_cmp:
        mock_cmp.return_value = mock_diff
        result = await mcp.call_tool(
            "compare_visual_diff",
            {
                "reference_image_path_or_url": "ref.jpg",
                "rendered_screenshot_path": "screen.png",
                "threshold": 80.0,
            },
        )
        assert len(result) >= 1
        assert "88.5" in result[0][0].text
        assert "PASSED" in result[0][0].text

