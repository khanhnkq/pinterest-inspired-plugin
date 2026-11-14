# Pinterest Inspiration Plugin Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a lightweight, cross-agent MCP plugin (compatible with Antigravity, Claude Code, OpenAI Codex, and Cursor) that scrapes 5–10 visual inspiration images from Pinterest, extracts design tokens (high-res images, dominant colors, aspect ratios), and equips AI Agents with standardized skills to reference them for UI/UX coding and AI image generation.

**Architecture:** Node.js (TypeScript) stdio MCP server using native `fetch` with mobile User-Agent to extract Pinterest's server-rendered `<script id="__PWS_INITIAL_PROPS__">` JSON state, returning clean visual-first pins without requiring browser binaries or API tokens. Paired with an Antigravity Skill (`pinterest-inspiration`) that guides the Agent to map dominant colors, layouts, and moods into Tailwind CSS/React code or image prompts.

**Tech Stack:** Node.js (v18+ / v24), TypeScript, `@modelcontextprotocol/sdk`, `vitest` for tests, `tsup` for compilation.

**Spec:** `docs/superpowers/specs/2026-11-14-pinterest-inspired-plugin-design.md`

## Global Constraints

- Max image results: 10 images per search query.
- No official Pinterest API keys or OAuth required.
- No headless browser dependencies (No Puppeteer/Playwright).
- Stdio transport for MCP server compatibility with Antigravity.
- Zero network dependencies beyond native `fetch`.

## Review Focus

1. **Pinterest HTML Structure Shift:** Pinterest occasionally alters script tags (`__PWS_INITIAL_PROPS__` vs `__PWS_DATA__`); scraper must handle missing tags gracefully with informative error messages.
2. **Vietnamese / Unicode Query Encoding:** Queries with special characters or Vietnamese diacritics must be properly URL-encoded.
3. **HTTP 429 / 403 Rate Limiting:** When Pinterest temporarily blocks requests, server must fail fast with clean error text instead of crashing or hanging.
4. **Invalid or Expired Image URLs:** Image downloader must validate HTTP status codes (200 OK) and content types before saving.
5. **Path Traversal in Image Downloader:** Destination paths must be sanitized to prevent saving files outside intended directories.

---

### Task 1: Scaffolding, Cross-Agent Manifests, and Build Tooling

**Files:**
- Create: `package.json`
- Create: `tsconfig.json`
- Create: `tsup.config.ts`
- Create: `plugin.json` (Universal Plugin Manifest)
- Create: `gemini-extension.json` (Antigravity & Gemini CLI)
- Create: `mcp_config.json` (Antigravity MCP config)
- Create: `mcp.json` (Claude Code, Codex, Cursor MCP standard)
- Create: `.claude-plugin/plugin.json` (Claude Code plugin manifest)
- Create: `AGENTS.md` (OpenAI Codex / Universal Agent Rules)
- Create: `CLAUDE.md` (Claude Code Instructions)
- Create: `.gitignore`

**Interfaces:**
- Produces: Project build pipeline (`npm run build`), test runner (`npm test`), and multi-agent manifest files enabling seamless plug-and-play across Antigravity, Claude Code, OpenAI Codex, and Cursor.

- [ ] **Step 1: Create `package.json`**
  Define npm package with scripts (`build`, `test`, `start`), dependencies (`@modelcontextprotocol/sdk`), and devDependencies (`typescript`, `tsup`, `vitest`, `@types/node`).

- [ ] **Step 2: Create `tsconfig.json` and `tsup.config.ts`**
  Configure TypeScript targeting ES2022 with NodeNext module resolution, and `tsup` bundling `src/index.ts` to `dist/index.js` with shebang `#!/usr/bin/env node`.

- [ ] **Step 3: Create Multi-Agent manifests & guidelines**
  - `plugin.json`: Declare universal plugin manifest (name `pinterest-inspiration`, version `1.0.0`, description, keywords).
  - `gemini-extension.json`: Antigravity / Gemini CLI extension descriptor.
  - `mcp_config.json` & `mcp.json`: Standard stdio MCP registration executing `node dist/index.js`.
  - `.claude-plugin/plugin.json`: Claude Code plugin manifest.
  - `AGENTS.md` & `CLAUDE.md`: Universal guidance on when and how to call the Pinterest inspiration tools and skills.
  - `.gitignore`: Ignore `node_modules/`, `dist/`, `.pinterest_cache/`.

