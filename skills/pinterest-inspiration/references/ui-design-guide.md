# UI/UX Design Guide: From Pinterest Moodboards to Anti-Slop Production Code

This master guide bridges raw visual tokens extracted from Pinterest with **`design-taste-frontend`** (anti-slop principles) and **`web-design-guidelines`** (Vercel accessibility standards).

---

## 1. Palette Extraction & Semantic Mapping

When `search_pinterest_inspiration` returns pins with `dominant_color` hex codes, map them into a coherent **60-30-10 color hierarchy**:

```
60% Dominant Base / Canvas   ──>  Backgrounds, page containers, cards
30% Secondary Structure      ──>  Borders, secondary text, muted surfaces, nav bars
10% High-Impact Accent       ──>  Primary buttons, active states, key data highlights
```

### Contrast & Tone Calibration (WCAG AA Compliance)
- **Never use pure `#000000` or `#FFFFFF`**: Pure black and white look harsh and artificial. Always tint neutrals with a hint of the dominant warmth or coolness (e.g., `#14100E` for deep roasted espresso or `#FBF9F5` for warm oat linen).
- **Verify Contrast (WCAG AA 4.5:1)**: Body copy must maintain at least 4.5:1 contrast against surface backgrounds. Large headlines must maintain at least 3:1 contrast.

### Tailwind CSS Token Configuration

#### Tailwind CSS v4 (`@theme` in global CSS)
```css
@theme {
  /* Extracted from Pinterest Moodboard */
  --color-brand-primary: #6A4E37;
  --color-brand-secondary: #93725B;
  --color-brand-accent: #CEAA8A;
  --color-brand-dark: #211813;
  
  --color-surface-canvas: #FBF9F5;
  --color-surface-card: #FFFFFF;
  --color-surface-muted: #F3EFEA;
  --color-surface-border: #E8DFD5;

  --color-content-title: #211813;
  --color-content-body: #53453C;
  --color-content-muted: #7E7067;

  --font-serif-display: "Cormorant Garamond", Georgia, serif;
  --font-sans-body: "Plus Jakarta Sans", system-ui, sans-serif;
  --font-mono-code: "JetBrains Mono", monospace;
}
```

---

## 2. The Anti-Slop Frontend Philosophy (`design-taste-frontend`)

### A. The One-Line Design Read
Before writing code, state clearly:  
`"Reading this as: <page kind> for <audience>, with a <vibe> language, leaning toward <aesthetic family>."`

### B. The Three Dials
Configure the three core variables to drive layout, motion, and typography:
- **`DESIGN_VARIANCE: 8`** (1 = Symmetrical Grid, 10 = Broken Grid / Kinetic Editorial)
- **`MOTION_INTENSITY: 5`** (1 = Static, 10 = Physics-based Cinematic)
- **`VISUAL_DENSITY: 4`** (1 = Gallery Airy, 10 = Data-Packed Cockpit)

### C. Forbidden AI Tells (Banned Patterns)
1. ❌ **No AI-Purple/Cyan Gradients**: Never default to `from-purple-600 to-indigo-600` or blue mesh gradients.
2. ❌ **No Inter + Slate-900 Default**: Reach for distinct pairings like *Cormorant Garamond* / *Instrument Serif* with *Plus Jakarta Sans* or *Geist*.
3. ❌ **No Cookie-Cutter 3-Column Card Grids**: Use asymmetric bento arrangements, staggered heights, and contrasting card scales.
4. ❌ **No Naked Centered Heroes**: Ground hero sections with tangible typography anchors, asymmetric imagery, or interactive proof points.

---

## 3. Web Interface Guidelines & Accessibility (`web-design-guidelines`)

Every component synthesized from Pinterest inspiration must pass these accessibility rules:

1. **Focus States**: Interactive elements must feature visible focus rings using `focus-visible:ring-2 focus-visible:ring-offset-2`. Never remove outlines without providing a visible focus ring.
2. **Keyboard Navigation & Skip Link**: Provide a skip-to-content link:
   ```html
   <a href="#main" class="sr-only focus:not-sr-only focus:absolute focus:top-4 focus:left-4 z-50 bg-[#211813] text-[#FBF9F5] px-4 py-2 rounded">
     Skip to main content
   </a>
   ```
