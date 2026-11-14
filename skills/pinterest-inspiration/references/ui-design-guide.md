# UI/UX Design Guide: From Pinterest Moodboard to Tailwind & React

This reference guide provides actionable patterns for translating visual moodboards and `dominant_color` tokens extracted from Pinterest into production-grade web interfaces using Tailwind CSS and modern React/Next.js.

---

## 1. Palette Extraction & Semantic Mapping

When `search_pinterest_inspiration` returns a set of pins with `dominant_color` hex codes, do not use them randomly. Structure them into a coherent **60-30-10 color hierarchy**:

```
60% Dominant Base / Canvas   ──>  Backgrounds, page containers, cards
30% Secondary Structure      ──>  Borders, secondary text, muted surfaces, nav bars
10% High-Impact Accent       ──>  Primary buttons, active states, key data highlights
```

### Contrast & Tone Calibration
- **Never use pure `#000000` or `#FFFFFF`**: Pure black and white look harsh and artificial. Always tint neutrals with a hint of the dominant warmth or coolness (e.g., `#0F1115` for deep obsidian or `#FAF8F5` for warm alabaster).
- **Verify Contrast (WCAG AA)**: Ensure foreground text meets at least 4.5:1 contrast against surface backgrounds.

### Tailwind CSS Token Configuration

#### A. Tailwind CSS v4 (`@theme` in global CSS)
```css
@theme {
  /* Extracted from Pinterest Moodboard */
  --color-brand-primary: #2C1E17;
  --color-brand-secondary: #8C6546;
  --color-brand-accent: #C15C3D;
  --color-brand-accent-hover: #A74B2F;
  
  --color-surface-canvas: #F8F5F0;
  --color-surface-card: #FFFFFF;
  --color-surface-muted: #EFE9E1;
  --color-surface-border: #E2D9CC;

  --color-content-title: #1B130E;
  --color-content-body: #4A3E37;
  --color-content-muted: #7E7067;

  --font-serif-display: "Playfair Display", Georgia, serif;
  --font-sans-body: "Plus Jakarta Sans", system-ui, sans-serif;
  --font-mono-code: "JetBrains Mono", monospace;
}
```

#### B. Tailwind CSS v3 (`tailwind.config.ts`)
```typescript
import type { Config } from 'tailwindcss';

const config: Config = {
  theme: {
    extend: {
      colors: {
        brand: {
          primary: '#2C1E17',
          secondary: '#8C6546',
          accent: '#C15C3D',
        },
        surface: {
          canvas: '#F8F5F0',
          card: '#FFFFFF',
          muted: '#EFE9E1',
          border: '#E2D9CC',
        },
        content: {
          title: '#1B130E',
          body: '#4A3E37',
          muted: '#7E7067',
        }
      },
      fontFamily: {
        display: ['var(--font-serif-display)', 'serif'],
        sans: ['var(--font-sans-body)', 'sans-serif'],
      },
    },
  },
};
export default config;
```

---

## 2. Typography Pairings & Hierarchy

Pinterest design pins frequently feature sophisticated editorial typography. Match the aesthetic using proven font pairings:

| Style Archetype | Display / Heading Font | Body / UI Font | Vibe & Best Use Cases |
| :--- | :--- | :--- | :--- |
| **Warm Editorial** | *Playfair Display*, *Instrument Serif*, *Cormorant* | *Plus Jakarta Sans*, *Inter*, *Satoshi* | Artisanal products, coffee, hospitality, fashion |
| **Modern Tech Minimal** | *Geist*, *Space Grotesk*, *Cabinet Grotesk* | *Inter*, *Geist*, *System-UI* | SaaS, AI tools, developer platforms, fintech |
| **Tactile Brutalist** | *Syne*, *Clash Display*, *Monument Extended* | *JetBrains Mono*, *IBM Plex Mono* | Creative studios, modern portfolios, music, streetwear |
| **Quiet Luxury** | *Cormorant Garamond*, *Cinzel* | *Montserrat* (light), *Tenor Sans* | High-end real estate, jewelry, luxury horology |

