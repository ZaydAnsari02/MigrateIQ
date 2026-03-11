# MigrateIQ — AI-powered BI Migration Validation Platform

Enterprise dashboard for automated Tableau → Power BI migration validation.

## Tech Stack

- **Framework**: Next.js 14 (App Router)
- **Language**: TypeScript
- **Styling**: Tailwind CSS
- **UI Components**: Custom (shadcn-compatible primitives)
- **HTTP Client**: Axios
- **Charts**: Recharts

## Project Structure
## frontend:

```
src/
├── app/
│   ├── globals.css          # Global styles + DM Sans font
│   ├── layout.tsx           # Root HTML layout + metadata
│   └── page.tsx             # Main dashboard page (orchestrator)
│
├── components/
│   ├── ui/
│   │   ├── Badge.tsx        # StatusBadge, LayerDot, SeverityBadge, RunStatusChip
│   │   ├── Button.tsx       # Button with variants: primary / secondary / ghost / danger
│   │   └── Card.tsx         # Card, CardHeader, CardBody, SummaryCard
│   │
│   ├── layout/
│   │   ├── Sidebar.tsx      # Collapsible left nav with user footer
│   │   └── Header.tsx       # Top bar with brand, status indicator, actions
│   │
│   ├── dashboard/
│   │   ├── DashboardOverview.tsx   # Summary cards + pass rate + activity feed
│   │   └── RunsTable.tsx           # Validation run history table
│   │
│   ├── upload/
│   │   └── UploadSection.tsx       # 4-zone drag-and-drop file uploader
│   │
│   ├── results/
│   │   ├── ResultsTable.tsx        # Filterable report pairs table
│   │   └── DetailPanel.tsx         # Per-report layer breakdown + screenshot comparison + diffs
│   │
│   └── comparison/
│       └── ComparisonExplorer.tsx  # Side-by-side report pair explorer
│
├── services/
│   └── validationService.ts  # All API calls (projectService, runService, reportService, layerService)
│
├── hooks/
│   └── index.ts              # useUpload, useSidebar, useSelection, useAsync
│
├── lib/
│   └── utils.ts              # cn(), getStatusColors(), computeStats(), formatDate(), formatDuration()
│
├── types/
│   └── index.ts              # All TypeScript interfaces and enums
│
└── constants/
    └── index.ts              # NAV_ITEMS, UPLOAD_ZONES, MOCK_PROJECT, MOCK_RUNS, MOCK_REPORT_PAIRS
```

## Three Validation Layers

| Layer | Name     | Technology             | What it checks                                    |
|-------|----------|------------------------|---------------------------------------------------|
| L1    | Visual   | Pixel diff + GPT-4o    | Screenshot similarity, chart types, layout, labels |
| L2    | Semantic | Claude Sonnet          | Tableau calc fields vs DAX — semantic equivalence  |
| L3    | Data     | SQL regression         | Row counts, KPI aggregations, metric values        |

## Getting Started

```bash
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

## Connecting to the Backend

Set `NEXT_PUBLIC_API_URL` in `.env.local`:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Then uncomment the real `axios` calls in `src/services/validationService.ts`
and remove the mock delay + mock data returns.

## Environment Variables

| Variable                | Description                   | Default                  |
|-------------------------|-------------------------------|--------------------------|
| `NEXT_PUBLIC_API_URL`   | FastAPI backend base URL      | `http://localhost:8000`  |
