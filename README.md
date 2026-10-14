# UNI Automated Ordering System

> **Internship project** — built by Leonid Fesiuk as an unpaid intern for
> a real retail company (2025–2026). All sensitive data (database
> credentials, internal IPs, private domains) has been removed and
> replaced with environment variable placeholders.

---

## What This System Does

A full-stack ERP module that automates the daily ordering workflow of a
retail chain with multiple warehouses and market locations. Before this
system, category managers spent hours manually calculating restock
quantities in Excel. After deployment, the same work is done in minutes
through a web interface.

The system answers four business questions automatically:

1. **How much should we order?** — calculates replenishment quantities
   based on sales velocity, seasonality, promo calendar, and supplier
   lead times
2. **Where should stock be moved?** — generates redistribution plans
   between markets that have excess and markets that are short
3. **What will sell during a promotion?** — forecasts demand with and
   without a promo using a fine-tuned Chronos-2 AI model in a separate
   forecasting service, including margin impact per product
4. **What are we losing?** — identifies out-of-stock products,
   archive candidates, and lost revenue from supply gaps

---

## How It Works

Every morning the system reads live ERP data (sales history, stock
levels, promo calendar, weather, supplier lead times) and turns it
into concrete decisions:

```
                  ┌────────────────────────────────────┐
                  │   UNI AUTOMATED ORDERING SYSTEM    │
                  │                                    │
                  │   Reads from ERP every morning:    │
                  │     • sales history & stock        │
                  │     • promo calendar               │
                  │     • weather & holidays           │
                  │     • supplier lead times          │
                  │                                    │
                  │   Answers:                         │
                  │     • How much should we buy?      │
                  │     • Where should stock go?       │
                  │     • What will sell on promo?     │
                  │     • What are we losing?          │
                  └──────────────────┬─────────────────┘
                                     │
           ┌─────────────────────────┴─────────────────────────┐
           ▼                                                   ▼
┌────────────────────────────┐               ┌────────────────────────────┐
│ BACKEND SERVICE            │               │ FORECASTING SERVICE        │
│ (business logic — math,    │               │ (AI — neural network)      │
│  rules & optimisation)     │               │                            │
│                            │               │ Kronos-2 (Chronos-2)       │
│ • ADS demand prediction    │               │ time-series model,         │
│ • ABC/XYZ classification   │               │ fine-tuned on 2 years      │
│ • safety stock insurance   │               │ of daily sales history     │
│ • greedy cost allocation   │               │                            │
└──────┬──────────────┬──────┘               └─────────────┬──────────────┘
       ▼              ▼                                    ▼
┌────────────────┐ ┌────────────────┐          ┌──────────────────────┐
│ PURCHASE ORDER │ │DISTRIBUTION PLN│          │ PROMO FORECAST       │
├────────────────┤ ├────────────────┤          ├──────────────────────┤
│ Supplier A     │ │ Store 003 ←120 │          │ Baseline:       450  │
│    240 pcs     │ │ Store 007 ← 85 │          │ With promo:     620  │
│ Supplier B     │ │ Store 012 ←200 │          │ Margin:      +12.4k  │
│    180 pcs     │ │ Store 021 ← 60 │          │ Lost:         34.2k  │
│ ────────────── │ │ ────────────── │          │ ──────────────────── │
│ Total:    420  │ │ Total:     465 │          │ AI prediction,       │
└────────────────┘ └────────────────┘          │ not a formula        │
                                               └──────────────────────┘
```

The two services run in parallel every morning. The **backend** is the
deterministic side — every decision comes from formulas, rules and
optimisation (ADS, ABC/XYZ analysis, safety stock, greedy allocation).
The **forecasting service** is the AI side — a neural network trained
on two years of real sales data learns demand patterns on its own and
produces numbers no formula could calculate.

- **Purchase order** — exact quantities to buy from each supplier,
  respecting pack size and lead time
- **Distribution plan** — exact quantities to ship from each warehouse
  to each market that is running short
- **Promo forecast** — the AI service predicts baseline vs promo sales
  per product per day, with margin impact and loss alerts

---

## Key Business Logic

### Auto-Ordering Engine
- **ADS — Average Daily Sales** (Ukrainian abbreviation SDP,
  "середньоденні продажі") — weighted moving average of daily sales
  with seasonality adjustments
- **ABC/XYZ classification** — vectorized product prioritisation for
  order allocation when supplier capacity is limited
- **Insurance balance** — safety stock that scales with lead time and
  demand volatility; doubles when stock covers fewer than 2 days
- **Promo-aware ordering** — future promotions are factored into demand
  so the system orders ahead of campaign starts

### Market Redistribution
Generates transfer orders between locations using a greedy allocator
that minimises transport cost while respecting pack-size constraints
(products can only move in multiples of their case pack).

### Forecasting Service (AI)

A standalone microservice (`backend_forecasting/`) that runs in
parallel with the backend — while the backend calculates, the
forecasting service predicts.

- **Kronos-2 (Chronos-2)** — a time-series neural network, fine-tuned
  on two years of daily sales history, with cross-learning across
  products in the same category
- The fine-tuned checkpoint is loaded from a local path
  (`models/kronos2`) at service start
- The model sees everything that shapes demand, not just sales: sales
  history, daily prices, promo flags, **weather** (morning and
  afternoon feels-like temperature, **rain/precipitation IDs**),
  **public holidays**, and the 5-level product category hierarchy
- Runs two scenarios — "with promo" and "baseline" — and outputs the
  margin impact per product per day, exported to Excel for category
  managers