### Typographic Rules:
1. **Tight Leading on Large Headers**: Display headers (48px+) should use `leading-[1.05]` to `leading-[1.1]` to avoid scattered text.
2. **Generous Leading on Paragraphs**: Body text should use `leading-relaxed` (1.625) or `leading-loose` (2.0) with slightly muted text (`text-content-body`).
3. **Tracking (Letter Spacing)**: Use `tracking-tight` (-0.02em) on big headers and `tracking-wider` (+0.05em) on small uppercase category badges (`text-xs uppercase tracking-widest`).

---

## 3. Pinterest-Inspired Layout Archetypes

### 1. Asymmetric Hero Section
Pinterest pins often feature large, expressive typography overlapping or juxtaposed against high-aspect ratio imagery.

```tsx
export function AsymmetricHero() {
  return (
    <section className="relative min-h-[85vh] bg-surface-canvas px-6 py-20 md:px-16 flex flex-col justify-center overflow-hidden">
      <div className="max-w-6xl mx-auto w-full grid grid-cols-1 lg:grid-cols-12 gap-12 items-center">
        {/* Left Column: Editorial Headline & Actions */}
        <div className="lg:col-span-7 space-y-8 z-10">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-surface-muted text-content-body text-xs font-medium tracking-wide uppercase">
            <span className="w-2 h-2 rounded-full bg-brand-accent animate-pulse" />
            Seasonal Batch 2026
          </div>
          <h1 className="font-display text-5xl md:text-7xl font-bold tracking-tight text-content-title leading-[1.05]">
            Crafted with ritual. <br />
            <span className="italic font-normal text-brand-secondary">Served with stillness.</span>
          </h1>
          <p className="text-content-body text-lg max-w-xl leading-relaxed">
            Directly sourced micro-lot beans roasted in small ceramic drums. Experience coffee in its purest, most deliberate form.
          </p>
          <div className="flex flex-wrap items-center gap-4 pt-2">
            <button className="px-7 py-3.5 rounded-full bg-brand-primary text-white font-medium hover:bg-brand-secondary transition-all duration-300 shadow-sm hover:shadow-md">
              Explore Our Harvest
            </button>
            <button className="px-7 py-3.5 rounded-full border border-surface-border text-content-title font-medium hover:bg-surface-muted transition-colors">
              The Philosophy
            </button>
          </div>
        </div>

        {/* Right Column: Visual Pin Framing */}
        <div className="lg:col-span-5 relative">
          <div className="relative aspect-[3/4] w-full rounded-2xl overflow-hidden shadow-2xl border border-surface-border/50">
            <img 
              src="https://images.unsplash.com/photo-1514432324607-a09d9b4aefdd?q=80&w=1080&auto=format&fit=crop" 
              alt="Artisanal pour over coffee" 
              className="w-full h-full object-cover transform hover:scale-105 transition-transform duration-700 ease-out"
            />
            {/* Color accent pill overlay */}
            <div className="absolute bottom-4 left-4 right-4 p-4 rounded-xl bg-surface-card/90 backdrop-blur-md border border-white/40 flex items-center justify-between">
              <div>
                <p className="text-xs uppercase tracking-wider text-content-muted">Origin Harvest</p>
                <p className="text-sm font-semibold text-content-title">Yirgacheffe Misty Valley</p>
              </div>
              <span className="px-2.5 py-1 text-xs font-mono rounded bg-brand-accent/10 text-brand-accent font-semibold">
                #C15C3D
              </span>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
```

---

### 2. The Asymmetric Bento Grid
Rather than rigid 3x3 uniform boxes, emulate Pinterest boards with varying column spans and aspect ratios:

