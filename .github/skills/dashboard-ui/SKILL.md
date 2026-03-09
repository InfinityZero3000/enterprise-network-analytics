---
name: dashboard-ui
description: "Create professional web dashboard UIs with React, Tailwind CSS, and Recharts. Use when: building dashboards, creating admin panels, designing operations monitoring pages, inventory tracking, analytics visualization, data tables, KPI cards, stock alerts, charts, supply chain status. Generates production-ready React + TypeScript + Tailwind code with responsive layouts, dark/light themes, and interactive charts."
argument-hint: "Describe the dashboard purpose (e.g., 'inventory monitoring dashboard with stock alerts')"
---

# Dashboard UI Generator

## When to Use
- User asks to create a web dashboard, admin panel, or monitoring page
- User provides mockup images or describes dashboard layouts
- User needs charts, KPI cards, data tables, alerts, or status indicators
- User wants operations/inventory/analytics/supply-chain dashboards
- User asks for React + Tailwind UI components

## Design Principles

### Visual Hierarchy
1. **KPI Cards at top** — large numbers, clear labels, color-coded status
2. **Charts in middle** — line charts for trends, bar charts for comparisons, donut/gauge for utilization
3. **Data tables at bottom** — sortable, filterable, with status badges
4. **Sidebar for navigation** — icon-based, collapsible

### Color System
Use a consistent, professional palette:
- **Primary**: `#1E3A5F` (deep navy) — headers, sidebar, primary actions
- **Secondary**: `#3B82F6` (blue) — active states, links, chart accents
- **Success**: `#10B981` (green) — in-stock, active, healthy
- **Warning**: `#F59E0B` (amber) — low stock, attention needed
- **Danger**: `#EF4444` (red) — critical alerts, out of stock, errors
- **Background**: `#F1F5F9` (light gray) — page background
- **Card**: `#FFFFFF` — card surfaces with subtle shadow
- **Text Primary**: `#1E293B` — headings
- **Text Secondary**: `#64748B` — labels, descriptions

### Typography
- Headings: `font-semibold` or `font-bold`, larger sizes
- KPI Numbers: `text-3xl font-bold` or `text-4xl font-bold`
- Labels: `text-sm text-gray-500`
- Table text: `text-sm`
- Font family: Inter or system-ui

### Spacing & Layout
- Page padding: `p-6`
- Card padding: `p-4` or `p-6`
- Card gap: `gap-4` or `gap-6`
- Border radius: `rounded-xl` for cards, `rounded-lg` for inner elements
- Card shadow: `shadow-sm` or `shadow-md`
- Use CSS Grid (`grid grid-cols-12`) for main layout

### Interactive Elements
- Hover states on cards: `hover:shadow-lg transition-shadow`
- Status badges: rounded-full with colored background
- Buttons: clear primary/secondary distinction
- Dropdown filters with clean styling

## Tech Stack

| Tool | Purpose |
|------|---------|
| React 18+ | UI framework |
| TypeScript | Type safety |
| Tailwind CSS 3+ | Utility-first styling |
| Recharts | Charts (LineChart, BarChart, PieChart, RadialBarChart) |
| Lucide React | Icons (consistent, clean) |
| clsx or cn() | Conditional class merging |

## Procedure

### Step 1 — Analyze Requirements
Read user description or mockup images. Identify:
- Dashboard purpose (operations, inventory, analytics, etc.)
- Required widgets: KPI cards, charts, tables, alerts, maps
- Data entities: products, orders, users, revenue, stock levels
- Filters needed: date range, category, status

### Step 2 — Scaffold Project
If no React project exists:
```bash
npx create-vite@latest dashboard --template react-ts
cd dashboard
npm install
npm install -D tailwindcss @tailwindcss/vite
npm install recharts lucide-react clsx
```

Configure [Tailwind with Vite plugin](./references/tailwind-setup.md).

### Step 3 — Create Layout Structure
```
src/
├── components/
│   ├── layout/
│   │   ├── Sidebar.tsx
│   │   ├── Header.tsx
│   │   └── DashboardLayout.tsx
│   ├── cards/
│   │   ├── KPICard.tsx
│   │   ├── AlertCard.tsx
│   │   └── StatCard.tsx
│   ├── charts/
│   │   ├── LineChartWidget.tsx
│   │   ├── BarChartWidget.tsx
│   │   ├── DonutChart.tsx
│   │   └── GaugeChart.tsx
│   ├── tables/
│   │   └── DataTable.tsx
│   └── common/
│       ├── Badge.tsx
│       ├── Card.tsx
│       └── FilterBar.tsx
├── data/
│   └── mockData.ts
├── types/
│   └── dashboard.ts
├── App.tsx
└── main.tsx
```

