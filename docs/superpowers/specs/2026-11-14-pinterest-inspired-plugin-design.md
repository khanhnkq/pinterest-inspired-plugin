# Pinterest Inspiration Plugin Design Document

- **Date:** 2026-11-14
- **Status:** Reviewed & Ready for Implementation Planning
- **Target Platform:** Antigravity Plugin Ecosystem / Model Context Protocol (MCP)

---

## 1. Intent and The Why

### Intent
Xây dựng một plugin cho Agent (Antigravity/MCP) có khả năng tự động cào (scrape) 5–10 hình ảnh cảm hứng từ Pinterest dựa theo từ khóa/phong cách, trích xuất các thuộc tính thị giác (ảnh HD gốc, mã màu chủ đạo, tỷ lệ khung hình), và đưa vào ngữ cảnh của Agent làm tư liệu tham chiếu thiết kế UI, viết code giao diện, sinh prompt tạo ảnh và sản xuất nội dung visual.

### The Why
- Khi thiết kế giao diện (UI/UX) hoặc tạo hình ảnh AI (Image Generation), các mô tả bằng văn bản thường trừu tượng và dễ dẫn đến kết quả rập khuôn (AI slop / generic UI).
- Pinterest là kho lưu trữ cảm hứng thị giác phong phú nhất về UI concepts, moodboards, color palettes, photography lighting, và illustration styles.
- Việc Agent có thể tự tìm kiếm 5–10 hình ảnh tham chiếu thực tế trên Pinterest giúp Agent nắm bắt phong cách thị giác ngay trong phiên làm việc, từ đó tạo ra thiết kế hoặc prompt tạo ảnh có tính thẩm mỹ và độ hoàn thiện cao hơn.

---

## 2. Goals, Non-Goals, Anti-Goals

### Goals
1. **Tìm kiếm cảm hứng không cần API token:** Cào trực tiếp dữ liệu công khai từ Pinterest dựa theo từ khóa/chủ đề mà không yêu cầu user phải đăng ký Pinterest Developer API.
2. **Thu gọn số lượng lấy (tối đa 10 ảnh):** Lấy đúng 5–10 kết quả chất lượng cao nhất cho mỗi query để tối ưu tốc độ (< 1s), tiết kiệm context window của LLM và tránh bị Pinterest rate limit.
3. **Trích xuất Visual Reference Tokens:** Trả về dữ liệu thị giác tối ưu:
   - Link ảnh gốc độ phân giải cao (`orig` và `736x`).
   - Mã màu chủ đạo (`dominant_color` hex, ví dụ: `#2c3e50`).
   - Tỷ lệ khung hình (`aspect_ratio` / width, height).
4. **Hỗ trợ tải ảnh về local:** Cung cấp tool tải ảnh về thư mục dự án / artifact để Agent dùng vision model phân tích hoặc làm tài nguyên mẫu.
5. **Skill định hướng tư duy sáng tạo:** Cung cấp Skill (`pinterest-inspiration`) hướng dẫn Agent cách kết nối dữ liệu ảnh tham chiếu vào:
   - Thiết kế giao diện & sinh code UI (HTML/Tailwind, React).
   - Sinh prompt tạo ảnh AI (Gemini ImageGen, Midjourney, DALL-E) chuẩn aesthetic.

### Non-Goals
1. **Không hỗ trợ tương tác tài khoản:** Không đăng nhập tài khoản Pinterest, không tự động bấm "Pin/Save", tạo board hoặc follow người dùng.
2. **Không cào hàng loạt quy mô lớn (Mass Bulk Scraping):** Không cào hàng nghìn ảnh hay cào toàn bộ profile/board.
3. **Không xử lý bypass CAPTCHA bằng bên thứ ba:** Không tích hợp các dịch vụ giải captcha trả phí.

### Anti-Goals
1. **Không sử dụng Headless Browser cồng kềnh (No Puppeteer/Chromium):** Tránh việc tải 400MB Chrome binary làm nặng môi trường của người dùng và làm chậm tốc độ phản hồi của Agent.
2. **Không làm nghẽn Context của Agent:** Không nhồi nhét dữ liệu HTML rác vào prompt của Agent. Chỉ trả về danh sách JSON tinh gọn gồm các thông số thị giác cốt lõi.

---

## 3. Constraints & Technical Findings

1. **Pinterest SSR Behavior (Lockdown Mitigation):**
   - Trên desktop user-agent không đăng nhập, Pinterest trả về App Shell rỗng.
   - Khi sử dụng Mobile User-Agent (`iPhone / Safari`), Pinterest SSR trả về đầy đủ 25 pins trong thẻ `<script id="__PWS_INITIAL_PROPS__">`, bao gồm:
     - Ảnh HD: `images.orig.url` (ảnh gốc sắc nét nhất) và `images['736x'].url`.
     - Mã màu: `dominant_color` (mã hex chuẩn từ Pinterest).
     - Kích thước: `images.orig.width`, `images.orig.height`.
