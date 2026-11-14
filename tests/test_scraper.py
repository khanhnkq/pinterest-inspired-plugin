"""Unit tests for Pinterest Mobile SSR scraper engine."""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

pytestmark = [pytest.mark.filterwarnings("ignore:.*asyncio_default_fixture_loop_scope.*:pytest.PytestDeprecationWarning")]

from src.pinterest_scraper import (
    MOBILE_USER_AGENT,
    PinterestRateLimitError,
    PinterestScraperError,
    _extract_pin_data,
    _sanitize_color,
    _sanitize_filename,
    async_download_pin_image,
    async_search_pinterest_inspiration,
    clear_query_cache,
    download_pin_image,
    extract_pins_from_html,
    search_pinterest_inspiration,
)

SAMPLE_PIN_PAYLOAD = {
    "initialReduxState": {
        "resources": {
            "BaseSearchResource": {
                "sample_query_key": {
                    "data": {
                        "results": [
                            {
                                "id": "pin_1",
                                "node_id": "node_pin_1",
                                "dominant_color": "#2c3e50",
                                "title": "Minimalist Workspace",
                                "description": "Clean desk setup with warm lighting",
                                "images": {
                                    "236x": {"width": 236, "height": 354, "url": "https://i.pinimg.com/236x/pin1.jpg"},
                                    "474x": {"width": 474, "height": 711, "url": "https://i.pinimg.com/474x/pin1.jpg"},
                                    "736x": {"width": 736, "height": 1104, "url": "https://i.pinimg.com/736x/pin1.jpg"},
                                    "orig": {"width": 1200, "height": 1800, "url": "https://i.pinimg.com/originals/pin1.jpg"},
                                },
                            },
                            {
                                "id": "pin_2",
                                "node_id": "node_pin_2",
                                "dominant_color": "e74c3c",  # Missing '#' prefix test
                                "title": "Modern Interior",
                                "images": {
                                    "736x": {"width": 736, "height": 736, "url": "https://i.pinimg.com/736x/pin2.jpg"},
                                    "orig": {"width": 1000, "height": 1000, "url": "https://i.pinimg.com/originals/pin2.jpg"},
                                },
                            },
                        ]
                    }
                }
            }
        },
        "pins": {
            "pin_3": {
                "id": "pin_3",
                "dominant_color": "#27ae60",
                "images": {
                    "orig": {"width": 800, "height": 1200, "url": "https://i.pinimg.com/originals/pin3.jpg"},
                    "736x": {"width": 736, "height": 1104, "url": "https://i.pinimg.com/736x/pin3.jpg"},
                },
            }
        },
    }
}


def make_mock_html(script_id: str, data: dict) -> str:
    """Helper to wrap JSON in SSR script tag."""
    json_str = json.dumps(data)
    return f"""
    <!DOCTYPE html>
    <html>
    <head><title>Pinterest</title></head>
    <body>
        <div id="root"></div>
        <script id="{script_id}" type="application/json">{json_str}</script>
    </body>
    </html>
    """


@pytest.fixture(autouse=True)
def reset_cache():
    """Ensure query cache is empty before each test."""
    clear_query_cache()
    yield
    clear_query_cache()


# ==========================================
# 1. Parsing & Extraction Tests
# ==========================================


def test_extract_pins_from_valid_initial_props():
    html = make_mock_html("__PWS_INITIAL_PROPS__", SAMPLE_PIN_PAYLOAD)
    pins = extract_pins_from_html(html, query="workspace", limit=10)

    assert len(pins) == 3
    # Check first pin from BaseSearchResource
    p1 = pins[0]
    assert p1["id"] == "pin_1"
    assert p1["dominant_color"] == "#2c3e50"
    assert p1["image_url"] == "https://i.pinimg.com/originals/pin1.jpg"
    assert p1["preview_url"] == "https://i.pinimg.com/736x/pin1.jpg"
    assert p1["width"] == 1200
    assert p1["height"] == 1800
    assert p1["aspect_ratio"] == 0.67
    assert p1["query"] == "workspace"
    assert p1["title"] == "Minimalist Workspace"

    # Check second pin (dominant color without # normalized to #e74c3c)
    p2 = pins[1]
    assert p2["id"] == "pin_2"
    assert p2["dominant_color"] == "#e74c3c"
    assert p2["aspect_ratio"] == 1.0

    # Check third pin from redux.pins
    p3 = pins[2]
    assert p3["id"] == "pin_3"
    assert p3["dominant_color"] == "#27ae60"