- [ ] **Step 4: Install dependencies and verify build toolchain**
  Run `npm install` and verify config files are syntactically valid.

- [ ] **Step 5: Commit**
  ```bash
  git add package.json tsconfig.json tsup.config.ts plugin.json gemini-extension.json mcp_config.json mcp.json .claude-plugin/ AGENTS.md CLAUDE.md .gitignore
  git commit -m "chore: scaffold cross-agent plugin manifests and build tooling"
  ```
  git commit -m "chore: scaffold pinterest-inspiration plugin project"
  ```

---

### Task 2: Core Types & Pinterest Mobile SSR Scraper Engine

**Files:**
- Create: `src/utils/types.ts`
- Create: `src/scraper/pinterest.ts`
- Test: `tests/scraper.test.ts`

**Interfaces:**
- Produces: `scrapePinterestInspiration(query: string, limit?: number): Promise<PinInspiration[]>`
- Types:
  ```typescript
  export interface PinImage {
    url: string;
    width: number;
    height: number;
  }

  export interface PinInspiration {
    id: string;
    dominant_color: string;
    aspect_ratio: number;
    image_url: string;       // high-res 'orig'
    preview_url: string;     // '736x'
    width: number;
    height: number;
    query: string;
  }
  ```

- [ ] **Step 1: Write the failing test for scraper parser**
  Create `tests/scraper.test.ts` testing parsing of HTML containing mock `<script id="__PWS_INITIAL_PROPS__">` JSON, verifying output length capped at `limit`, extraction of `dominant_color`, `orig` URL, and handling of malformed/empty HTML.

- [ ] **Step 2: Run test to verify it fails**
  Run: `npm test tests/scraper.test.ts`
  Expected: FAIL (modules not found)

- [ ] **Step 3: Implement `types.ts` and `src/scraper/pinterest.ts`**
  Implement `scrapePinterestInspiration` using native `fetch` with Mobile User-Agent (`Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1`), URL encoding for `query`, parsing `__PWS_INITIAL_PROPS__`, extracting top pins up to `limit` (max 10), and mapping to `PinInspiration`.

- [ ] **Step 4: Run tests to verify they pass**
  Run: `npm test tests/scraper.test.ts`
  Expected: PASS

- [ ] **Step 5: Commit**
  ```bash
  git add src/utils/types.ts src/scraper/pinterest.ts tests/scraper.test.ts
  git commit -m "feat: implement pinterest mobile SSR scraper"
  ```

---

### Task 3: In-Memory Cache and Image Downloader Utility

**Files:**
- Create: `src/scraper/cache.ts`
- Create: `src/utils/downloader.ts`
- Test: `tests/downloader.test.ts`

**Interfaces:**
- Consumes: `PinInspiration` from Task 2.
- Produces:
  - `QueryCache<T>`: TTL in-memory cache for search results.
  - `downloadPinImage(imageUrl: string, outputDir?: string): Promise<string>` (returns saved local file path).

- [ ] **Step 1: Write the failing test for cache and downloader**
  Create `tests/downloader.test.ts` verifying cache hit/miss behavior, safe output path resolution, handling HTTP 404 on image download, and writing binary data to disk.

- [ ] **Step 2: Run test to verify it fails**
  Run: `npm test tests/downloader.test.ts`
  Expected: FAIL

- [ ] **Step 3: Implement `src/scraper/cache.ts` and `src/utils/downloader.ts`**
  - `cache.ts`: Simple in-memory Map with 15-minute TTL.
  - `downloader.ts`: Downloads image buffer via `fetch`, creates `.pinterest_cache/` if no output dir specified, writes file with unique hash filename, and returns absolute path.

- [ ] **Step 4: Run tests to verify they pass**
  Run: `npm test tests/downloader.test.ts`
  Expected: PASS

- [ ] **Step 5: Commit**
  ```bash
  git add src/scraper/cache.ts src/utils/downloader.ts tests/downloader.test.ts
  git commit -m "feat: implement cache and image downloader"
  ```

---

### Task 4: MCP Server Stdio Implementation & Tool Handlers

**Files:**
- Create: `src/index.ts`
- Test: `tests/mcp-server.test.ts`

**Interfaces:**
- Consumes: `scrapePinterestInspiration` (Task 2), `downloadPinImage` (Task 3).
- Produces: Executable MCP Server exposing tools:
  - `search_pinterest_inspiration`: `{ query: string, limit?: number }`
  - `download_pin_image`: `{ image_url: string, output_dir?: string }`

- [ ] **Step 1: Write the failing test for MCP tool schemas and handlers**
  Create `tests/mcp-server.test.ts` verifying tool registrations and JSON-RPC tool response format.

- [ ] **Step 2: Run test to verify it fails**
  Run: `npm test tests/mcp-server.test.ts`
  Expected: FAIL

- [ ] **Step 3: Implement `src/index.ts`**
  Use `McpServer` from `@modelcontextprotocol/sdk/server/mcp.js` and `StdioServerTransport`. Register `search_pinterest_inspiration` and `download_pin_image` with Zod parameter schemas. Format output text with Markdown preview image links and color swatches.

- [ ] **Step 4: Run tests and build server bundle**
  Run: `npm test && npm run build`
  Expected: PASS, and `dist/index.js` generated.

- [ ] **Step 5: Commit**
  ```bash
  git add src/index.ts tests/mcp-server.test.ts
  git commit -m "feat: implement MCP server and register inspiration tools"
  ```

---

### Task 5: Antigravity Skill Definition & Design Guidance

**Files:**
- Create: `skills/pinterest-inspiration/SKILL.md`
- Create: `skills/pinterest-inspiration/references/ui-design-guide.md`
- Create: `skills/pinterest-inspiration/references/prompt-crafting.md`

**Interfaces:**
- Consumes: MCP tools `search_pinterest_inspiration` and `download_pin_image`.
- Produces: Agent workflows for visual moodboarding, UI token mapping (Tailwind/React), and Image Generation prompting (Gemini/Midjourney).

- [ ] **Step 1: Create `skills/pinterest-inspiration/SKILL.md`**
  Write frontmatter (`name: pinterest-inspiration`, `description`), activation triggers, step-by-step procedure:
  1. Formulate visual search query in English.
  2. Invoke `search_pinterest_inspiration`.
  3. Render Markdown Moodboard with image previews (`![preview](url)`) and dominant color hex pills.
  4. Branch into UI design mode or Image generation mode based on user goal.

- [ ] **Step 2: Create reference guides**
  - `ui-design-guide.md`: How to extract color schemes into Tailwind config / CSS variables, identify card/hero layout structures, and write clean components.
  - `prompt-crafting.md`: How to convert visual mood, lighting, color palette, and composition into high-fidelity image generation prompts.

- [ ] **Step 3: Verify skill formatting and link integrity**
  Ensure skill metadata conforms to Antigravity skill guidelines.

- [ ] **Step 4: Commit**
  ```bash
  git add skills/pinterest-inspiration/
  git commit -m "docs: add pinterest-inspiration skill and design references"
  ```

---

### Task 6: End-to-End Integration Verification & Documentation

**Files:**
- Create: `README.md`
- Modify: `package.json`

**Interfaces:**
- Consumes: Built `dist/index.js`, manifests, and skills.
- Produces: Complete, verified plugin ready to be enabled in Antigravity.

- [ ] **Step 1: Write integration smoke test**
  Create an end-to-end smoke test script or vitest test that spins up the MCP server, sends `tools/call` for `search_pinterest_inspiration` with a live query (or mocked live response), and verifies that image URLs, dominant color hexes, and dimensions are returned correctly.

- [ ] **Step 2: Run all tests and complete build**
  Run: `npm test && npm run build`
  Expected: All unit & integration tests pass with 0 errors.

- [ ] **Step 3: Write comprehensive `README.md`**
  Document plugin overview, capabilities, manual/global installation instructions, tool list, and example user prompts.

- [ ] **Step 4: Commit**
  ```bash
  git add README.md
  git commit -m "docs: complete plugin documentation and verification"
  ```
