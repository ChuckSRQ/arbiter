# Arbiter Redesign Roadmap — Design #102
### 5-Session Delegation to gh copilot (GPT-5.4)

---

## What "drop everything else" means

The current build has 5 page sections (Today/Edge, Opportunities, Portfolio, Evidence, Archive)
rendered in a wide multi-column desktop layout with gradient backgrounds and Geist fonts.

Design #102 collapses all of that into:

- **One app**: a vertical stack of briefing cards
- **Each card is self-contained**: badge → title → date → context → price row → analysis → sources
- **Only three card types exist**: opportunity cards, no-trade cards, and portfolio position cards
- **Everything else is gone**: nav links, stat cards, evidence shelf, archive grid, section dividers, gradient fills

The data model (`report-schema.ts`) stays — it already has everything the UI needs.
The pipeline (`scripts/`) stays — it already generates the right JSON.
Only the presentation layer changes.

---

## Delegation Pattern

Each session:
1. Marcus sets up the session goal and files to change
2. Marcus calls `gh copilot -- gpt-5.4` as a subagent to do the actual implementation
3. Marcus reviews the output, opens the browser, verifies
4. If broken: quick fix in the next session
5. If clean: commit and move on

**Start each gh copilot session with this exact prompt header:**

```
You are implementing Design #102 for Arbiter (file paths are absolute).
Design spec: ~/Marcus/Workspace/design-library/designs/102-professional-political-briefing.md
Read it first.
Project root: /Users/carlosmac/arbiter
Current session goal: [insert session goal]
Files to change: [list]
Files to preserve: [list]
Design constraints: no gradients, no external fonts (system-ui), flat #0D0F1A background, blue+amber only, portrait-first 450×800px primary
```

---

## Session Roadmap

---

### Session 1 — Foundation: Design Tokens + Layout Shell
**Time: ~5 minutes**
**Goal**: Replace globals.css and layout.tsx. Strip Geist. Set CSS custom properties. Flat navy background.

**Files to delegate to gh copilot:**
- `src/app/globals.css` — replace entirely
- `src/app/layout.tsx` — remove Geist, strip font variables, set body background to `#0D0F1A`

**gh copilot prompt:**
```
Replace globals.css and layout.tsx with the Design #102 tokens.
globals.css: CSS custom properties for ALL design tokens (--color-primary: #0D0F1A, --color-secondary: #141828, --color-surface: #05081A, --color-blue: #3B82F6, --color-blue-light: #93C5FD, --color-amber: #FBBF24, --color-amber-light: #FDE68A, --color-amber-label: #FCD34D, --color-blue-label: #60A5FA, --color-body: #E8E4DC, --color-heading: #F1F5F9). Body: background #0D0F1A, color #E8E4DC, font-family system-ui, no gradients.
layout.tsx: remove Geist/Geist_Mono imports, remove font variables from <html> className, keep flex flex-col min-h-full, update metadata title to "Arbiter — Political Briefing".
Exact file paths:
- /Users/carlosmac/arbiter/src/app/globals.css
- /Users/carlosmac/arbiter/src/app/layout.tsx
```

**Verification**: `npm run build` passes. No console errors.

---

### Session 2 — Sticky Header + Opportunity Card Component
**Time: ~5 minutes**
**Goal**: Build the `card-header` and the opportunity card anatomy. Drop the old multi-section page and replace with a vertical stack.

**Files to delegate to gh copilot:**
- `src/app/page.tsx` — replace entirely