def test_extract_pins_limit_capping():
    html = make_mock_html("__PWS_INITIAL_PROPS__", SAMPLE_PIN_PAYLOAD)
    pins = extract_pins_from_html(html, limit=1)
    assert len(pins) == 1
    assert pins[0]["id"] == "pin_1"


def test_extract_pins_fallback_script_tags():
    # Test __PWS_DATA__ tag
    html_data = make_mock_html("__PWS_DATA__", SAMPLE_PIN_PAYLOAD)
    pins_data = extract_pins_from_html(html_data, limit=5)
    assert len(pins_data) >= 1

    # Test generic __PWS_* tag
    html_custom = make_mock_html("__PWS_EXPERIENCE_DATA__", SAMPLE_PIN_PAYLOAD)
    pins_custom = extract_pins_from_html(html_custom, limit=5)
    assert len(pins_custom) >= 1


def test_extract_pins_empty_or_missing_script():
    # Empty string
    assert extract_pins_from_html("") == []
    # HTML without any PWS script
    assert extract_pins_from_html("<html><body><h1>No Scripts</h1></body></html>") == []


def test_extract_pins_malformed_json():
    html = '<script id="__PWS_INITIAL_PROPS__">{invalid json: true}</script>'
    assert extract_pins_from_html(html) == []


def test_extract_pins_deep_search_fallback():
    # When BaseSearchResource and redux.pins are absent, deep search finds nested pins
    nested_data = {
        "customFeed": {
            "items": [
                {
                    "id": "deep_pin_1",
                    "dominant_color": "#123456",
                    "images": {
                        "orig": {"width": 500, "height": 500, "url": "https://i.pinimg.com/orig/deep1.jpg"}
                    },
                }
            ]
        }
    }
    html = make_mock_html("__PWS_INITIAL_PROPS__", nested_data)
    pins = extract_pins_from_html(html, limit=5)
    assert len(pins) == 1
    assert pins[0]["id"] == "deep_pin_1"
    assert pins[0]["image_url"] == "https://i.pinimg.com/orig/deep1.jpg"


# ==========================================
# 2. Field Normalization & Edge Cases
# ==========================================


def test_sanitize_color_variations():
    assert _sanitize_color("#FFFFFF") == "#ffffff"
    assert _sanitize_color("333333") == "#333333"
    assert _sanitize_color("#fff") == "#fff"
    assert _sanitize_color(None) == "#000000"
    assert _sanitize_color("invalid-color-code") == "#000000"
    assert _sanitize_color("") == "#000000"


def test_extract_pin_data_edge_cases():
    # Missing images dict returns None
    assert _extract_pin_data({"id": "p1"}) is None

    # Empty images dict returns None
    assert _extract_pin_data({"id": "p1", "images": {}}) is None

    # Missing orig falls back to 736x
    fallback_pin = _extract_pin_data({
        "id": "p_fallback",
        "images": {
            "736x": {"width": 736, "height": 1104, "url": "https://i.pinimg.com/736x/test.jpg"}
        }
    })
    assert fallback_pin is not None
    assert fallback_pin.image_url == "https://i.pinimg.com/736x/test.jpg"
    assert fallback_pin.preview_url == "https://i.pinimg.com/736x/test.jpg"
    assert fallback_pin.width == 736
    assert fallback_pin.height == 1104
    assert fallback_pin.aspect_ratio == 0.67

    # Zero height does not trigger division by zero
    zero_height_pin = _extract_pin_data({
        "id": "p_zero",
        "images": {
            "orig": {"width": 100, "height": 0, "url": "https://i.pinimg.com/orig/test.jpg"}
        }
    })
    assert zero_height_pin is not None
    assert zero_height_pin.aspect_ratio == 1.0


