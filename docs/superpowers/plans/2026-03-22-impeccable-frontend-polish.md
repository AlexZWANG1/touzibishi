# Impeccable Frontend Polish — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Systematically apply Impeccable design principles to the IRIS (Prism) frontend — fixing accessibility, performance, typography, color, layout, motion, and interaction issues identified during the audit/critique pass.

**Architecture:** 7 independent tasks targeting distinct layers of the design system. Each task is self-contained and produces a visual or measurable improvement. Tasks are ordered by impact: foundation fixes first (fonts, a11y, tokens), then visual refinements (layout, color, motion), then polish (empty states, cleanup).

**Tech Stack:** Next.js 15, React 19, Tailwind CSS v4, CSS custom properties, `next/font/google`

---

## File Map

| File | Responsibility | Tasks |
|------|---------------|-------|
| `src/app/layout.tsx` | Root layout, font loading | T1 |
| `src/app/globals.css` | Design tokens, base styles, animations | T1, T2, T3, T5, T7 |
| `tailwind.config.ts` | Tailwind extensions | T1, T3 |
| `src/components/AppNav.tsx` | Top navigation bar | T2, T6 |
| `src/app/page.tsx` | Home page | T4, T6 |
| `src/components/SearchBar.tsx` | Search input | T2, T6 |
| `src/components/MetricCard.tsx` | KPI metric card | T4 |
| `src/components/MetricCardGrid.tsx` | Metric card layout | T4 |
| `src/components/FairValueCard.tsx` | Fair value visualization | T4 |
| `src/components/PanelTabBar.tsx` | Analysis tab bar | T2 |
| `src/components/ChatPanel.tsx` | Chat conversation panel | T5, T6 |
| `src/components/StreamingTimeline.tsx` | Tool timeline | T6 |
| `src/components/TimelineItem.tsx` | Timeline event item | T5 |
| `src/components/WatchlistGrid.tsx` | Watchlist table | T2, T6 |
| `src/components/WatchlistCard.tsx` | Watchlist row | T2 |
| `src/components/DataPanel.tsx` | Data panel wrapper | T6 |
| `src/components/CompsPanel.tsx` | Comps panel wrapper | T6 |
| `src/components/StrategyPanel.tsx` | Strategy panel | T4, T6 |
| `src/components/SensitivityHeatmap.tsx` | Heatmap grid | T4 |
| `src/components/FundamentalsPanel.tsx` | Research panel | T6 |
| `src/components/PhaseIndicator.tsx` | Phase progress | T5 |
| `src/app/knowledge/page.tsx` | Knowledge base page | T6 |

---

## Chunk 1: Foundation (Tasks 1-3)

### Task 1: Font Loading — Google Fonts → `next/font`

**Why:** CSS `@import` for Google Fonts creates a render-blocking request chain. 13 font weights loaded in one shot. Next.js `next/font` self-hosts fonts, eliminates FOUT, and loads only what's needed.

**Files:**
- Modify: `src/app/layout.tsx`
- Modify: `src/app/globals.css`
- Modify: `tailwind.config.ts`

- [ ] **Step 1: Install and configure `next/font/google` in layout.tsx**

Replace the CSS @import approach with Next.js font optimization. In `layout.tsx`:

```tsx
import { Playfair_Display, Sora, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { AppNav } from "@/components/AppNav";

const playfair = Playfair_Display({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  style: ["normal", "italic"],
  display: "swap",
  variable: "--font-display",
});

const sora = Sora({
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700"],
  display: "swap",
  variable: "--font-sans",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  display: "swap",
  variable: "--font-mono",
});

// ... in the JSX:
<html lang="zh-CN" className={`${playfair.variable} ${sora.variable} ${jetbrainsMono.variable}`}>
```

- [ ] **Step 2: Remove `@import` from globals.css and update font variables**

Remove line 1 of `globals.css` (the Google Fonts `@import` URL).

Update the CSS custom property definitions in `:root`:

