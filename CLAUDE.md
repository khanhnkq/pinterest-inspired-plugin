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

This plugin registers 7 standardized MCP tools:

1. `search_pinterest_inspiration(query: str, limit: int = 8)`:
   - Scrapes visual references from Pinterest via mobile SSR state.
   - Extracts HD `image_url`, preview `preview_url`, `dominant_color` hex, and aspect ratios.
   - Limit is capped between 1 and 10 to keep context lightweight.

2. `download_pin_image(image_url: str, output_path: str = '')`:
   - Downloads a selected pin image to `.pinterest_cache/` or a custom directory.
   - Allows vision analysis, computer-vision layout detection, or local design asset archiving.

3. `extract_color_palette(image_path_or_url: str, num_colors: int = 5)`:
   - Quantizes the image into prominent colors with percentage share and relative luminance.
   - Assigns 60-30-10 semantic roles (Canvas, Surface, Accent).
   - Generates ready-to-paste Tailwind CSS `@theme` snippet and WCAG contrast check.

4. `calculate_wcag_contrast(foreground_hex: str, background_hex: str)`:
   - Computes exact WCAG 2.1 relative luminance and contrast ratio.
   - Flags compliance for AA/AAA normal and large text.

5. `extract_text_and_ocr(image_path_or_url: str)`:
   - Uses Tesseract OCR to extract exact stats, numerical metrics (`$30,240`, `129`, `24%`), headings, and navigation labels from reference pins for high-fidelity UI cloning.

6. `detect_layout_regions(image_path_or_url: str)`:
   - Analyzes layout geometry using horizontal/vertical luminance projections.
   - Detects sidebar width %, header height px, content bounding box, and estimated card columns (e.g. 2, 3, or 4).

7. `compare_visual_diff(reference_image_path_or_url: str, rendered_screenshot_path: str, threshold: float = 80.0)`:
   - Compares a rendered UI screenshot with a reference pin using pixel absolute differences.
   - Outputs similarity percentage score (0-100%), pass/fail verdict, and saves a heatmap image to `.pinterest_cache/diff_heatmap.png`.

---

## Bundled Skills & Superpowers Iterative Verification Loop

This plugin bundles three native skills inside `skills/`:
- `skills/pinterest-inspiration`: Core visual search, moodboard extraction, layout detection, and visual diff verification.
- `skills/design-taste-frontend`: Anti-slop frontend taste (The Three Dials, Design Read, asymmetric layouts, typographic tension).
- `skills/web-design-guidelines`: Web interface guidelines, accessibility compliance, visible focus states, and WCAG contrast.

### Standard Verification Pipeline:
1. **Translate queries into descriptive visual English** with design terminology (e.g. `minimalist brutalist dashboard ui`, `artisanal ceramic landing page`).
2. **Present a rich Markdown visual moodboard** featuring preview images and dominant color hex badges. Let the user choose their reference pin.
3. **INSPECT (Multi-Modal CV Extraction):** Call `download_pin_image()`, `extract_color_palette()` (for 60-30-10 palette), `detect_layout_regions()` (for sidebar width % and card columns), and `extract_text_and_ocr()` (for real stats & labels).
4. **BUILD (Anti-Slop Synthesis):** Execute Design Read & Dials before writing frontend code (`design-taste-frontend`). Avoid AI defaults (purple gradients, generic centered 3-card grids).
5. **IMPROVE (Closed-Loop Visual Diff):** Render a screenshot of the built UI, run `compare_visual_diff(reference_pin, screenshot)`, and verify WCAG AA 4.5:1 contrast.
6. **ITERATE:** If similarity score < 80%, inspect `.pinterest_cache/diff_heatmap.png`, patch layout classes (grid columns, padding, typography), and re-verify until convergence.
