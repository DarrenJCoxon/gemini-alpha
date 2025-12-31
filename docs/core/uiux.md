# UI/UX Specification: ContrarianAI "Mission Control"

**Version:** 1.0
**Date:** 2025-12-31
**Status:** Approved

## 1. Introduction
This document defines the user experience and visual design for **ContrarianAI**, a professional-grade crypto trading dashboard. The interface serves as a "Mission Control" for the user to monitor the "Council of AI Agents" in real-time.

**Primary Goal:** Trust & Transparency. The UI must verify *why* the bot is trading by visualizing the AI's reasoning process clearly.

## 2. Overall UX Goals & Principles

### 2.1 Design Principles
*   **Institutional, Not Gamified:** Avoid cartoony graphics. Use precise data visualization, monospaced numbers, and a clean, high-contrast dark theme typical of Bloomberg Terminals or professional trading software.
*   **"Glass Box" AI:** The AI's logic should never be a black box. Every trade must link back to the specific "Council Session" log that triggered it.
*   **Information Density:** Maximize screen real estate on desktop. Use minimal padding and compact rows to show more data without scrolling.
*   **Signal over Noise:** Use color strictly for semantic meaning (Green = Buy/Profit, Red = Sell/Loss, Amber = Warning). Neutral data should remain grey/white.

### 2.2 User Personas
*   **The Operator (You):** Wants to verify the bot is working correctly, check P&L quickly, and deep-dive into a specific trade's rationale if it looks risky.

## 3. Visual Identity (Institutional Dark)

### 3.1 Color Palette
We use the **Zinc** scale from Tailwind CSS for a neutral, blue-grey tinted dark mode.

| Color Type | Tailwind Class | Hex Code | Usage |
| :--- | :--- | :--- | :--- |
| **Background** | `bg-zinc-950` | `#09090b` | Main app background (Deepest dark, not pure black). |
| **Surface** | `bg-zinc-900` | `#18181b` | Cards, Panels, Sidebars. |
| **Border** | `border-zinc-800` | `#27272a` | Subtle dividers. |
| **Primary/Buy** | `text-emerald-500` | `#10b981` | Positive P&L, Buy Signals, "Greed" indicators. |
| **Destructive/Sell** | `text-rose-500` | `#f43f5e` | Negative P&L, Sell Signals, "Fear" indicators, Errors. |
| **Warning** | `text-amber-500` | `#f59e0b` | "High Volatility" alerts, System Warnings. |
| **Text Main** | `text-zinc-100` | `#f4f4f5` | Primary headers and data. |
| **Text Muted** | `text-zinc-400` | `#a1a1aa` | Labels, secondary info. |

### 3.2 Typography
*   **UI Font:** `Inter` (Clean, legible sans-serif for labels/headers).
*   **Data Font:** `JetBrains Mono` (Monospace for all prices, scores, logs, and tabular data).

## 4. Information Architecture

### 4.1 Sitemap
```mermaid
graph TD
    A[Dashboard (Home)] --> B[Council Feed]
    A --> C[Active Positions]
    A --> D[Market Scanner]
    A --> E[System Health]
    
    F[History] --> G[Past Trades]
    F --> H[Performance Analytics]
    
    I[Settings] --> J[API Keys]
    I --> K[Risk Configuration]
```

## 5. Key Screen Layouts

### 5.1 Main Dashboard (Desktop View)
A 3-column "Bento Grid" layout.

*   **Top Bar:** Global Status (System Online/Offline), Total Equity, Daily P&L (Ticker style).
*   **Left Column (The Intelligence - 40% width):**
    *   **"Council Chamber" Feed:** A scrollable timeline of agent deliberations.
*   **Center Column (The Action - 35% width):**
    *   **Active Trades:** Cards showing current open positions with live charts (Recharts) and dynamic Stop Loss lines.
*   **Right Column (The Market - 25% width):**
    *   **Scanner:** Dense table of Top 30 coins sorted by "Divergence Score."

### 5.2 Mobile Adaptation
*   **Stacking:** Columns stack vertically.
*   **Order:** 1. P&L/Status (Top) -> 2. Active Trades -> 3. Council Feed (Collapsed by default) -> 4. Scanner.
*   **Navigation:** Bottom Tab Bar (Dashboard, Trades, Logs, Settings).

## 6. Component Specifications (Shadcn UI)

### 6.1 The "Council Session" Card
This is the most complex component. It represents one 15-minute decision cycle.

*   **Header:** Asset Symbol (e.g., SOL/USD) + Timestamp + Final Decision Badge (e.g., "HOLD - Neutral").
*   **Body (Accordion - Collapsible):**
    *   **Sentiment Block:** Icon (Twitter Bird) + Fear Score (0-100) Progress Bar. Text summary.
    *   **Technical Block:** Icon (Chart) + Key Indicators (RSI: 45, MA: Bullish).
    *   **Vision Block:** Thumbnail of the chart analyzed.
*   **Footer:** Master Node's reasoning text ("Sentiment is fear, but structure is broken. No entry.").

### 6.2 Trade Card
*   **Header:** Symbol + Direction (LONG) + Entry Price.
*   **Visual:** Mini Sparkline chart (green/red) showing price action since entry.
*   **Metrics:** Current P&L (large text), ROI %.
*   **Risk:** "Distance to Stop" (e.g., "-2.5%").

### 6.3 Scanner Table
*   **Columns:** Symbol, Price, 15m Change, Fear Score, Tech Score.
*   **Interaction:** Clicking a row filters the "Council Chamber" to show logs for that asset only.

## 7. Interaction Design

*   **Real-time Updates:** The dashboard must use **Supabase Realtime** (WebSockets). When the Python bot inserts a new log, the UI should animate the new card sliding in at the top of the feed without a page refresh.
*   **Toasts:** Use `Sonner` (toast library) for critical alerts (e.g., "Trade Executed: BTC/USD", "Stop Loss Updated").
*   **Loading States:** Skeleton loaders (shimmer effect) for all data cards while fetching.

## 8. Accessibility
*   **Contrast:** Ensure all text passes WCAG AA on the dark background (Zinc-950).
*   **Motion:** Allow users to disable live animations in Settings if they find the feed distracting.
*   **Screen Readers:** Ensure status icons (Green Dot / Red Dot) have `aria-label="System Online"`.
```

---

**UI/UX Specification Complete.**

We now have the complete triad:
1.  **PRD** (Logic)
2.  **Architecture** (Tech)
3.  **UI Spec** (Design)

You are ready to build.

**Recommended Next Step:**
We need to set up the repository. Switch to the **Scrum Master (SM)** to create the first story: **"Project Initialization & Monorepo Setup."**

Type `*agent sm` to start the build.