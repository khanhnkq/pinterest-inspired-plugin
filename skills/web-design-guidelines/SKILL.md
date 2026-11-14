---
name: web-design-guidelines
description: Review UI code for Web Interface Guidelines compliance and accessibility. Use when asked to "review my UI", "check accessibility", "audit design", "review UX", or "check my site against best practices".
metadata:
  author: vercel-labs
  version: "1.0.0"
  argument-hint: <file-or-pattern>
---

# Web Interface Guidelines & Accessibility Standards

Comprehensive design engineering and accessibility rules for web interfaces. Ensures high contrast, zero-jank performance, keyboard accessibility, semantic HTML, and responsive stability.

## Rules & Directives

### 1. Accessibility & Semantics
- **Icon-only buttons**: Always provide an explicit `aria-label`.
- **Form controls**: Always pair with a `<label>` or descriptive `aria-label`.
- **Keyboard navigation**: Interactive elements must handle keyboard events (`onKeyDown` / `onKeyUp` for Enter/Space).
- **Semantics first**: Use `<button>` for actions, `<a>`/`<Link>` for navigation. Never `<div onClick>`.
- **Images**: Require descriptive `alt` text (or `alt=""` if purely decorative).
- **Decorative icons**: Mark with `aria-hidden="true"`.
- **Async updates**: Dynamic notifications, toasts, and validation states require `aria-live="polite"`.
- **Headings & Hierarchy**: Logical hierarchy from `<h1>` down to `<h6>`. Include a skip link for main content (`<a href="#main" class="sr-only focus:not-sr-only">Skip to content</a>`).
- **Anchor targets**: Add `scroll-margin-top` on heading anchors to prevent fixed headers from obscuring text.

### 2. Focus States & Keyboard Interactions
- **Visible focus rings**: Interactive elements must feature visible focus rings via `:focus-visible` (e.g., `focus-visible:ring-2 focus-visible:ring-offset-2`).
- **No focus removal**: Never apply `outline: none` or Tailwind `outline-none` without an immediate, visible focus-visible replacement.
- **Group focus**: Use `:focus-within` for compound inputs and card groups.
- **Header occlusion**: Sticky headers, floating bars, or drawers must never obscure the currently focused element.

### 3. Forms & Inputs
- **Autofill support**: Inputs require `autocomplete` attributes and descriptive `name` tags.
- **Mobile keyboards**: Use appropriate `type` (`email`, `tel`, `url`, `number`) and `inputmode`.
- **Paste integrity**: Never prevent pasting (`onPaste` + `preventDefault` is strictly forbidden).
- **Hit targets**: Clickable labels (`htmlFor` or wrapping controls). Minimum 44x44px touch hit target for mobile.
- **Spellcheck**: Disable spellcheck on emails, discount codes, usernames (`spellCheck={false}`).
- **Button states**: Keep submit buttons enabled until network submission begins; display loading spinner with aria status.
- **Inline errors**: Display validation errors adjacent to fields; move focus to the first invalid field upon failed submission.
- **Placeholders**: End placeholders with `…` and show an exemplary format.

### 4. Animation & Motion Safety
- **Reduced motion**: Respect `prefers-reduced-motion` media queries; provide static or subtle opacity-only fallbacks.
- **Compositor properties**: Only animate `transform` and `opacity` to avoid layout recalculation thrashing.
- **Explicit transitions**: Never use `transition: all`—always list explicit properties (e.g., `transition-colors`, `transition-transform duration-200`).
- **Interruptible animations**: Allow user actions to interrupt or override active transitions smoothly.
- **Looping motion**: Autoplay animations exceeding 5 seconds must include pause/stop controls.

### 5. Typography & Editorial Polish
- **Ellipses**: Use actual unicode ellipsis `…` instead of three dots `...`.
- **Quotes**: Use typographic curly quotes `“` `”` / `‘` `’` rather than straight quotes `"` `'`.
- **Non-breaking spaces**: Bind numbers and units or shortcuts with `&nbsp;` (e.g., `10&nbsp;MB`, `⌘&nbsp;K`).
- **Widow prevention**: Use `text-wrap: balance` on hero headlines and `text-wrap: pretty` on body paragraphs.
- **Tabular figures**: Apply `tabular-nums` / `font-variant-numeric: tabular-nums` to tables, price tags, and countdown counters.

### 6. Contrast & Visual Hierarchy
- **WCAG AA Compliance**: Maintain a minimum contrast ratio of 4.5:1 for body copy and 3:1 for large headlines.
- **Interactive contrast**: Hover, active, and focused states must exhibit higher contrast than resting states.
- **Intentional background matching**: Set `<meta name="theme-color">` and `color-scheme` to align with the active canvas color.

### 7. Performance & Resource Loading
- **Image dimensions**: Explicit `width` and `height` attributes to prevent Cumulative Layout Shift (CLS).
- **Lazy loading**: Below-fold images must specify `loading="lazy"`. Above-fold hero images use `fetchpriority="high"`.
- **Media alternatives**: Prefer compressed `<video autoplay muted loop playsinline>` over bloated GIFs.
- **Font preloading**: Preload critical brand display typefaces with `font-display: swap`.

---

## Review Output Format

When reviewing code, output findings grouped by file in `file:line` syntax:

```text
## src/components/Hero.tsx

src/components/Hero.tsx:42 - icon button missing aria-label
src/components/Hero.tsx:55 - animation missing prefers-reduced-motion
src/components/Hero.tsx:67 - transition: all → list properties explicitly

## src/components/ProductCard.tsx

✓ pass (contrast ratio 6.2:1, semantic button, lazy loaded image with explicit dimensions)
```