```css
--display: var(--font-display), Georgia, serif;
--sans: var(--font-sans), "PingFang SC", "Noto Sans SC", "Source Han Sans SC", "Microsoft YaHei", sans-serif;
--mono: var(--font-mono), Consolas, "Courier New", monospace;
```

Note: Also adding `"Noto Sans SC"` and `"Source Han Sans SC"` as Chinese font fallbacks for Linux/Android coverage.

- [ ] **Step 3: Verify fonts load correctly**

Run: `cd iris-frontend && npm run dev`
Open browser, check:
1. No network requests to `fonts.googleapis.com` in DevTools Network tab
2. Font files served from `/_next/static/media/`
3. Playfair renders on headings, Sora on body, JetBrains Mono on data

- [ ] **Step 4: Commit**

```bash
git add src/app/layout.tsx src/app/globals.css
git commit -m "perf: migrate Google Fonts to next/font self-hosting

Eliminates render-blocking @import chain for 13 font weights.
Adds Noto Sans SC / Source Han Sans SC fallbacks for CJK coverage."
```

---

### Task 2: Accessibility — Contrast, Focus, & Semantics

**Why:** `--t3` (#888) has 3.5:1 contrast ratio, `--t4` (#bbb) has 1.6:1 — both fail WCAG AA (4.5:1 for text). No visible focus indicators on buttons/links. These are P0 accessibility violations.

**Files:**
- Modify: `src/app/globals.css`
- Modify: `src/components/AppNav.tsx`
- Modify: `src/components/SearchBar.tsx`
- Modify: `src/components/PanelTabBar.tsx`
- Modify: `src/components/WatchlistGrid.tsx`
- Modify: `src/components/WatchlistCard.tsx`

- [ ] **Step 1: Fix color contrast tokens in globals.css**

In `:root`, update the low-contrast tokens:

```css
/* Before */
--t3: #888888;   /* 3.5:1 on #fafaf9 — FAIL */
--t4: #bbbbbb;   /* 1.6:1 on #fafaf9 — FAIL */

/* After */
--t3: #6b6560;   /* ~5.2:1 on #fafaf9 — PASS AA */
--t4: #9a9490;   /* ~3.2:1 on #fafaf9 — PASS AA-large, acceptable for hints/placeholders */
```

The new `--t3` is warm-tinted to match the existing neutral palette direction. `--t4` is used only for placeholder text and decorative hints (large text or non-essential), where 3:1 is acceptable per WCAG for UI components.

- [ ] **Step 2: Add global focus-visible styles in globals.css**

After the `button { cursor: pointer; }` rule, add:

```css
:focus-visible {
  outline: 2px solid var(--ac);
  outline-offset: 2px;
}

:focus:not(:focus-visible) {
  outline: none;
}
```

This ensures keyboard users see a clear indigo focus ring, while mouse clicks remain clean.

- [ ] **Step 3: Add `aria-label` to icon-only buttons**

Audit components for icon-only buttons without accessible labels:

- `AppNav.tsx`: The "LIVE" indicator should be wrapped in `aria-hidden="true"` (decorative)
- `SearchBar.tsx`: Submit button — add `aria-label="提交分析"`
- `WatchlistGrid.tsx`: Refresh button already has text, OK
- `WatchlistCard.tsx`: "复盘" button already has text, OK

- [ ] **Step 4: Fix table header alignment in WatchlistGrid**

The `style={{ textAlign: index >= 2 ? "right" : "left" }}` inline style conflicts with the `text-left` class. Remove the `text-left` class from `<th>` and keep only the inline style, or use conditional classes:

```tsx
className={`px-5 py-3 font-sans text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--t3)] ${
  index >= 2 ? "text-right" : "text-left"
}`}
```

Remove the inline `style` attribute.

- [ ] **Step 5: Verify and commit**

Check in browser:
1. Muted text is still visible but now passes contrast check
2. Tab through the page — every interactive element shows a visible focus ring
3. Screen reader reads button labels correctly