2. **Visual-First Payload:**
   - Trong chế độ unauthenticated lockdown, Pinterest lược bỏ text title và description dài dòng. Điều này hoàn toàn phù hợp với mục tiêu "Visual Inspiration", tập trung 100% vào hình ảnh chất lượng cao và bảng màu sắc.
3. **Môi trường thực thi:** Node.js (TypeScript) stdio transport, tích hợp mượt mà vào Antigravity (`plugin.json`, `mcp_config.json`, `skills/`).

---

## 4. Approaches Considered & Selected

- **PA 1 - Static HTML Regex:** Dễ gãy khi đổi markup, thiếu mã màu.
- **PA 2 - Headless Browser (Playwright):** Quá nặng, chậm (3–5s), ngốn RAM.
- **PA 3 - Fast Mobile SSR Extractor (ĐÃ CHỌN):**
  - Gửi 1 HTTP GET request với Mobile User-Agent tới `https://www.pinterest.com/search/pins/?q=<query>`.
  - Trích xuất JSON từ thẻ `<script id="__PWS_INITIAL_PROPS__">`.
  - Lấy top 5–10 pins chất lượng cao nhất.
  - Phản hồi cực nhanh (< 800ms), 0 MB browser overhead, cung cấp chính xác ảnh gốc HD và dominant color hex.

---

## 5. Architecture & Components

```
pinterest-inspired-plugin/
├── plugin.json                 # Manifest khai báo plugin cho Antigravity
├── mcp_config.json             # Khai báo stdio MCP server
├── package.json                # Dependencies (@modelcontextprotocol/sdk, typescript, tsup)
├── tsconfig.json               # Cấu hình TypeScript
├── src/
│   ├── index.ts                # MCP Server entry point (đăng ký tools)
│   ├── scraper/
│   │   ├── pinterest.ts        # Logic fetch & parse Mobile SSR pins
│   │   └── cache.ts            # In-memory cache cho queries trùng lặp
│   └── utils/
│       ├── downloader.ts       # Utility tải ảnh về local workspace
│       └── types.ts            # Type definitions cho Pin, Image, DominantColor
├── skills/
│   └── pinterest-inspiration/
│       ├── SKILL.md            # Skill hướng dẫn Agent workflow tham chiếu
│       └── references/
│           ├── ui-design-guide.md     # Bóc tách grid, spacing, color palette vào Tailwind/React
│           └── prompt-crafting.md     # Tạo prompt ảnh AI từ moodboard và lighting
└── README.md                   # Hướng dẫn sử dụng và cài đặt
```

### Tools cung cấp qua MCP:
1. `search_pinterest_inspiration`:
   - Input: `query` (chuỗi từ khóa tiếng Anh/Việt), `limit` (mặc định: 8, tối đa: 10).
   - Output: Danh sách pins gồm `id`, `image_url` (orig), `preview_url` (736x), `dominant_color` (hex), `width`, `height`, `aspect_ratio`.
2. `download_pin_image`:
   - Input: `image_url`, `output_path` (tùy chọn; mặc định lưu vào `.pinterest_cache/` trong workspace hiện tại).
   - Output: File path cục bộ của ảnh đã tải để Agent dùng Vision model kiểm tra.

### Skill `pinterest-inspiration`:
- Hướng dẫn Agent:
  1. Chuyển đổi yêu cầu người dùng thành từ khóa tìm kiếm trực quan bằng tiếng Anh.
  2. Gọi `search_pinterest_inspiration(query, limit=8)`.
  3. Trình bày Moodboard tổng hợp (bảng màu, phong cách chủ đạo).
  4. Hướng dẫn áp dụng trực tiếp vào:
     - **UI Code**: Mapping dominant color vào Tailwind theme, thiết kế layout card/hero.
     - **Image Gen**: Tạo prompt chi tiết gồm Style, Lighting, Palette, Framing cho Gemini/Midjourney.

---

## 6. Engineering Decisions (Builder Calls)

1. **Thư viện HTTP:** Sử dụng native `fetch` của Node.js (Node 18+ đã có sẵn, không cần thêm dependency bên ngoài).
2. **Thư viện MCP:** `@modelcontextprotocol/sdk` phiên bản mới nhất với StdioServerTransport.
3. **Thư mục lưu trữ ảnh:** Mặc định lưu vào `.pinterest_cache/` tại workspace hiện tại (tự động thêm vào `.gitignore` nếu có git repo).
4. **Xử lý lỗi chặn (Rate Limit / 403):** Cơ chế Fail-Fast rõ ràng, trả về thông báo lỗi thân thiện để Agent biết và thử lại với từ khóa khác hoặc chờ một lát.
