# UNI Automated Ordering System

Enterprise ERP system for automated ordering, redistribution, and demand forecasting in retail.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Frontend (React)                      │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐   │
│  │AutoOrder │ │Insurance │ │Redistrib.│ │  Dashboard   │   │
│  └──────────┘ └──────────┘ └──────────┘ └──────────────┘   │
└────────────────────────┬────────────────────────────────────┘
                         │ REST API
┌────────────────────────▼────────────────────────────────────┐
│                    Backend (FastAPI)                         │
│  ┌──────────────┐ ┌──────────────┐ ┌────────────────────┐  │
│  │ Auto-Order   │ │Redistribution│ │  Price Analysis    │  │
│  │  (Warehouse) │ │   Engine     │ │  (Out Products)    │  │
│  └──────────────┘ └──────────────┘ └────────────────────┘  │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│              Backend Forecasting (Clean Arch)                │
│  ┌──────────────┐ ┌──────────────┐ ┌────────────────────┐  │
│  │   Domain     │ │  Use Cases   │ │     Adapters       │  │
│  │ (Entities)   │ │ (Forecasting)│ │ (Kronos-2, ERP)    │  │
│  └──────────────┘ └──────────────┘ └────────────────────┘  │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│                  Data Layer                                  │
│  ┌──────────────┐              ┌────────────────────┐       │
│  │    MySQL     │              │    PostgreSQL      │       │
│  │  (ERP Data)  │              │  (Order Storage)   │       │
│  └──────────────┘              └────────────────────┘       │
└─────────────────────────────────────────────────────────────┘
```

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Backend API | FastAPI, Hypercorn |
| ORM | SQLAlchemy 2.0 |
| Databases | MySQL 8, PostgreSQL 15 |
| Frontend | React 18, Vite, Material-UI |
| Forecasting | PyTorch, Chronos-2 |
| Containerization | Docker, Docker Compose |
| Proxy | Nginx |

## Features

- **Auto-Ordering** — Automated order calculation for warehouse restocking
- **Market Redistribution** — Intelligent stock redistribution between markets
- **Insurance Balance** — Safety stock calculation with seasonality
- **Demand Forecasting** — ML-based sales prediction using Chronos-2
- **Price Analysis** — Out-product and market-down identification
- **Sales Loss Tracking** — Lost revenue analysis

## Project Structure

```
UNI_ALL_DEV/
├── backend/                    # FastAPI backend
│   ├── api/                   # API routes and helpers
│   ├── autoorder/             # Auto-ordering logic
│   ├── autoorder_m/           # Market auto-ordering
│   ├── redistribution/        # Redistribution engine
│   ├── insurance_balance/     # Insurance balance calc
│   ├── out_product/           # Out-product analysis
│   ├── sales_looses/          # Sales loss tracking
│   └── config/                # Configuration
│
├── backend_forecasting/       # Forecasting service (Clean Architecture)
│   ├── core/
│   │   ├── domain/           # Entities, value objects
│   │   ├── usecases/         # Business logic
│   │   └── ports/            # Interfaces
│   ├── adapters/
│   │   ├── primary/          # API adapters
│   │   └── secondary/        # Data/AI adapters
│   └── config/               # Settings
│
├── frontend/                  # React frontend
│   └── src/
│       ├── components/       # UI components
│       └── services/         # API clients
│
└── docker-compose.yml         # Orchestration
```

## Getting Started

### Prerequisites

- Docker & Docker Compose
- Node.js 20+ (for local frontend development)

### Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd UNI_ALL_DEV
```

2. Create environment files:
```bash
# Backend
cp backend/.env.example backend/.env
# Edit backend/.env with your database credentials

# Frontend
cp frontend/.env.example frontend/.env
# Edit frontend/.env with your API URL
```

3. Start the application:
```bash
docker-compose up --build
```

The application will be available at:
- Frontend: http://localhost:5000
- API: http://localhost:8000
- API Docs: http://localhost:8000/docs

## Environment Variables

### Backend (.env)

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

### Frontend (.env)

| Variable | Description |
|----------|-------------|
| `VITE_PORT` | Development server port |
| `VITE_API_BASE_URL` | Backend API base URL |

## API Documentation

Once running, interactive API documentation is available at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## License

This project is proprietary and confidential.