```bash
git add src/app/globals.css src/components/AppNav.tsx src/components/SearchBar.tsx src/components/WatchlistGrid.tsx
git commit -m "fix(a11y): improve color contrast and add focus-visible indicators

--t3 raised to 5.2:1 contrast ratio (was 3.5:1).
--t4 raised to 3.2:1 (was 1.6:1).
All interactive elements now show focus ring for keyboard navigation."
```

---

### Task 3: Fluid Typography & Spacing

**Why:** All font sizes are fixed px values. On a 1440px monitor vs a 1024px laptop, text looks identical — wasting space on large screens and feeling cramped on small ones. Impeccable recommends `clamp()` for fluid sizing.

**Files:**
- Modify: `src/app/globals.css`
- Modify: `src/app/page.tsx`
- Modify: `src/app/knowledge/page.tsx`
- Modify: `tailwind.config.ts`

- [ ] **Step 1: Add fluid type scale utilities in globals.css**

After the `.font-data` rule, add a fluid type scale:

```css
.text-fluid-hero {
  font-size: clamp(36px, 4vw + 16px, 54px);
}

.text-fluid-h1 {
  font-size: clamp(24px, 2vw + 12px, 36px);
}

.text-fluid-h2 {
  font-size: clamp(20px, 1.5vw + 8px, 28px);
}

.text-fluid-body {
  font-size: clamp(14px, 0.2vw + 13px, 16px);
}
```

- [ ] **Step 2: Apply fluid hero sizing on Home page**

In `page.tsx`, replace the fixed hero heading size:

```tsx
{/* Before */}
<h1 className="max-w-[700px] font-display text-[42px] leading-[1.04] tracking-[-0.04em] text-[var(--ink)] sm:text-[54px]">

{/* After */}
<h1 className="max-w-[700px] font-display text-fluid-hero leading-[1.04] tracking-[-0.04em] text-[var(--ink)]">
```

Similarly, apply `text-fluid-h2` to section headings ("Watchlist", "Recent Analyses"):

```tsx
{/* Before */}
<h2 className="font-display text-[28px] font-medium tracking-[-0.03em] text-[var(--ink)]">

{/* After */}
<h2 className="font-display text-fluid-h2 font-medium tracking-[-0.03em] text-[var(--ink)]">
```

- [ ] **Step 3: Apply fluid heading to Knowledge page**

In `knowledge/page.tsx`, the document title:

```tsx
{/* Before */}
<h1 className="mt-5 font-display text-[36px] font-medium leading-[1.08] tracking-[-0.03em] text-[var(--ink)]">

{/* After */}
<h1 className="mt-5 font-display text-fluid-h1 font-medium leading-[1.08] tracking-[-0.03em] text-[var(--ink)]">
```

- [ ] **Step 4: Add fluid spacing utility for section gaps**

In globals.css, add:

```css
.gap-fluid-section {
  margin-top: clamp(32px, 4vw, 56px);
}
```

Apply to major section breaks in `page.tsx`:

```tsx
{/* Replace mt-8, mt-9, mt-10 section spacing with consistent fluid spacing */}
<section className="gap-fluid-section space-y-4 animate-fade-up [animation-delay:240ms]">
```

- [ ] **Step 5: Commit**

```bash
git add src/app/globals.css src/app/page.tsx src/app/knowledge/page.tsx
git commit -m "feat: add fluid typography and spacing with clamp()

Hero scales 36-54px, headings 20-28px, body 14-16px.
Section spacing responds to viewport width."
```

---

## Chunk 2: Visual Refinements (Tasks 4-5)

### Task 4: Break the Card Monotony — Layout Differentiation

**Why:** MetricCard repeats the exact same structure (label → big number → change%) for every KPI. StrategyPanel repeats 3-4 identical metric blocks. SensitivityHeatmap cells are too cramped. These are Impeccable anti-patterns: "identical card grids" and "hero metric layout template".

