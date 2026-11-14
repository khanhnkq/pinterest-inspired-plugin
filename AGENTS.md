# AGENTS.md — Universal Agent Operating Guidelines

This document provides context, tool signatures, and operational workflows for AI coding agents (OpenAI Codex, Antigravity, Cursor, Windsurf, Claude Code) working with or utilizing the **Pinterest Inspiration Plugin**.

---

## 1. Project Purpose & Architecture

The **Pinterest Inspiration Plugin** is a zero-configuration, zero-API-key, and zero-browser-dependency visual inspiration engine. It uses Python 3, `uv`, and FastMCP over standard I/O (stdio).

- **Scraper Engine (`src/pinterest_scraper.py`):** Uses mobile Safari User-Agent SSR to parse `<script id="__PWS_INITIAL_PROPS__">` JSON, delivering top pins (<800ms) with original HD images, preview URLs, dominant hex colors, and aspect ratios.
- **FastMCP Server (`src/server.py`):** Exposes standardized MCP tools.
- **Cross-Agent Manifests:** `plugin.json`, `gemini-extension.json`, `mcp_config.json`, `mcp.json`, `.claude-plugin/plugin.json`.

---

## 2. Exposed MCP Tools

### `search_pinterest_inspiration(query: str, limit: int = 8)`
Searches Pinterest for visual references matching `query` and returns up to 10 pins.

- **Parameters:**
  - `query` (`string`, required): Descriptive visual keywords in English (e.g. `minimalist brutalist dashboard ui`, `cyberpunk neon editorial photography`).
  - `limit` (`integer`, optional, default: 8): Number of inspirations to return (clamped between 1 and 10).
- **Return Fields per Pin:**
  - `id`: Pinterest Pin ID.
  - `dominant_color`: Normalized hex code (e.g. `#1a202c`).
  - `aspect_ratio`: Float width/height ratio.
  - `image_url`: Highest-resolution original image URL (`orig`).
  - `preview_url`: Web-optimized preview URL (`736x`).
  - `width` & `height`: Dimensions in pixels.
  - `query`: The search keyword.

### `download_pin_image(image_url: str, output_path: str = '')`
Downloads an inspiration image to local storage for multi-modal vision inspection or direct project asset usage.

- **Parameters:**
  - `image_url` (`string`, required): Direct image URL obtained from `search_pinterest_inspiration`.
  - `output_path` (`string`, optional): Destination file or directory path. Defaults to `.pinterest_cache/<hash>.jpg`.
- **Return Value:**
  - Absolute local file path of the downloaded image.

---

## 3. Standard Agent Workflow

When a user asks for UI design, moodboards, branding, or AI image creation:

1. **Query Translation:** Convert user requests (even in Vietnamese or casual language) into clear visual English search terms.
   - *Example:* "Làm trang landing page bán gốm tối giản" → `"minimalist handcrafted ceramic pottery editorial landing page"`
2. **Visual Retrieval:** Call `search_pinterest_inspiration(query=..., limit=6)`.
3. **Present Moodboard:** Display an aesthetic Markdown moodboard with clickable images and dominant color hex badges.
4. **Downstream Execution:**
   - **For UI/UX:** Map dominant hex colors to Tailwind CSS palette (`primary`, `surface`, `accent`), choose layout grids, and build components.
   - **For AI Image Generation:** Deconstruct lighting, medium, camera angle, and colors into precise Midjourney or Gemini Imagen 3 prompts.

---

## 4. Development & Testing Commands

- **Install dependencies:** `uv sync`
- **Run test suite:** `uv run pytest`
- **Run test with output:** `uv run pytest -v`
- **Start MCP Server directly:** `uv run python -m src.server`
