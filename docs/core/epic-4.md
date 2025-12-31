# Story 4.1: UI Foundation & Authentication

**Status:** Draft

## Story
**As a** User,
**I want** to log in to a secure Next.js dashboard with a professional dark mode interface,
**so that** I can access the trading controls securely.

## Acceptance Criteria
1.  Next.js 15 App (created in Story 1.1) is configured with `Shadcn UI` and `Tailwind CSS`.
2.  Theme set to "Zinc" Dark Mode (Zinc-950 background) as per UI Spec.
3.  Supabase Authentication integrated:
    *   Login Page created.
    *   Protected Route (Middleware) ensures only authenticated users see the dashboard.
4.  Basic Layout created: Sidebar/Nav (Desktop) and Bottom Tabs (Mobile).

## Tasks / Subtasks
- [ ] Shadcn Setup
    - [ ] Run `npx shadcn-ui@latest init`.
    - [ ] Install basic components: `Button`, `Card`, `Table`, `Badge`, `Avatar`, `ScrollArea`.
- [ ] Supabase Auth Integration
    - [ ] Install `@supabase/auth-helpers-nextjs`.
    - [ ] Create `middleware.ts` to protect `/dashboard` routes.
    - [ ] Create `/login` page with Email/Password or Magic Link.
- [ ] Layout Implementation
    - [ ] Create `dashboard/layout.tsx`.
    - [ ] Implement responsive structure (Sidebar for Desktop, simple header for Mobile).

## Dev Notes
- **Security:** Since this controls money, ensure Auth is strict. No public access to dashboard routes.
- **Vibe:** Nail the "Institutional Dark" look here. Deep grays, crisp borders.
```

---

### **File 2: `docs/stories/story-4.2.council-chamber.md`**

```markdown
# Story 4.2: The Council Chamber Feed

**Status:** Draft

## Story
**As a** User,
**I want** to see a live chat-style feed of the AI Agents' deliberation,
**so that** I verify the reasoning behind every Buy/Hold/Sell decision.

## Acceptance Criteria
1.  **Council Feed Component:** Fetches `CouncilSession` records from Supabase.
2.  **Visualization:** Displays sessions as a vertical stream of cards.
    *   Header: Asset + Timestamp + Decision.
    *   Body: Collapsible details showing Sentiment Score, Tech Indicators, and the Reasoning Text.
3.  **Visual Polish:** Use color coding (Green for Buy, Red for Sell, Grey for Hold).
4.  **Performance:** Uses "Infinite Scroll" or simple Pagination to handle history.

## Tasks / Subtasks
- [ ] Data Fetching
    - [ ] Create Server Action or API route to fetch `CouncilSession` joined with `Asset`.
- [ ] Feed Component UI
    - [ ] Build `CouncilCard.tsx`.
    - [ ] Implement `Accordion` for expanding the reasoning text.
    - [ ] Add "Vote Visuals" (e.g., a progress bar for Sentiment Score).
- [ ] Integration
    - [ ] Render the feed in the left column of the Dashboard.

## Dev Notes
- **Key Feature:** This is the "Killer Feature" of the UI. Spend time making the typography readable (JetBrains Mono for data).
- **Format:** Display the `reasoningLog` as Markdown if the AI outputs markdown, or pre-formatted text.
```

---

### **File 3: `docs/stories/story-4.3.positions-scanner.md`**

```markdown
# Story 4.3: Active Positions & Market Scanner

**Status:** Draft

## Story
**As a** User,
**I want** to see my open trades and a heatmap of potential opportunities,
**so that** I know my current P&L and what the bot is watching.

## Acceptance Criteria
1.  **Active Trades Widget:** Displays `Trade` records where `status = OPEN`.
    *   Shows Entry Price, Current Price (mocked/fetched), and live P&L %.
    *   Visualizes the distance to the "Stop Loss."
2.  **Market Scanner:** Table showing the Top 30 Assets.
    *   Columns: Symbol, Last Price, Sentiment Score, Tech Signal.
    *   Sortable by "Fear Score" (Sentiment).

## Tasks / Subtasks
- [ ] Active Trades Component
    - [ ] Fetch `Trade` data.
    - [ ] Calculate live P&L (Current Price - Entry Price).
    - [ ] Create `TradeCard.tsx` with a mini progress bar for Stop Loss distance.
- [ ] Scanner Table
    - [ ] Use `TanStack Table` (Shadcn Data Table).
    - [ ] Fetch latest `Candle` and `SentimentLog` for all assets.
    - [ ] Implement sorting logic.
- [ ] Charts
    - [ ] Install `recharts`.
    - [ ] (Optional V1) Add a mini sparkline to the Trade Card.

## Dev Notes
- **Real-time Price:** For V1, using the last fetched `Candle` price (15m old) is fine for the Scanner. For Active Trades, we might want a client-side fetch to Kraken public ticker for real-time P&L accuracy.
```

---

### **File 4: `docs/stories/story-4.4.realtime-updates.md`**

```markdown
# Story 4.4: Realtime Realization (Supabase)

**Status:** Draft

## Story
**As a** User,
**I want** the dashboard to update automatically when the bot acts,
**so that** I don't have to manually refresh the page to see new signals.

## Acceptance Criteria
1.  Dashboard subscribes to Supabase Realtime changes on `CouncilSession` and `Trade` tables.
2.  When a new Council Session is inserted (by the Python bot), the Feed automatically shows the new card at the top.
3.  When a Trade status changes (e.g., STOPPED OUT), the Active Trades UI updates instantly.
4.  Toast notifications appear for major events ("New Buy Signal: SOL/USD").

## Tasks / Subtasks
- [ ] Supabase Client Setup
    - [ ] Configure `supabase-js` client for client-side usage.
- [ ] Realtime Hooks
    - [ ] Create `useCouncilListener` hook.
    - [ ] Create `useTradeListener` hook.
- [ ] Toast Integration
    - [ ] Use `Sonner` (Shadcn default) to trigger alerts on `INSERT` events.
- [ ] Testing
    - [ ] Manually insert a record in Supabase Table Editor and verify UI updates without refresh.

## Dev Notes
- **UX Magic:** This makes the app feel "alive." Ensure the subscription cleans up properly (useEffect return) to prevent memory leaks.
```

---

**All Epics are mapped.**

You have a complete execution plan:
1.  **Epic 1:** Build the Data Foundation (Monorepo, Python, Kraken).
2.  **Epic 2:** Build the AI Brain (LangGraph, Gemini).
3.  **Epic 3:** Enable Execution (Trading, Stops).
4.  **Epic 4:** Visualize it (Next.js Dashboard).

**Project Initialization Complete.**

To begin development, you (or the Developer Agent) should start with **Story 1.1**.

**Would you like me to switch to the Developer Agent (`*agent dev`) to start coding Story 1.1, or do you have any other planning questions?**