**Files:**
- Modify: `src/components/MetricCard.tsx`
- Modify: `src/components/MetricCardGrid.tsx`
- Modify: `src/components/FairValueCard.tsx`
- Modify: `src/components/SensitivityHeatmap.tsx`
- Modify: `src/components/StrategyPanel.tsx`
- Modify: `src/app/page.tsx`

- [ ] **Step 1: Differentiate MetricCard with size variants**

Add a `size` prop to MetricCard to break the monotony:

```tsx
interface MetricCardProps {
  metric: MetricItem;
  size?: "default" | "compact";
}

export function MetricCard({ metric, size = "default" }: MetricCardProps) {
  const positive = metric.change != null && metric.change > 0;
  const negative = metric.change != null && metric.change < 0;

  if (size === "compact") {
    return (
      <div className="flex items-center justify-between gap-3 border-b border-[var(--b1)] px-4 py-3 last:border-b-0">
        <span className="text-[12px] text-[var(--t2)]">{metric.label}</span>
        <div className="flex items-center gap-2">
          <span className="font-mono text-[14px] font-semibold text-[var(--cy-t)]">{metric.value}</span>
          {metric.change != null && (
            <span
              className="font-mono text-[11px] font-medium"
              style={{ color: positive ? "var(--green)" : negative ? "var(--red)" : "var(--t3)" }}
            >
              {positive ? "+" : ""}{metric.change.toFixed(1)}%
            </span>
          )}
        </div>
      </div>
    );
  }

  // ... keep existing "default" rendering
}
```

- [ ] **Step 2: Update MetricCardGrid to use mixed layout**

Show the first 3 metrics as full cards (primary KPIs) and remaining as compact rows:

```tsx
export function MetricCardGrid({ metrics }: { metrics: MetricItem[] }) {
  const primary = metrics.slice(0, 3);
  const secondary = metrics.slice(3);

  return (
    <div className="space-y-3">
      {primary.length > 0 && (
        <div className="grid gap-3 md:grid-cols-3">
          {primary.map((m) => (
            <MetricCard key={m.label} metric={m} />
          ))}
        </div>
      )}
      {secondary.length > 0 && (
        <div className="prism-panel overflow-hidden">
          {secondary.map((m) => (
            <MetricCard key={m.label} metric={m} size="compact" />
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Improve SensitivityHeatmap cell spacing**

In `SensitivityHeatmap.tsx`, increase the grid gap:

```tsx
{/* Before */}
<div className="grid gap-[6px]"

{/* After */}
<div className="grid gap-[8px]"
```

And increase cell padding:

```tsx
{/* Before */}
className="rounded-sm px-2 py-3 text-center font-mono text-[12px]"