### Step 4 — Build Components (order matters)
1. **Card wrapper** — reusable card with title, optional action button
2. **KPI cards** — big number + label + trend indicator + icon
3. **Charts** — wrap Recharts with consistent styling and responsive container
4. **Data tables** — header row, sortable columns, status badges
5. **Sidebar** — icon nav, active state, collapsible
6. **Layout** — grid composition of all widgets

### Step 5 — Apply Dashboard Patterns

#### KPI Card Pattern
```tsx
<div className="bg-white rounded-xl shadow-sm p-6">
  <div className="flex items-center justify-between mb-2">
    <span className="text-sm text-gray-500">{label}</span>
    <Icon className="h-5 w-5 text-blue-500" />
  </div>
  <div className="text-3xl font-bold text-gray-900">{value}</div>
  <div className="flex items-center mt-2 text-sm">
    <TrendingUp className="h-4 w-4 text-green-500 mr-1" />
    <span className="text-green-600">{change}</span>
  </div>
</div>
```

#### Chart Card Pattern
```tsx
<div className="bg-white rounded-xl shadow-sm p-6">
  <div className="flex items-center justify-between mb-4">
    <h3 className="text-lg font-semibold text-gray-900">{title}</h3>
    <select className="text-sm border rounded-lg px-3 py-1">{filters}</select>
  </div>
  <ResponsiveContainer width="100%" height={300}>
    <LineChart data={data}>...</LineChart>
  </ResponsiveContainer>
</div>
```

#### Alert/Status Card Pattern (colored header)
```tsx
<div className="rounded-xl shadow-sm overflow-hidden">
  <div className="bg-red-600 text-white p-4">
    <h3 className="font-semibold">{title}</h3>
    <div className="text-3xl font-bold mt-1">{count}</div>
  </div>
  <div className="bg-white p-4 space-y-2">{items}</div>
</div>
```

#### Status Badge Pattern
```tsx
<span className={clsx(
  "px-2.5 py-0.5 rounded-full text-xs font-medium",
  status === "in_stock" && "bg-green-100 text-green-700",
  status === "low_stock" && "bg-amber-100 text-amber-700",
  status === "critical" && "bg-red-100 text-red-700",
)}>{label}</span>
```

#### Supply Chain Pipeline Pattern
```tsx
<div className="flex items-center gap-2">
  {stages.map((stage, i) => (
    <Fragment key={i}>
      <div className={clsx("px-4 py-2 rounded-lg text-sm font-medium", stage.color)}>
        {stage.label}
      </div>
      {i < stages.length - 1 && <ChevronRight className="h-4 w-4 text-gray-400" />}
    </Fragment>
  ))}
</div>
```

### Step 6 — Responsive Design
- Mobile: single column, cards stack vertically
- Tablet: 2-column grid
- Desktop: full grid (sidebar + 3-4 column content)
```tsx
<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
```

### Step 7 — Populate with Realistic Mock Data
Always generate realistic-looking data. Never use lorem ipsum for dashboards.
Use domain-appropriate labels, numbers, and date ranges.

## Chart Styling Reference

### Recharts Consistent Theme
```tsx
const CHART_COLORS = {
  primary: '#3B82F6',
  secondary: '#8B5CF6',
  success: '#10B981',
  warning: '#F59E0B',
  danger: '#EF4444',
  gray: '#94A3B8',
};

// Common Recharts props
const chartDefaults = {
  strokeWidth: 2,
  dot: false,
  activeDot: { r: 6, strokeWidth: 0 },
};
```

### Gauge / Radial Chart (for utilization %)
Use `RadialBarChart` from Recharts with custom center label.

### Donut Chart (for category breakdown)
Use `PieChart` with `innerRadius` prop for donut style.

## Sidebar Reference

### Icon-based Sidebar
```tsx
const navItems = [
  { icon: LayoutDashboard, label: 'Dashboard', path: '/' },
  { icon: Package, label: 'Inventory', path: '/inventory' },
  { icon: ShoppingCart, label: 'Orders', path: '/orders' },
  { icon: BarChart3, label: 'Analytics', path: '/analytics' },
  { icon: Settings, label: 'Settings', path: '/settings' },
];
```

## Checklist Before Delivery
- [ ] All cards have consistent border-radius and shadow
- [ ] Color coding is consistent (green=good, amber=warning, red=critical)
- [ ] Charts are wrapped in ResponsiveContainer
- [ ] Mobile responsive (test with grid-cols breakpoints)
- [ ] Mock data is realistic and domain-appropriate
- [ ] No hardcoded pixel widths (use Tailwind responsive classes)
- [ ] Interactive hover/focus states present
- [ ] Sidebar has active state indicator
- [ ] KPI cards show trend direction (up/down arrow + color)
- [ ] Tables have status badges, not raw text
