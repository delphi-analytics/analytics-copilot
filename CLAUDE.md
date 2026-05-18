# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Data Visualization Copilot — an AI-powered analytics platform where users ask questions in natural language and get interactive charts, SQL queries, and insights. Built with a LangGraph agent pipeline that processes questions through 7 steps: intent understanding, schema discovery, SQL generation, query execution, insight analysis, visualization configuration, and response composition.

## Development Commands

```bash
# Start the full application (backend + frontend)
./start.sh

# Or run with Docker Compose
docker compose up -d

# Backend only (after venv setup)
source venv/bin/activate
PYTHONPATH=. python -m uvicorn backend.main:app --host 0.0.0.0 --port 8001 --reload

# Frontend only (dev mode with hot reload)
cd frontend && npm run dev

# Build frontend for production
cd frontend && npm run build

# Install dependencies
pip install -r requirements.txt
pip install qdrant-client fastembed redis  # For optional vector memory
```

## Architecture

### Backend Agent Pipeline (`backend/agent/`)

The core is a **LangGraph StateGraph** with 7 nodes that process `AnalyticsState`:

1. **intent** (`intent.py`) — Classifies question type, extracts entities, detects follow-ups
2. **schema** (`schema.py`) — Discovers relevant tables/columns using DB Intelligence
3. **sql_gen** (`sql_gen.py`) — Generates SQL using schema context + conversation history
4. **executor** (`executor.py`) — Executes SQL against datasource (SQLite, PostgreSQL, ClickHouse, CSV)
5. **analyst** (`analyst.py`) — Analyzes results for insights, key metrics, anomalies
6. **viz_config** (`viz_config.py`) — Generates Apache ECharts configuration
7. **responder** (`responder.py`) — Composes final response with follow-up questions

Entry point: `run_analytics_agent()` in `backend/agent/graph.py`

### DB Intelligence Layer (`backend/services/db_intelligence.py`)

Scans the connected ClickHouse database on startup and caches comprehensive schema context:
- Column types, unique counts, exact categorical values (≤200 unique)
- Business facts (total revenue, order counts, date ranges)
- Column annotations (which columns to use for revenue, units, dates)
- Global query rules (mandatory filters, JOIN patterns, ClickHouse functions)

Context stored at `/tmp/dvc_metadata/db_intelligence.json`, refreshes every 24 hours.

### LLM Routing (`backend/agent/llm.py`)

Uses LiteLLM for provider-agnostic calls. Model routing:
- `llm_fast_model` (groq/llama-3.1-8b-instant) — Intent classification, routing
- `llm_smart_model` (groq/llama-3.3-70b-versatile) — SQL generation, insights
- `llm_premium_model` (anthropic/claude-sonnet-4-6) — Complex analysis (optional)
- Automatic fallback on rate limits with 15s backoff

### Data Connector (`backend/data/connector.py`)

Universal connector supporting: SQLite, PostgreSQL, ClickHouse, CSV/Excel (via DuckDB). Schema introspection cached per datasource for 1 hour.

### Frontend (`frontend/`)

React + TypeScript + Vite, served from `backend/static/` after build.
- **Charts**: Apache ECharts via `echarts-for-react`
- **State**: Zustand store (`frontend/src/store/chat.ts`)
- **API**: Axios client (`frontend/src/api/client.ts`)
- **Styling**: TailwindCSS

### Key API Endpoints

- `POST /api/v1/copilot/query` — Main chat endpoint, returns chart + insights
- `POST /api/v1/copilot/upload` — Upload CSV/Excel for analysis
- `GET /api/v1/db/context` — Get DB intelligence context summary
- `POST /api/v1/db/context/refresh` — Trigger database scan

## Configuration

Environment variables in `.env`:
- `GROQ_API_KEY` — Required for free LLM access
- `DATABASE_URL` — SQLite default, PostgreSQL for production
- `REDIS_URL` — For caching (optional)
- `QDRANT_URL` — Vector memory (disabled by default)

See `.env.example` for all options.

## Datasources

Two datasources registered on startup:
- **default** — SQLite demo database (`./demo.db`) with sales, users, tickets tables
- **limese** — ClickHouse production database (hosted, read-only access for analytics)

Register new datasources via `POST /api/v1/copilot/datasource`.

## LLM Cache

Successful queries cached for 15 minutes (Canary pattern) — check `backend/services/llm_cache.py`. Cache checked before running agent pipeline for non-follow-up questions.