```tsx
export function VisualBentoGrid() {
  return (
    <section className="py-24 bg-surface-canvas px-6 md:px-16">
      <div className="max-w-6xl mx-auto space-y-12">
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-6">
          <div>
            <span className="text-xs uppercase tracking-widest text-brand-accent font-semibold">Visual Archives</span>
            <h2 className="font-display text-4xl font-bold text-content-title mt-2">Design Collections</h2>
          </div>
          <p className="text-content-muted max-w-md text-sm leading-relaxed">
            Curated visual components directly influenced by our Pinterest inspiration moodboards.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Card 1: Tall Feature Card (Row Span 2) */}
          <div className="md:row-span-2 group relative overflow-hidden rounded-2xl bg-surface-card p-8 border border-surface-border flex flex-col justify-between hover:shadow-lg transition-all duration-300">
            <div className="space-y-4">
              <span className="inline-block px-3 py-1 rounded-full text-xs font-mono bg-surface-muted text-brand-primary">
                Aesthetic 01
              </span>
              <h3 className="font-display text-2xl font-bold text-content-title">Organic Earth & Terracotta</h3>
              <p className="text-sm text-content-body leading-relaxed">
                Textured paper substrates paired with earthy terracotta clay accents and warm stone typography.
              </p>
            </div>
            <div className="mt-8 aspect-[4/5] rounded-xl overflow-hidden bg-surface-muted">
              <div className="w-full h-full bg-gradient-to-br from-[#E2D9CC] via-[#C15C3D]/20 to-[#2C1E17]/10 flex items-center justify-center p-6 text-center text-xs text-content-muted">
                3:4 Visual Card
              </div>
            </div>
          </div>

          {/* Card 2: Wide Card (Col Span 2) */}
          <div className="md:col-span-2 rounded-2xl bg-brand-primary text-white p-8 relative overflow-hidden flex flex-col md:flex-row items-center justify-between gap-6">
            <div className="space-y-3 max-w-md">
              <span className="text-xs font-mono uppercase tracking-widest text-brand-accent">Highlight</span>
              <h3 className="font-display text-3xl font-semibold">Monochrome Editorial Rhythm</h3>
              <p className="text-sm text-surface-muted/80 leading-relaxed">
                Balanced typography with high-contrast negative space and precise Swiss grid alignment.
              </p>
            </div>
            <div className="w-24 h-24 rounded-full border border-white/20 flex items-center justify-center shrink-0">
              <span className="text-2xl font-serif italic">#2C1E17</span>
            </div>
          </div>

          {/* Card 3: Standard Metric Card */}
          <div className="rounded-2xl bg-surface-card p-6 border border-surface-border hover:border-brand-secondary/40 transition-colors">
            <p className="text-xs font-mono text-content-muted">DOMINANT RATIO</p>
            <p className="text-3xl font-bold text-content-title mt-2 font-display">16:9 / 3:4</p>
            <p className="text-xs text-content-body mt-2">Dynamic rhythm between panoramic headers and editorial portrait pins.</p>
          </div>

          {/* Card 4: Accent Color Card */}
          <div className="rounded-2xl bg-surface-card p-6 border border-surface-border hover:border-brand-accent/40 transition-colors">
            <p className="text-xs font-mono text-content-muted">PRIMARY ACCENT</p>
            <div className="flex items-center gap-3 mt-2">
              <div className="w-6 h-6 rounded-full bg-brand-accent shadow-inner" />
              <p className="text-2xl font-bold text-content-title font-mono">#C15C3D</p>
            </div>
            <p className="text-xs text-content-body mt-2">Warm terracotta button states and micro-indicators.</p>
          </div>
        </div>
      </div>
    </section>
  );
}
```

---

## 4. Polished Micro-Interactions & Styling Cues

To give interfaces the same premium feel as high-ranking Pinterest pins:
1. **Soft Border Highlights**: Use `border border-white/10 dark:border-white/5` coupled with `shadow-sm hover:shadow-xl hover:-translate-y-0.5 transition-all duration-300`.
2. **Subtle Glassmorphism**: Use `bg-surface-card/80 backdrop-blur-md` instead of opaque white boxes.
3. **Color Badges**: Display hex values or category tags as pill badges:
   ```html
   <span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-mono bg-[#8C6546]/10 text-[#8C6546]">
     <span class="w-2 h-2 rounded-full bg-[#8C6546]"></span>
     #8C6546
   </span>
   ```
4. **Organic Image Framing**: Use `rounded-2xl` or `rounded-3xl` with `overflow-hidden` and a slow hover scale (`hover:scale-105 transition-transform duration-700 ease-out`).