**gh copilot prompt:**
```
Rewrite /Users/carlosmac/arbiter/src/app/page.tsx to match Design #102.
The entire page is now: sticky header bar + vertical stack of opportunity cards (one per item in getTopOpportunities(report)).
Import data from: ./dashboard-data (getTopOpportunities, mockDashboardReport, defaultPortfolioSnapshot, getPortfolioReviewCards)
Import types from: ./report-schema (DailyReport, Opportunity, PositionReview)

STICKY HEADER (card-header component):
- Background: #0D0F1A, padding 16px 18px, sticky top, z-index 50
- Left: "Arbiter" wordmark — display size (22px bold), color #F1F5F9
- Right: badge showing reportDate (amber label style) + live dot (amber, pulsing via CSS animation)
- Remove ALL nav links, stat strips, section anchors

PAGE BODY:
- Background: #0D0F1A, no gradient
- Padding: 16px (portrait-first), cards use CSS Grid: 1 column at <768px, 3 columns at >=1200px
- Card grid: gap 16px, each card has portrait proportions (min-height ~400px)

OPPORTUNITY CARD anatomy (top to bottom, each is a distinct visual block):
1. Badge row: ticker badge (pill, blue bg) + market type badge
2. Race title (22px bold #F1F5F9) on its own line
3. Election date (14px, color #60A5FA) on new line — use market.expiresAt or a reasonable display
4. Context paragraph (15px #E8E4DC) — one paragraph, use opportunity.reason truncated to ~120 chars
5. Price row (flex, centered, gap 12px):
   - "Market" box: bg #05081A, border 1px solid rgba(59,130,246,0.55), box-shadow blue glow, padding 12px 10px
     Label: "MARKET" (12px uppercase letter-spacing, color #60A5FA)
     Value: opportunity.market.yesAskCents + "¢" (22px bold #93C5FD)
   - "Edge" box: SAME bg/border/shadow style as market but amber (rgba(251,191,36,0.55), box-shadow amber)
     Label: "EDGE" (#FCD34D)
     Value: "+" + opportunity.edge + " pts" (22px bold #FDE68A) — only show if edge > 0
   - "Marcus" box: same amber style as Edge
     Label: "MARCUS" (#60A5FA)
     Value: opportunity.marcusFairValue + "¢" (22px bold #FDE68A)
6. Analysis section: label "ANALYSIS" (#FCD34D, 12px uppercase), paragraph in #E8E4DC using opportunity.whatWouldChange
7. Source links: flex-wrap row of pills, each a.href to evidenceLink.href, label from evidenceLink.label, style: rounded-sm blue tinted

NO-TRADE STATE (when getTopOpportunities(report).length === 0):
- One centered card, same card styles
- Large "No trade today" heading in #F1F5F9
- Subtext from report.summary in #E8E4DC
- Badge showing pass count if report.passes?.length > 0

Build this as a pure server component. No 'use client'. Use Tailwind 4 utility classes. Map custom properties directly in className where needed (Tailwind 4 supports arbitrary values). Do NOT use the old inline color strings from the previous version.

The card component should be a local function (not exported), e.g. function OpportunityCard({ opportunity }: { opportunity: Opportunity }) inside page.tsx.

After the cards: if there are portfolio positions (getPortfolioReviewCards(report, portfolioSnapshot).length > 0), render a "Portfolio" section header + the same card style for each position (swap price row for Exposure + P&L).
```

**Verification**: Browser at 450px shows vertical stack. Price boxes glow. No layout overflow.

---

### Session 3 — Portfolio Card + Pass Display
**Time: ~5 minutes**
**Goal**: Complete the portfolio section and add pass entries as compact cards below opportunities.

**Files to delegate to gh copilot:**
- `src/app/page.tsx` — update

**gh copilot prompt:**
```
Update /Users/carlosmac/arbiter/src/app/page.tsx to add:
PORTFOLIO SECTION — after the opportunity cards, before any closing
   Section header: "Portfolio" label (uppercase, 12px letter-spacing, color #60A5FA)
   One PortfolioCard per item in getPortfolioReviewCards(report, portfolioSnapshot)
   PortfolioCard anatomy (same card styles as opportunity cards but different price row):
   - Badge row: ticker + action badge (Hold=blue, Reduce=amber, Exit=red)
   - Title (market.title)
   - Price row (3 boxes):
     - "Entry" box: blue glow, value = executablePrice + "¢" or "—"
     - "P&L" box: amber glow, value = position.pnl >= 0 ? "+$"+pnl : "-$"+Math.abs(pnl), colored #6EE7B7 if positive, #FB7185 if negative
     - "Exposure" box: blue glow, value = "$"+exposure.toLocaleString()
   - Note paragraph: position.note
   - Source links if position.evidenceLinks.length > 0

2. PASS ENTRIES — after portfolio section
   Section header: "Passed" label
   Render report.passes?.slice(0, 5) as compact horizontal-scroll strip of small cards (ticker + reason code only)
   If passes is empty or undefined, render nothing

Style consistency: ALL cards use the same rounded-lg background #141828. Price boxes always use bg #05081A with the appropriate colored glow border.
```

**Verification**: Portfolio section renders with correct P&L colors. Pass entries show as compact list.

---

### Session 4 — Polish + Responsive + Edge Cases
**Time: ~5 minutes**
**Goal**: Fix any rendering issues, add responsive behavior for 1200px+ desktop, handle empty states.

