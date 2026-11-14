# CLAUDE.md — Claude Code Guidelines

Operational guidelines for Claude Code interacting with the Pinterest Inspiration Plugin.

---

## Commands

- **Install Environment:** `uv sync`
- **Run Unit Tests:** `uv run pytest`
- **Run Verbose Tests:** `uv run pytest -v`
- **Start MCP Server (stdio):** `uv run python -m src.server`

---

## MCP Tools Reference

This plugin registers two MCP tools:

1. `search_pinterest_inspiration(query: str, limit: int = 8)`:
   - Scrapes visual references from Pinterest via mobile SSR state.
   - Extracts HD `image_url`, preview `preview_url`, `dominant_color` hex, and aspect ratios.
   - Limit is capped between 1 and 10 to keep context lightweight.

2. `download_pin_image(image_url: str, output_path: str = '')`:
   - Downloads a selected pin image to `.pinterest_cache/` or a custom directory.
   - Allows vision analysis or local design asset archiving.

---

## Bundled Skills & Design Workflow

This plugin bundles three native skills inside `skills/`:
- `skills/pinterest-inspiration`: Core visual search and moodboard extraction.
- `skills/design-taste-frontend`: Anti-slop frontend taste (The Three Dials, Design Read, asymmetric layouts, typographic tension).
- `skills/web-design-guidelines`: Web interface guidelines, accessibility compliance, visible focus states, and WCAG contrast.

### Standard Pipeline:
1. **Translate queries into descriptive visual English** with design terminology (e.g. `minimalist brutalist dashboard ui`, `artisanal ceramic landing page`).
2. **Present a rich Markdown visual moodboard** featuring preview images and dominant color hex badges.
3. **Execute Design Read & Dials** before writing frontend code. Avoid AI defaults (purple gradients, generic centered 3-card grids).
4. **Map Pinterest dominant hex colors** into a 60-30-10 palette and enforce WCAG 4.5:1 contrast and keyboard focus.