**Why a separate AI service?** The backend is a mathematical-logic
model: fixed formulas and rules that a manager can audit line by line.
Promo forecasting is a prediction problem — it needs a model that
learns non-linear patterns (seasonality, weather, holidays,
price-promo interaction) from historical data instead of computing
them. Keeping it separate means the AI can be retrained and redeployed
without touching the order-calculating code, and the core ERP keeps
working even when the model is unavailable (fallback adapter).

---

## Architecture

```
Frontend (React 18 + MUI)
    │  REST
    ├──────────────────────────────┐
    ▼                              ▼
Backend (FastAPI + SQLAlchemy)    Forecasting Service (Clean Architecture)
    │  ├─ autoorder/              │  ├─ core/domain/      entities, value objects
    │  ├─ autoorder_m/            │  ├─ core/usecases/    forecast_for_group, build_features
    │  ├─ redistribution/         │  ├─ core/ports/       DataInputGateway, AIPort interfaces
    │  ├─ insurance_balance/      │  └─ adapters/         ERP gateway, Kronos-2, fallback, fake
    │  ├─ out_product/            │
    │  ├─ sales_looses/           │
    │  └─ prices/                 │
    │                             │
    └──────────────┬──────────────┘
                   ▼
Data Layer
├─ MySQL    live ERP data (products, prices, promos, receipts)
└─ PostgreSQL generated orders and forecast results
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| API | FastAPI, Hypercorn, Pydantic v2 |
| ORM | SQLAlchemy 2.0 (declarative, session-per-request with retry) |
| Databases | MySQL 8 (ERP source), PostgreSQL 15 (order storage) |
| Frontend | React 18, Vite 6, Material-UI 6, React Router 7 |
| ML Forecasting | PyTorch, Kronos-2 / Chronos-2 (fine-tuned), NumPy/Pandas |
| Excel Export | openpyxl, xlsxwriter, SheetJS (browser-side) |
| Infrastructure | Docker, Docker Compose, Nginx reverse proxy |

---

## Project Structure

```
UNI_ALL_DEV/
├── backend/
│   ├── api/                  FastAPI app, helpers, Excel export
│   ├── autoorder/            warehouse ordering, analysis, DB layer
│   ├── autoorder_m/          market auto-ordering with category groups
│   ├── redistribution/       inter-market stock transfer engine
│   ├── insurance_balance/    safety stock calculator
│   ├── out_product/          out-of-stock, archive, market-down analysis
│   ├── sales_looses/         lost sales revenue tracking
│   ├── prices/               price + stock snapshot service
│   ├── gui/                  legacy Flask dashboard
│   └── nginx/                reverse proxy config
│
├── backend_forecasting/      Forecasting microservice
│   ├── core/
│   │   ├── domain/           PromoScenario, ForecastResult entities
│   │   ├── usecases/         forecast_for_group, build_features
│   │   ├── features.py       shared pandas transformations
│   │   ├── gateway/          DataInputGateway port
│   │   └── ports/            AIPort interface
│   ├── adapters/
│   │   ├── primary/          FastAPI router
│   │   └── secondary/        ERP gateway, Kronos-2, fallback, fake
│   ├── config/               settings, weather, holidays, categories
│   └── scripts/              demo dataset generators
│
└── frontend/
    └── src/
        ├── components/
        │   ├── autoorderw/   warehouse ordering UI
        │   ├── autoorderm/   market ordering UI
        │   ├── insurance/    insurance balance UI
        │   ├── redistribution/ stock transfer UI
        │   ├── outProducts/  out-product analysis UI
        │   ├── salesLooses/  sales loss UI
        │   └── deshboard/    overview dashboard
        └── services/         API client, date validation
```

---

## Getting Started

### Prerequisites

- Docker & Docker Compose
- Node.js 20+ (for local frontend development)

### Setup

1. Clone the repository:
```bash
git clone https://github.com/leonfesjuk/UNI_ALL_DEV.git
cd UNI_ALL_DEV
```

2. Create environment files:
```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
# Edit both files with your own database credentials and API URL
```

3. Start the application:
```bash
cd backend
docker-compose up --build
```

The application will be available at:
- Frontend: http://localhost:5000
- API: http://localhost:8000
- API Docs: http://localhost:8000/docs

---

## Environment Variables

### Backend (`backend/.env`)

| Variable | Description |
|----------|-------------|
| `DB_MYSQL_HOST` | MySQL server host |
| `DB_MYSQL_PORT` | MySQL server port |
| `DB_MYSQL_USER` | MySQL username |
| `DB_MYSQL_PASSWORD` | MySQL password |
| `DB_MYSQL_DATABASE` | MySQL database name |
| `DB_POSTGRES_HOST` | PostgreSQL server host |
| `DB_POSTGRES_PORT` | PostgreSQL server port |
| `DB_POSTGRES_USER` | PostgreSQL username |
| `DB_POSTGRES_PASSWORD` | PostgreSQL password |
| `DB_POSTGRES_DATABASE` | PostgreSQL database name |

### Frontend (`frontend/.env`)

| Variable | Description |
|----------|-------------|
| `VITE_PORT` | Development server port |
| `VITE_API_BASE_URL` | Backend API base URL |

---

## Security Notice

This repository is a **sanitised public version** of a production
internship project. The following has been removed or replaced:

- All database credentials (moved to `.env` files, git-ignored)
- Internal IP addresses and private domain names
- Real product, supplier, and customer identifiers
- Generated data files (`.parquet`, model weights, caches)
- Compiled bytecode (`__pycache__`)

The `.env.example` files contain only placeholder values. No real
secrets exist in the git history or the current working tree.

---

## License

This project is proprietary and confidential.
Built as an unpaid internship project for a private retail company.