{/* After */}
className="rounded-md px-3 py-3.5 text-center font-mono text-[12px]"
```

- [ ] **Step 4: Differentiate StrategyPanel metric blocks**

In `StrategyPanel.tsx`, the 3 signal metrics (Target Weight, Discount, Suggested Shares) are identical blocks. Make the primary metric (Target Weight) larger:

```tsx
<div className="mt-4 grid gap-3 sm:grid-cols-[1.2fr_0.8fr_0.8fr]">
```

And for the first child, increase the number size:

```tsx
{[
  { label: "Target Weight", value: `${(strategy.signal.targetWeight * 100).toFixed(1)}%`, primary: true },
  { label: "Discount", value: strategy.signal.discountPct != null ? `${strategy.signal.discountPct.toFixed(1)}%` : "—" },
  { label: "Suggested Shares", value: strategy.signal.suggestedShares ?? "—" },
].map((item) => (
  <div key={item.label} className="rounded-lg bg-[var(--bg)] p-4">
    <div className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--t3)]">
      {item.label}
    </div>
    <div className={`mt-2 font-mono font-semibold text-[var(--cy-t)] ${
      item.primary ? "text-[28px]" : "text-[22px]"
    }`}>
      {item.value}
    </div>
  </div>
))}
```

- [ ] **Step 5: Differentiate Home page Capability Modules**

In `page.tsx`, make the first module (基本面研究) a "featured" layout that's wider and visually distinct:

```tsx
{CAPABILITY_MODULES.map((module, idx) => (
  <article
    key={module.key}
    className={`prism-card overflow-hidden ${idx === 0 ? "border-[var(--b2)]" : ""}`}
  >
    <div className="h-[3px]" style={{ background: module.bar }} />
    <div className={`flex flex-col gap-5 p-6 ${
      idx === 0 ? "lg:flex-row lg:items-start" : "lg:flex-row lg:items-center"
    }`}>
```

For `idx === 0`, give the description more space and a slightly larger title:

```tsx
<h2 className={`font-semibold text-[var(--t1)] ${
  idx === 0 ? "text-[18px]" : "text-[16px]"
}`}>{module.title}</h2>
```

- [ ] **Step 6: Commit**

```bash
git add src/components/MetricCard.tsx src/components/MetricCardGrid.tsx src/components/SensitivityHeatmap.tsx src/components/StrategyPanel.tsx src/app/page.tsx
git commit -m "design: break card monotony with size variants and layout differentiation

MetricCardGrid: primary 3 as cards, rest as compact rows.
SensitivityHeatmap: increased cell spacing and radius.
StrategyPanel: primary metric emphasized.
Home: first capability module visually featured."
```

---

### Task 5: Motion Refinement — Kill Bounce, Add Purpose

**Why:** `animate-bounce` for streaming dots is explicitly called out by Impeccable as "dated and tacky". Phase transitions lack meaningful motion. The `fade-up` animation is good but could be more refined.

**Files:**
- Modify: `src/app/globals.css`
- Modify: `src/components/ChatPanel.tsx`
- Modify: `src/components/TimelineItem.tsx`
- Modify: `src/components/PhaseIndicator.tsx`
- Modify: `tailwind.config.ts`

- [ ] **Step 1: Replace bounce animation with smooth pulse in globals.css**

Add a new keyframe for streaming dots:

```css
@keyframes dot-pulse {
  0%, 100% {
    opacity: 0.25;
    transform: scale(0.85);
  }
  50% {
    opacity: 1;
    transform: scale(1);
  }
}
```

And in `tailwind.config.ts`, add:

```ts
"dot-pulse": "dot-pulse 1.4s ease-in-out infinite",
```

- [ ] **Step 2: Update StreamingDots in ChatPanel.tsx**

```tsx
function StreamingDots() {
  return (
    <span className="ml-2 inline-flex items-center gap-[5px] align-middle">
      {[0, 200, 400].map((delay) => (
        <span
          key={delay}
          className="inline-block h-[5px] w-[5px] animate-dot-pulse rounded-full bg-[var(--ac)]"
          style={{ animationDelay: `${delay}ms` }}
        />
      ))}
    </span>
  );
}
```

Key changes: `animate-bounce` → `animate-dot-pulse`, slightly smaller dots (6→5px), wider stagger delays.

- [ ] **Step 3: Add phase transition animation to PhaseIndicator**

Add a subtle scale-in for the active phase pill:

```css
@keyframes phase-activate {
  from {
    opacity: 0.5;
    transform: scale(0.92);
  }
  to {
    opacity: 1;
    transform: scale(1);
  }
}
```

In `PhaseIndicator.tsx`, add animation class to active pill:

```tsx
className={`rounded-pill px-3 py-1.5 text-[11px] font-medium transition-colors ${
  active ? "animate-[phase-activate_0.25s_ease-out]" : ""
}`}
```

- [ ] **Step 4: Improve fade-up easing**

In globals.css, update `fade-up` to use a more natural expo ease-out:

```css
@keyframes fade-up {
  from {
    opacity: 0;
    transform: translateY(16px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
```

In `tailwind.config.ts`, update the animation timing:

```ts
"fade-up": "fade-up 0.5s cubic-bezier(0.16, 1, 0.3, 1) forwards",
```

This uses `ease-out-expo` — smooth deceleration that feels natural per Impeccable guidelines.

- [ ] **Step 5: Add timeline item entrance animation**

In globals.css, add:

```css
@keyframes slide-in-left {
  from {
    opacity: 0;
    transform: translateX(-8px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}
```

In `TimelineItem.tsx`, add entrance animation:

```tsx
<div className="relative flex gap-3 px-4 py-3 animate-[slide-in-left_0.3s_cubic-bezier(0.16,1,0.3,1)]">
```

- [ ] **Step 6: Commit**

```bash
git add src/app/globals.css tailwind.config.ts src/components/ChatPanel.tsx src/components/PhaseIndicator.tsx src/components/TimelineItem.tsx
git commit -m "design: refine motion — replace bounce with smooth pulse, add expo easing

Streaming dots: bounce → dot-pulse (smooth scale+opacity).
Phase indicator: subtle scale-in on activation.
Fade-up: exponential ease-out for natural deceleration.
Timeline items: slide-in-left entrance."
```

---

## Chunk 3: Color, Empty States & Cleanup (Tasks 6-7)

### Task 6: Color De-AI & Empty States

**Why:** Background radial gradient uses indigo+cyan — a common AI product fingerprint. Empty states throughout the app are bare text with no teaching intent. Impeccable requires empty states to "teach the interface".

**Files:**
- Modify: `src/app/globals.css`
- Modify: `src/app/page.tsx`
- Modify: `src/components/ChatPanel.tsx`
- Modify: `src/components/DataPanel.tsx`
- Modify: `src/components/CompsPanel.tsx`
- Modify: `src/components/StrategyPanel.tsx`
- Modify: `src/components/FundamentalsPanel.tsx`
- Modify: `src/components/StreamingTimeline.tsx`
- Modify: `src/components/AppNav.tsx`
- Modify: `src/components/WatchlistGrid.tsx`
- Modify: `src/app/knowledge/page.tsx`

- [ ] **Step 1: Replace AI-flavored background gradient**

In `globals.css`, update the `body` background:

```css
/* Before: indigo + cyan radials — AI-coded */
body {
  background:
    radial-gradient(circle at top left, rgba(99, 102, 241, 0.06), transparent 28%),
    radial-gradient(circle at top right, rgba(6, 182, 212, 0.05), transparent 24%),
    linear-gradient(180deg, #fcfcfb 0%, #fafaf9 35%, #f7f5f1 100%);
}

/* After: warm single-tone — matches existing warm neutrals */
body {
  background:
    radial-gradient(ellipse at 20% 0%, rgba(180, 160, 130, 0.06), transparent 50%),
    linear-gradient(180deg, #fcfcfb 0%, #fafaf9 35%, #f7f5f1 100%);
}
```

This uses a warm sepia-ish radial that harmonizes with the `#fafaf9` / `#f3f2f0` palette.

- [ ] **Step 2: Warm-tint the status colors**

In `:root`, nudge the status colors toward the warm palette:

```css
/* Before — pure Tailwind palette */
--green: #15803d;
--red: #b91c1c;
--amber: #a16207;

/* After — warm-tinted to match the overall warmth */
--green: #1a7a3a;
--red: #b5231e;
--amber: #9c6510;
```

Subtle shift — the greens and reds gain a slightly warmer undertone.

- [ ] **Step 3: Redesign empty state for Home page ("no results")**

In `page.tsx`, replace the bare text empty state:

```tsx
{!watchlist.length && !history.length && (
  <div className="rounded-[20px] border border-dashed border-[var(--b2)] bg-[var(--bg-w)] px-8 py-12 text-center shadow-card">
    <div className="mx-auto mb-5 inline-flex h-14 w-14 items-center justify-center rounded-[16px] bg-[var(--ac-s)]">
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="var(--ac)" strokeWidth="1.6">
        <path d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </div>
    <p className="font-display text-[22px] font-medium text-[var(--ink)]">开始你的第一轮研究</p>
    <p className="mx-auto mt-3 max-w-[380px] text-[14px] leading-[1.8] text-[var(--t2)]">
      在搜索框中描述一个具体的投研问题 — 比如 "分析 AAPL 服务业务增长" — Prism 会自动编排数据拉取、估值建模和同业对比的完整流程。
    </p>
    <div className="mt-6 flex flex-wrap justify-center gap-2">
      {["AAPL 财报分析", "NVDA vs AMD 估值", "META 交易策略"].map((hint) => (
        <button
          key={hint}
          type="button"
          onClick={() => setQuery(hint)}
          className="rounded-pill border border-[var(--b2)] bg-[var(--bg)] px-4 py-2 text-[12px] font-medium text-[var(--t2)] transition-colors hover:border-[var(--ac-m)] hover:text-[var(--ac)]"
        >
          {hint}
        </button>
      ))}
    </div>
  </div>
)}
```

- [ ] **Step 4: Improve Watchlist empty state**

In `WatchlistGrid.tsx`, replace the bare text:

```tsx
<tr>
  <td colSpan={7} className="px-5 py-12 text-center">
    <p className="text-[14px] font-medium text-[var(--t1)]">追踪列表为空</p>
    <p className="mx-auto mt-2 max-w-[320px] text-[12px] leading-[1.7] text-[var(--t3)]">
      完成一轮深度分析后，Prism 会自动把带有估值结论的标的加入这里。你可以在此追踪价格变动和建议更新。
    </p>
  </td>
</tr>
```

- [ ] **Step 5: Improve panel empty states (Data, Comps, Strategy, Fundamentals)**

For each panel, replace bare "等待..." text with structured loading hints.

`DataPanel.tsx` (when `metrics.length === 0 && financialTables.length === 0`):

```tsx
<div className="flex h-full flex-col items-center justify-center px-6 py-12 text-center">
  <div className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--t4)]">数据面板</div>
  <p className="mt-2 text-[13px] text-[var(--t3)]">
    Prism 拉取到财务报表和市场指标后，会展示在这里。
  </p>
</div>
```

Apply the same pattern to `CompsPanel.tsx`, `StrategyPanel.tsx`, and `FundamentalsPanel.tsx` — adding a section label above the message.

- [ ] **Step 6: Redesign ChatPanel conversation empty state**

```tsx
{segments.length === 0 && !isStreaming && pageState === "IDLE" && (
  <div className="flex h-full flex-col items-center justify-center px-6 text-center">
    <div className="mb-4 text-[var(--ac)]">
      <PrismLogo size={28} showWordmark={false} />
    </div>
    <p className="font-display text-[24px] font-medium text-[var(--ink)]">对话区</p>
    <p className="mx-auto mt-3 max-w-[400px] text-[13px] leading-[1.8] text-[var(--t3)]">
      分析启动后，Prism 会把推理过程、关键结论和你的追问整理在这里。你可以随时引导分析方向。
    </p>
  </div>
)}
```

- [ ] **Step 7: Remove "LIVE" indicator noise from AppNav**

The green dot + "LIVE" text in AppNav provides no actionable information. Replace with a more useful backend status indicator:

In `AppNav.tsx`, simplify:

```tsx
{/* Before: always-on LIVE badge */}
<div className="flex items-center gap-2">
  <span className="inline-block h-1.5 w-1.5 rounded-full bg-[var(--green)] animate-pulse-dot" />
  <span className="font-mono text-[11px] text-[var(--t3)]">LIVE</span>
</div>

{/* After: remove entirely — if needed later, make it show actual connection state */}
```

Simply delete this block. The "Dev" link already indicates system access.

- [ ] **Step 8: Commit**

```bash
git add src/app/globals.css src/app/page.tsx src/components/ChatPanel.tsx src/components/DataPanel.tsx src/components/CompsPanel.tsx src/components/StrategyPanel.tsx src/components/FundamentalsPanel.tsx src/components/StreamingTimeline.tsx src/components/AppNav.tsx src/components/WatchlistGrid.tsx
git commit -m "design: de-AI background gradient, warm-tint status colors, teaching empty states

Background: indigo+cyan radials → warm sepia single-tone.
Status colors: subtle warm tint to match neutral palette.
Empty states: all panels now explain what will appear and how to trigger it.
Removed always-on LIVE indicator noise."
```

---

### Task 7: Legacy Cleanup & Polish

**Why:** 35 lines of `--iris-*` legacy CSS aliases add maintenance confusion. `field-sizing: content` needs a fallback. Onboarding card duplicates information already in Capability Modules.

**Files:**
- Modify: `src/app/globals.css`
- Modify: `src/app/page.tsx`

- [ ] **Step 1: Check legacy alias usage before removal**

Search the codebase for any remaining `--iris-` variable references:

Run: `grep -r "iris-" src/ --include="*.tsx" --include="*.ts" | grep -v "node_modules" | grep "var(--iris-"`

If any components still use `--iris-*` variables, update them to use the canonical short names first.

- [ ] **Step 2: Remove legacy aliases from globals.css (if safe)**

Remove lines 57-91 (the `/* Legacy aliases ... */` block) from `:root`.

If Step 1 found remaining usages, replace them in the components first, then remove the aliases.

- [ ] **Step 3: Add `field-sizing` fallback**

In globals.css, the `textarea { field-sizing: content; }` rule only works in Chrome 123+. Add a feature check:

```css
textarea {
  resize: none;
}

@supports (field-sizing: content) {
  textarea {
    field-sizing: content;
  }
}
```

This ensures the textarea gracefully falls back to normal sizing in older browsers, while the JS-based auto-resize in SearchBar and ChatPanel already handles height adjustment.

- [ ] **Step 4: Remove onboarding card from Home page**

In `page.tsx`, remove the entire `{!onboardingDismissed && (...)}` aside block (lines 214-240) and the related state/effect/callback:

- Remove `ONBOARDING_STORAGE_KEY` const
- Remove `onboardingDismissed` state
- Remove `useEffect` that reads localStorage
- Remove `dismissOnboarding` callback
- Remove the `<aside>` JSX block

The Capability Modules already explain what Prism does, making this card redundant.

- [ ] **Step 5: Verify nothing is broken**

Run: `cd iris-frontend && npm run build`
Expected: Build succeeds with no errors.

Run: `npm run dev` and visually verify:
1. No CSS variable resolution errors in DevTools console
2. Textareas still auto-resize properly
3. Home page looks cleaner without the onboarding card

- [ ] **Step 6: Commit**

```bash
git add src/app/globals.css src/app/page.tsx
git commit -m "chore: remove legacy CSS aliases, onboarding card, add field-sizing fallback

Removed 35 lines of --iris-* legacy aliases (all usages migrated).
Wrapped field-sizing:content in @supports for browser compat.
Removed redundant onboarding card — Capability Modules cover same info."
```

---

## Summary

| Task | Focus | Files Changed | Impact |
|------|-------|--------------|--------|
| T1 | Font perf | 3 | Eliminates render-blocking, self-hosts fonts |
| T2 | Accessibility | 6 | WCAG AA contrast, focus-visible, semantics |
| T3 | Fluid typography | 4 | Responsive text scaling with clamp() |
| T4 | Card differentiation | 6 | Breaks monotonous metric/module layouts |
| T5 | Motion refinement | 5 | Bounce → pulse, expo easing, entrance anims |
| T6 | Color & empty states | 11 | De-AI gradient, teaching empty states, warm colors |
| T7 | Cleanup & polish | 2 | Legacy alias removal, compat fix, declutter |

**Execution order:** T1 → T2 → T3 → T4 → T5 → T6 → T7 (foundation → visual → polish)

Tasks 1-3 can be parallelized. Tasks 4-5 can be parallelized. Task 6 depends on T2 (contrast tokens). Task 7 can run independently.
