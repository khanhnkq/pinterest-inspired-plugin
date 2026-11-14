# CLAUDE.md — Claude Code Guidelines

Operational guidelines for Claude Code interacting with the Pinterest Inspiration Plugin.

---

## Commands

- **Install Environment:** `uv sync`
- **Run Unit Tests:** `uv run pytest`
- **Run Verbose Tests:** `uv run pytest -v`
- **Start MCP Server (stdio):** `uv run python -m src.server`

---

## MCP Tool Reference

This plugin registers two MCP tools:

1. `search_pinterest_inspiration(query: str, limit: int = 8)`:
   - Scrapes visual references from Pinterest via mobile SSR state.
   - Extracts HD `image_url`, preview `preview_url`, `dominant_color` hex, and aspect ratios.
   - Limit is capped between 1 and 10 to keep context lightweight.

2. `download_pin_image(image_url: str, output_path: str = '')`:
   - Downloads a selected pin image to `.pinterest_cache/` or a custom directory.
   - Allows vision analysis or local design asset archiving.

---

## Agent Guidelines & Style

- **Always translate non-English or vague user intents into visual English search terms.** Pinterest returns optimal visual pins with descriptive English style keywords (e.g. `brutalist editorial typography poster`, `swiss style minimalism ui`).
- **Do not overwhelm the user with raw JSON.** Synthesize search results into clean Markdown visual moodboards with dominant color swatches (`#hex`) and image previews.
- **Respect constraints:** Zero API keys, zero headless browser dependencies, fast execution (<800ms).