def test_sanitize_filename():
    assert _sanitize_filename("https://i.pinimg.com/originals/ab/cd/ef/abcdef123456.jpg") == "abcdef123456.jpg"
    assert _sanitize_filename("https://i.pinimg.com/image.png?query=param") == "image.png"
    # Fallback to sha256 stem if name has no safe chars
    assert _sanitize_filename("https://i.pinimg.com/?????.jpg").endswith(".jpg")
    # Path traversal characters in basename are stripped
    assert "/" not in _sanitize_filename("https://i.pinimg.com/../../etc/passwd.jpg")
    assert ".." not in _sanitize_filename("https://i.pinimg.com/../../etc/passwd.jpg")


def test_extract_pin_data_string_dimensions():
    # String dimensions are safely cast to int
    pin = _extract_pin_data({
        "id": "p_str",
        "images": {
            "orig": {"width": "600", "height": "800", "url": "https://i.pinimg.com/orig/test.jpg"}
        }
    })
    assert pin is not None
    assert pin.width == 600
    assert pin.height == 800
    assert pin.aspect_ratio == 0.75


# ==========================================
# 3. Search & Network Mocking Tests
# ==========================================


def test_search_pinterest_empty_query():
    with pytest.raises(ValueError, match="Search query cannot be empty"):
        search_pinterest_inspiration("")
    with pytest.raises(ValueError, match="Search query cannot be empty"):
        search_pinterest_inspiration("   ")