**Files to delegate to gh copilot:**
- `src/app/page.tsx` — update

**gh copilot prompt:**
```
Polish /Users/carlosmac/arbiter/src/app/page.tsx:

1. RESPONSIVE: 
   - Cards already grid 1-col (<768px) / 3-col (>=1200px) from Session 2
   - Ensure portfolio cards and pass entries also follow the same grid at the same breakpoints
   - Price row stays 3-across at all sizes (don't stack vertically)
   - Header stays sticky across all breakpoints

2. EMPTY STATES to handle gracefully:
   - If report.watchlist?.length > 0: show "Watchlist" as a small label + comma-separated inline list (NOT a card, NOT a new section)
   - If report.archive is empty: render nothing for archive (drop the "archive pending" placeholder)
   - If getPortfolioReviewCards returns []: show one small centered note "No open positions" (no portfolio section at all)

3. THESIS STRIP: Between the sticky header and the cards, add a single full-width band:
   - Background: #141828, padding 12px 18px
   - Text: report.thesis (14px, #E8E4DC, centered)
   - No card border, no shadow — just a colored band

4. LIVE INDICATOR: The amber pulsing dot in the header should use a CSS keyframe animation.
   Add to globals.css:
   @keyframes pulse { 0%,100% { opacity: 1 } 50% { opacity: 0.3 } }
   .live-dot { animation: pulse 2s ease-in-out infinite }

5. BUILD FIXES: Ensure:
   - No TypeScript errors (all types from report-schema.ts must be imported correctly)
   - No unused imports
   - npm run build passes
   - npm run lint passes

6. READ从前: Read the current globals.css to check if the @keyframes pulse rule needs to be added (it may not be there from Session 1).
   File: /Users/carlosmac/arbiter/src/app/globals.css
```

**Verification**: `npm run build` + `npm run lint` both pass. Browser at 1200px looks good. Empty states work.

---

### Session 5 — Full Integration + Final Review
**Time: ~5 minutes**
**Goal**: Verify the complete page, check data flow, commit.

**Marcus does this session directly** (not delegated):
1. Run `npm run build && npm run lint` — must both pass
2. Open browser at 450px portrait — visually verify against design spec
3. Open at 1200px — check responsive behavior
4. Check price boxes: Market (blue glow), Edge (amber glow), Marcus (amber glow)
5. Check "No trade today" state with mockDashboardReport or a report with 0 opportunities
6. Check portfolio cards with P&L coloring
7. Commit with message: `feat: complete redesign to design #102 — navy/blue/amber briefing card UI`

---

## What Stays vs. What Changes

| Layer | Status |
|-------|--------|
| `report-schema.ts` | Stays — data model is correct |
| `dashboard-data.ts` | Stays — data loading is correct |
| `report-storage.ts` | Stays |
| `scripts/` pipeline | Stays |
| `globals.css` | Replaced |
| `layout.tsx` | Replaced |
| `page.tsx` | Replaced (3 rewrite sessions + 1 polish) |
| Tests (`*.test.tsx`) | Update after final UI is stable |

---

## What Gets Dropped

- **Everything outside the card stack**: header stat cards, nav links, section dividers, thesis strip
- Archive section — entirely removed
- Watchlist section — entirely removed
- Polling Evidence section — not a card type in Design #102
- Multi-column desktop grid (old) — replaced by portrait card 3-column grid at 1200px+
- Gradient radial backgrounds — flat #0D0F1A only
- Geist font loading — system-ui only
- All old inline color strings from the previous page.tsx (#6EE7B7, #FB7185, etc. — replaced by the new blue/amber palette)
- ISR stat cards in header (gross exposure, unrealized P&L, cash available) — these move into portfolio cards

---

**Decisions confirmed (1–4 dropped, 5 yes):**

- Archive → DROP
- Thesis strip → DROP
- Watchlist → DROP
- Live portfolio indicator → KEEP in sticky header
- Portrait cards, 3-column grid at desktop (not single-column page)
- Build-test after each session: YES

**Updated page structure:**
1. Sticky header (Arbiter wordmark + live dot + report date)
2. Opportunity cards (portrait aspect, 3-col grid at 1200px+, stacked at 450px)
3. Portfolio position cards (same card anatomy, different price row)
4. Pass entries (compact list or strip, no full card)
5. NO archive, NO thesis strip, NO watchlist section