3. **Semantic HTML**: Use `<button>` for actions and `<a>` for navigation. Do not use `<div onClick>`.
4. **Layout Stability (Prevent CLS)**: Explicitly declare `width` and `height` on all `<img>` tags.
5. **Reduced Motion**: Respect `prefers-reduced-motion`:
   ```css
   @media (prefers-reduced-motion: reduce) {
     * { animation-duration: 0.01ms !important; transition-duration: 0.01ms !important; }
   }
   ```
6. **Typographic Polish**:
   - Use unicode ellipsis `…` instead of `...`.
   - Use curly quotes `“` `”`.
   - Use `&nbsp;` between numbers and units (e.g. `12&nbsp;oz`, `250&nbsp;g`).

---

## 4. Production Layout Implementation (Asymmetric Editorial Hero)

```tsx
export function EditorialHero() {
  return (
    <section className="relative min-h-[90vh] bg-[#FBF9F5] text-[#211813] px-6 py-20 lg:px-16 flex flex-col justify-center">
      <div className="max-w-7xl mx-auto w-full grid grid-cols-1 lg:grid-cols-12 gap-12 items-center">
        {/* Left Column: Typographic Narrative */}
        <div className="lg:col-span-7 space-y-8">
          <div className="inline-flex items-center gap-2.5 px-3.5 py-1.5 rounded-full bg-[#F3EFEA] border border-[#E8DFD5] text-[#6A4E37] text-xs font-mono tracking-wider uppercase">
            <span className="w-2 h-2 rounded-full bg-[#6A4E37] animate-pulse" aria-hidden="true" />
            Seasonal Micro-Lot Roast • 2026
          </div>
          <h1 className="font-serif text-5xl md:text-7xl lg:text-8xl font-light tracking-tight leading-[1.02] text-balance">
            Roasted slowly. <br />
            <span className="italic font-normal text-[#93725B]">Served with quiet intent.</span>
          </h1>
          <p className="text-[#53453C] text-lg max-w-xl font-sans leading-relaxed text-pretty">
            Direct-trade Ethiopian Yirgacheffe and Colombian Gesha roasted in small ceramic drum batches.
          </p>
          <div className="flex flex-wrap items-center gap-4 pt-2">
            <button className="px-8 py-4 rounded-full bg-[#6A4E37] text-[#FBF9F5] font-sans font-medium text-sm tracking-wide uppercase hover:bg-[#211813] focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-[#6A4E37] transition-colors duration-200">
              Explore The Harvest
            </button>
            <a href="#roastery" className="px-8 py-4 rounded-full border border-[#E8DFD5] text-[#211813] font-sans font-medium text-sm tracking-wide uppercase hover:bg-[#F3EFEA] focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-[#6A4E37] transition-colors duration-200">
              Roasting Protocol
            </a>
          </div>
        </div>

        {/* Right Column: Asymmetric Double Pin Imagery */}
        <div className="lg:col-span-5 grid grid-cols-2 gap-4">
          <div className="aspect-[3/4] rounded-2xl overflow-hidden shadow-xl border border-[#E8DFD5]">
            <img 
              src="https://images.unsplash.com/photo-1514432324607-a09d9b4aefdd?q=80&w=800" 
              alt="Artisanal pour over brew" 
              width={800} 
              height={1067} 
              className="w-full h-full object-cover hover:scale-105 transition-transform duration-700 ease-out"
              fetchpriority="high"
            />
          </div>
          <div className="aspect-[3/4] rounded-2xl overflow-hidden shadow-xl border border-[#E8DFD5] translate-y-8">
            <img 
              src="https://images.unsplash.com/photo-1447933601403-0c6688de566e?q=80&w=800" 
              alt="Whole coffee roasted beans" 
              width={800} 
              height={1067} 
              className="w-full h-full object-cover hover:scale-105 transition-transform duration-700 ease-out"
              loading="lazy"
            />
          </div>
        </div>
      </div>
    </section>
  );
}
```