@patch("httpx.Client.get")
def test_search_pinterest_inspiration_success(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = make_mock_html("__PWS_INITIAL_PROPS__", SAMPLE_PIN_PAYLOAD)
    mock_get.return_value = mock_resp

    results = search_pinterest_inspiration("minimalist architecture", limit=5)
    assert len(results) == 3

    # Check request headers and URL encoding
    call_args = mock_get.call_args
    assert "https://www.pinterest.com/search/pins/?q=minimalist%20architecture" in call_args[0]


@patch("httpx.Client.get")
def test_search_pinterest_unicode_vietnamese(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = make_mock_html("__PWS_INITIAL_PROPS__", SAMPLE_PIN_PAYLOAD)
    mock_get.return_value = mock_resp

    query = "thiết kế nội thất scandinavian"
    search_pinterest_inspiration(query, limit=5)

    call_args = mock_get.call_args
    called_url = call_args[0][0]
    assert "thi%E1%BA%BFt%20k%E1%BA%BF" in called_url


@patch("httpx.Client.get")
def test_search_pinterest_rate_limit(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 429
    mock_get.return_value = mock_resp

    with pytest.raises(PinterestRateLimitError, match="HTTP 429"):
        search_pinterest_inspiration("modern logo", use_cache=False)


@patch("httpx.Client.get")
def test_search_pinterest_forbidden(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 403
    mock_get.return_value = mock_resp

    with pytest.raises(PinterestRateLimitError, match="HTTP 403"):
        search_pinterest_inspiration("dark tech ui", use_cache=False)


@patch("httpx.Client.get")
def test_search_pinterest_http_error(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "500 Internal Error", request=MagicMock(), response=mock_resp
    )
    mock_get.return_value = mock_resp

    with pytest.raises(PinterestScraperError, match="HTTP error"):
        search_pinterest_inspiration("luxury branding", use_cache=False)


@patch("httpx.Client.get")
def test_query_caching(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = make_mock_html("__PWS_INITIAL_PROPS__", SAMPLE_PIN_PAYLOAD)
    mock_get.return_value = mock_resp

    # First call: network hit
    res1 = search_pinterest_inspiration("editorial typography", limit=5, use_cache=True)
    assert mock_get.call_count == 1

    # Second call: cache hit (no additional network call)
    res2 = search_pinterest_inspiration("editorial typography", limit=5, use_cache=True)
    assert mock_get.call_count == 1
    assert len(res1) == len(res2)

    # Clearing cache triggers new network call
    clear_query_cache()
    search_pinterest_inspiration("editorial typography", limit=5, use_cache=True)
    assert mock_get.call_count == 2


# ==========================================
# 4. Downloader Tests
# ==========================================


def test_download_pin_image_invalid_url():
    with pytest.raises(ValueError, match="Invalid image URL"):
        download_pin_image("ftp://invalid.com/image.jpg")
    with pytest.raises(ValueError, match="Invalid image URL"):
        download_pin_image("")


@patch("httpx.Client.get")
def test_download_pin_image_default_cache_dir(mock_get, tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"content-type": "image/jpeg"}
    mock_resp.content = b"fake-default-cache-bytes"
    mock_get.return_value = mock_resp

    image_url = "https://i.pinimg.com/originals/99/88/77/default_cached_pin.jpg"
    saved_path = download_pin_image(image_url)

    assert os.path.exists(saved_path)
    assert ".pinterest_cache" in saved_path
    assert Path(saved_path).name == "default_cached_pin.jpg"
    assert Path(saved_path).read_bytes() == b"fake-default-cache-bytes"


@patch("httpx.Client.get")
def test_download_pin_image_to_custom_dir(mock_get, tmp_path: Path):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"content-type": "image/jpeg"}
    mock_resp.content = b"\xff\xd8\xff\xe0\x00\x10JFIF"  # Valid JPEG header bytes
    mock_get.return_value = mock_resp

    image_url = "https://i.pinimg.com/originals/11/22/33/112233aabbcc.jpg"
    dest_dir = str(tmp_path / "custom_images")

    saved_path = download_pin_image(image_url, output_path=dest_dir)
    assert os.path.exists(saved_path)
    assert Path(saved_path).name == "112233aabbcc.jpg"
    assert Path(saved_path).read_bytes() == b"\xff\xd8\xff\xe0\x00\x10JFIF"

    # Downloading again returns cached path without network call
    mock_get.reset_mock()
    cached_path = download_pin_image(image_url, output_path=dest_dir)
    assert cached_path == saved_path
    mock_get.assert_not_called()


@patch("httpx.Client.get")
def test_download_pin_image_to_custom_file(mock_get, tmp_path: Path):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"content-type": "image/png"}
    mock_resp.content = b"\x89PNG\r\n\x1a\n"
    mock_get.return_value = mock_resp

    image_url = "https://i.pinimg.com/originals/test.png"
    target_file = str(tmp_path / "reference_mood.png")

    saved_path = download_pin_image(image_url, output_path=target_file)
    assert saved_path == target_file
    assert os.path.exists(saved_path)
    assert Path(saved_path).read_bytes() == b"\x89PNG\r\n\x1a\n"


@patch("httpx.Client.get")
def test_download_pin_image_http_404(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    mock_get.return_value = mock_resp

    with pytest.raises(PinterestScraperError, match="HTTP 404"):
        download_pin_image("https://i.pinimg.com/originals/missing.jpg")


# ==========================================
# 5. Async Methods Test
# ==========================================


@pytest.mark.asyncio
async def test_async_search_pinterest():
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = make_mock_html("__PWS_INITIAL_PROPS__", SAMPLE_PIN_PAYLOAD)
        mock_get.return_value = mock_resp

        pins = await async_search_pinterest_inspiration("isometric 3d illustration", limit=2)
        assert len(pins) == 2
        assert pins[0]["id"] == "pin_1"


@pytest.mark.asyncio
async def test_async_download_image(tmp_path: Path):
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"content-type": "image/jpeg"}
        mock_resp.content = b"fake-async-image-data"
        mock_get.return_value = mock_resp

        target_file = str(tmp_path / "async_image.jpg")
        saved = await async_download_pin_image("https://i.pinimg.com/test.jpg", output_path=target_file)
        assert saved == target_file
        assert Path(saved).read_bytes() == b"fake-async-image-data"
