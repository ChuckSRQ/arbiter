# Arbiter Redesign — Design #102 Implementation Plan

## Goal

Redesign Arbiter's UI to match design #102: a dark-navy political briefing terminal
with electric blue (market data) and warm amber (analyst judgment) — portrait-first,
system-ui, three-layer elevation, with the price row as the visual anchor.

---

## Current State

- Background: radial gradient purple/blue (#1E245F → #0A0D2A → #070819)
- Fonts: Geist (loaded via `next/font/google`)
- Layout: wide multi-column desktop grid — 5 sections (Today/Edge, Opportunities, Portfolio, Evidence, Archive)
- Color tokens: scattered inline Tailwind, no CSS variables for design tokens
- Price display: flat grey boxes, 4-column metrics grid per opportunity
- Sections use large rounded-[28px] cards with gradient fills

---

## Design Target (Design #102)

| Token | Value | Usage |
|-------|-------|-------|
| Primary bg | `#0D0F1A` | Page background (flat, no gradient) |
| Secondary bg | `#141828` | Card surface |
| Tertiary/amber | `#FBBF24` | Marcus prices, Edge delta, Analysis labels |
| Blue accent | `#3B82F6` | Structural: badges, headers, Market price values |
| Blue light | `#93C5FD` | Market price values |
| Amber light | `#FDE68A` | Marcus price and Edge values |
| Surface/deep | `#05081A` | Price boxes (3rd elevation layer) |
| Card bg | `#141828` | Card surface |
| Body text | `#E8E4DC` | Warm cream body copy |
| On-primary | `#F1F5F9` | Race titles, header titles |

- Font: `System-ui, -apple-system, BlinkMacSystemFont, sans-serif` — no external loading
- Layout: Portrait-first (450×800px primary), single-column stacked cards
- Radius: `lg`=20px (cards), `md`=12px (price boxes), `sm`=6px (badges/links)
- Elevation: page (#0D0F1A) → card (#141828) → price box (#05081A with glow borders)
- Price row: Market (blue glow) | Edge (amber glow, larger) | Marcus (amber glow)
- Card anatomy (top to bottom): badge → race title + election date → context paragraph → price row → analysis → source links

---

## Files to Change

1. **`src/app/globals.css`** — replace entirely
2. **`src/app/layout.tsx`** — remove Geist font loading, update body background
3. **`src/app/page.tsx`** — replace entirely (new component structure)

No new components files needed — everything inlined in page.tsx per the briefing-card pattern.

---

## Step-by-Step Implementation

### Step 1: `globals.css` — Design tokens and base styles

Replace the current file completely. Define CSS custom properties for all design tokens,
set the flat navy background on `body`, remove the radial gradient and Geist variable
references, set `font-family: system-ui`.

```css
:root {
  --color-primary: #0D0F1A;
  --color-secondary: #141828;
  --color-surface: #05081A;
  --color-blue: #3B82F6;
  --color-blue-light: #93C5FD;
  --color-amber: #FBBF24;
  --color-amber-light: #FDE68A;
  --color-amber-label: #FCD34D;
  --color-blue-label: #60A5FA;
  --color-body: #E8E4DC;
  --color-heading: #F1F5F9;
  --rounded-lg: 20px;
  --rounded-md: 12px;
  --rounded-sm: 6px;
}
```

Key rules:
- `body`: `background: var(--color-primary)`, `color: var(--color-body)`, `font-family: system-ui`
- Remove all gradient backgrounds
- `::selection`: blue highlight
- No external font imports

### Step 2: `layout.tsx` — Strip Geist

- Remove `Geist` and `Geist_Mono` imports from `next/font/google`
- Remove `geistSans.variable` and `geistMono.variable` from `<html>` className
- Body keeps `flex flex-col min-h-full` but loses font variable references
- Title/metadata unchanged

### Step 3: `page.tsx` — New component structure

Full rewrite. Sections:

**A. Sticky header bar (`card-header`)**
- Background: `#0D0F1A` (on-primary), text: `#F1F5F9`
- Left: "Arbiter" wordmark in `display` size (22px bold)
- Right: live indicator dot (amber pulse) + report date + election count badge
- Sticky top, `z-index: 50`

**B. Report thesis strip**
- Single line: report thesis text
- Background: `#141828`, padding 16px, full-width
- Not a card — just a colored band below the header

**C. Opportunity cards (portrait stack)**
One `<article>` per opportunity. Structure (top → bottom):

1. **Badge row**: market ticker badge (blue) + market type badge (blue-light)
2. **Race title** (22px bold, #F1F5F9) + election date on new line (blue, 14px)
3. **Context paragraph** (15px, #E8E4DC, 1 paragraph max)
4. **Price row** (flex row, centered):
   - `price-box-market`: blue border/glow, label "Market" (blue-label), value in `#93C5FD`
   - `price-box-edge`: amber border/glow (larger, 14px padding), label "Edge" in `#FCD34D`, value in `#FDE68A`
   - `price-box-marcus`: amber border/glow, label "Marcus" (blue-label or amber), value in `#FDE68A`
5. **Analysis section**: label "Analysis" in `#FCD34D`, paragraph in `#E8E4DC`
6. **Source links**: inline `source-link` pills in a flex-wrap row
7. **"What would change the view"** strip: amber-tinted box, same as design spec

**Caveat — no-trade state:**
If `topOpportunities.length === 0`, render a centered "No trade today" card:
- Large heading in white, sub-text in body color
- Pass count badge
- Short paragraph from `report.summary`

**D. Portfolio section**
- Section header label ("Portfolio", uppercase, blue)
- Same card anatomy as opportunity cards, but for each position
- Price row shows: Market price | P&L | Exposure (no Marcus/Edge in portfolio)
- Action badge (Hold/Reduce/Exit) in top-right corner

**E. Archive strip**
- Horizontal scroll of prior report cards (compact)
- Each: date, headline, verdict one-liner
- Or: if empty, "No prior reports" state

**Sections removed from current build:**
- Evidence section (polling evidence) — removed per new design scope; can be added back later
- Nav links section (Today/Opportunities/Portfolio/Evidence/Archive anchor links)
- Multi-column stat cards in header

---

## Verification Steps

1. `npm run build` — must pass with zero errors
2. `npm run lint` — zero warnings
3. Open in browser (Chrome, 450px wide) — portrait layout looks correct
4. Open at 1200px wide — cards still look good (portrait-first but not broken on desktop)
5. Check all 3 price boxes render with correct glow borders
6. Check "no trade today" state renders when opportunities array is empty

---

## Risks and Tradeoffs

- **Scope creep**: The current build has 5 sections; the new design has 2–3. Deliberately
  dropping Evidence and Archive for v1. Can add back as separate cards later.
- **Data model mismatch**: The new card layout assumes specific fields (market type,
  election date, Marcus fair value). Need to verify `getTopOpportunities()` returns
  fields that map cleanly. If not, update `dashboard-data.ts` / `report-schema.ts`.
- **Portrait-first**: Carlos indicated portrait is primary. Desktop layout is
  secondary — the cards should not look broken at 1200px but the primary QA target
  is 450×800.
- **Font rendering**: System-ui varies by OS. The design intentionally accepts this
  trade-off for zero font-loading overhead and offline reliability.

---

## Open Questions

1. Does the new design drop the Evidence section entirely, or should it appear as a
   separate card type below opportunities?
2. Should Portfolio cards keep the action badge (Hold/Reduce/Exit) in the top-right,
   or move to a price-row element like the opportunities cards?
3. Is the "What would change the view" strip wanted on every card, or only on
   opportunity cards (not portfolio review cards)?
4. The current design has a live portfolio indicator. Should that stay in the sticky
   header, or move into the portfolio section itself?
