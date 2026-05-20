# AGENTS.md — Data Visualization Copilot

## What this project is

An AI-powered analytics platform where users type questions in natural language and get back interactive Apache ECharts, SQL, key metrics, and follow-up suggestions. Built around a **LangGraph StateGraph** pipeline that orchestrates 7 async nodes. Targets the **Limese** (beauty brand) ClickHouse database as its primary datasource, with a SQLite demo DB for local testing.

## Repository layout

```
analytics_copilot/
├── backend/
│   ├── main.py              # FastAPI app entry point, startup logic, all /api routes
│   ├── config.py            # All settings from .env via pydantic-settings
│   ├── agent/               # LangGraph pipeline + LLM routing
│   │   ├── graph.py         # Non-streaming pipeline (main query path)
│   │   ├── streaming_graph.py  # SSE-capable pipeline with real node-level progress
│   │   ├── llm.py           # LiteLLM wrapper with multi-model fallback chain
│   │   ├── memory.py        # Qdrant vector memory for semantic query cache
│   │   ├── pre_filter.py    # Minimal rule-based greeting skip
│   │   ├── state.py         # TypedDict AnalyticsState — the one shared state object
│   │   └── nodes/           # Each pipeline node is a pure async function
│   │       ├── intent.py    # Node 1: LLM intent classification
│   │       ├── schema.py    # Node 2: DB Intelligence table/column selection
│   │       ├── sql_gen.py   # Node 3: LLM SQL generation with DB context
│   │       ├── executor.py  # Node 4: Execute SQL, one auto-fix attempt for ClickHouse errors
│   │       ├── analyst.py   # Node 5: LLM insight & anomaly analysis
│   │       ├── viz_config.py  # Node 6: Apache ECharts JSON config generation
│   │       ├── responder.py # Node 7: Compose final response + follow-ups
│   │       └── insight_followup.py  # Handles "why is this happening?" follow-ups
│   ├── data/
│   │   ├── connector.py     # Universal connector (SQLite, PostgreSQL, ClickHouse, CSV/DuckDB)
│   │   └── clickhouse_connector.py  # Raw ClickHouse client wrapper
│   ├── services/
│   │   ├── db_intelligence.py  # Deep-scan ClickHouse schema, builds context, auto-caches to disk
│   │   ├── llm_cache.py     # 15-min Canary pattern SQL cache
│   │   ├── business_rag.py # Hardcoded glossary, metric defs, platform Q&A for LLM context
│   │   └── ...
│   ├── routers/
│   │   ├── copilot.py      # Main POST /query endpoint
│   │   ├── streaming.py    # GET/POST /stream SSE endpoint (real progress)
│   │   └── dashboards.py
│   └── models/             # SQLAlchemy models (Conversation, Message, etc.)
├── frontend/src/
│   ├── pages/CopilotPage.tsx   # Main React page, SSE connection, chat UI
│   ├── store/chat.ts        # Zustand store (sessions, messages, loading state)
│   ├── api/client.ts        # Axios API client (REST + SSE)
│   └── components/Chat/     # ChatMessage, ChatInput, charts
├── demo.db                  # SQLite demo with sales, users, support_tickets (2000 rows)
├── start.sh                 # Full dev launcher (venv + deps + Redis/Qdrant + frontend build + uvicorn)
├── docker-compose.yml       # Redis + Qdrant for vector memory
└── requirements.txt
```

## End-to-end request flow

```
User types question
        │
        ▼
FastAPI POST /api/v1/copilot/query (copilot.py)
        │  (or GET/POST /stream for SSE progress)
        ▼
run_analytics_agent()  [graph.py]
        │
        ▼
pre_filter() — rule-based greeting skip (no LLM cost)
        │
        ├─→ greeting/conversational/off_topic → skip_to_respond → compose_response → done
        │
        └─→ data query → understand_intent()  [Node 1, fast 8B LLM]
                     │  Intent: chart_request | data_query | analytical_question | etc.
                     ▼
               discover_schema()  [Node 2]
                     │  DB Intelligence context built from cached scan of ClickHouse
                     ▼
               generate_sql()  [Node 3, smart 70B LLM]
                     │  DB context injected as prompt (column annotations, exact values, rules)
                     ▼
               execute_sql()  [Node 4]
                     │  Execute against datasource, one auto-fix attempt if ClickHouse error
                     ▼
               analyze_insights()  [Node 5, smart 70B LLM]
                     │  Patterns, key_metrics, anomalies from query results
                     ▼
               generate_viz_config()  [Node 6]
                     │  Apache ECharts JSON (bar, line, pie, heatmap, gauge, table)
                     ▼
               compose_response()  [Node 7]
                     │  Natural language answer + follow-up questions
                     ▼
               Response → frontend
```

## Technologies by layer

| Layer | Technology | Purpose |
|---|---|---|
| **Frontend** | React 19 + TypeScript + Vite | SPA, hot reload dev |
| **UI state** | Zustand | Session/chat state |
| **Charts** | Apache ECharts (echarts-for-react) | Interactive visualizations |
| **Styling** | TailwindCSS | Utility CSS |
| **API** | FastAPI + uvicorn | REST endpoints, CORS, static file serving |
| **DB ORM** | SQLAlchemy 2.0 (async, aiosqlite) | Conversations/messages persistence |
| **Agent framework** | LangGraph 0.2.x | StateGraph DAG with conditional routing |
| **LLM calls** | LiteLLM | Provider-agnostic (Groq, Gemini, Claude, DeepSeek…) |
| **Vector memory** | Qdrant + FastEmbed (BAAI/bge-small) | Semantic query cache |
| **Data connectors** | sqlite3, asyncpg, clickhouse-connect, DuckDB | Universal datasource |
| **Structured logging** | structlog | JSON logs with context |
| **Auth** | python-jose JWT | Optional user auth |
| **Optional infra** | Redis (cache), MinIO (conversation store) | Per improvements |

## Key components in depth

### LangGraph Pipeline (graph.py)

Every node is an `async def (state: AnalyticsState) -> AnalyticsState`. LangGraph handles the DAG, state passing, and error propagation. `AnalyticsState` is a TypedDict with these fields flowing through all nodes:

```
session_id, conversation_id, user_question, datasource_id,
conversation_history, user_id
  → intent {type, chart_type_hint, entities, confidence}
  → schema_context {relevant_tables, columns}
  → sql_query
  → query_results {columns, rows, row_count}
  → insights, key_metrics, anomalies
  → viz_config (ECharts JSON), viz_type
  → final_response {text, chart, insights, follow_up_questions, sql}
```

Conditional routing after intent:
- `greeting/off_topic` → `skip_to_respond` (pre_filter handles it)
- `insight_followup` (e.g. "why is X dropping?") → dedicated node → `compose_response`
- `analytical_question` → still goes through full SQL pipeline but responds narratively
- Everything else → normal pipeline

### DB Intelligence (db_intelligence.py)

**On startup** a daemon thread scans the Limese ClickHouse and caches result to `backend/data/db_intelligence.json` (auto-refresh every 24h). It deep-scans these priority tables:
- `combined_sales_final` — main sales table (~340K orders)
- `product_master`, `product_catlog`, `inventory_sales_overview_new`, `platform_sku_mapping`, etc.

For each table it extracts: row count, column types, unique counts, exact categorical values (up to 200), date ranges, numerical ranges, business facts. **Hard-coded COLUMN_ANNOTATIONS** tell the LLM which column to use for revenue (`row_subtotal`), units (`quantity_ordered`), date filters, mandatory status exclusions, etc.

`build_sql_context_prompt()` converts this into a compact LLM prompt — only relevant tables, only useful columns, capped categorical values.

### LLM Routing (llm.py)

Uses LiteLLM. Three model tiers:
- `llm_fast_model` — Groq 8B for intent classification, routing (fast, cheap)
- `llm_smart_model` — Groq 70B for SQL generation, analysis
- `llm_premium_model` — Anthropic Claude (optional, for complex analysis)

Fallback chain per task: primary → Groq 8B → Gemini 1.5 Flash → Gemini 1.5 Pro → DeepSeek Coder → Mistral. Rate limits trigger 0.5s retry then fallback.

### Data Connector (connector.py)

`execute_query()` has a **two-layer read-only enforcement**: first checks that SQL starts with SELECT/WITH, then scans for modifying keywords (INSERT, UPDATE, DELETE, DROP, etc.). Even if validation is bypassed, the connector refuses execution.

Supported datasources:
- `sqlite` — demo database
- `clickhouse` — Limese production (host: 118.95.209.221, port 8123, db: limese)
- `postgresql` — via asyncpg
- `csv` — via DuckDB (SQL on CSV files)

### Streaming (streaming.py + streaming_graph.py)

Two parallel pipelines:
1. `graph.py` → non-streaming POST /query (blocks until complete)
2. `streaming_graph.py` → SSE GET/POST /stream (yields real node-level progress as each node completes)

The streaming version wraps every node with a progress callback that emits `{"type": "progress", "step": "understand_intent", "progress": 10, "data": {...}}` events. Frontend shows a 7-step progress bar and elapsed timer.

### Vector Memory (memory.py)

Qdrant stores embeddings of (question, SQL, results). On every query, `search_semantic_cache()` checks if a similar question was cached. **Validation rejects matches** where year/month parts differ, or where one question asks for a chart and the other doesn't. Threshold: 0.92 cosine similarity.

### Business RAG (business_rag.py)

Hardcoded knowledge: glossary of Limese platforms/terms, metric definitions, common Q&A, platform-specific insights. `build_rag_prompt()` enriches SQL-generation and insight prompts with domain context.

## Commands

```bash
# Full app (backend + frontend + Redis + Qdrant)
./start.sh

# Backend only
source venv/bin/activate
PYTHONPATH=. python -m uvicorn backend.main:app --host 0.0.0.0 --port 8001 --reload

# Frontend dev
cd frontend && npm run dev

# Frontend build → served from backend/static/
cd frontend && npm run build

# Docker services only
docker compose up -d redis qdrant

# DB context refresh
curl -X POST http://localhost:8001/api/v1/db/context/refresh
```

## Key conventions

- **PYTHONPATH must include repo root** (`PYTHONPATH=.`) or FastAPI can't find `backend.*` imports
- **DB credentials for Limese are hardcoded** in `main.py:208-214` and `db_intelligence.py:85-89` — both must stay in sync
- **SQLite demo auto-seeds** on first startup if `demo.db` is empty (sales: 2000, users: 500, tickets: 1000 rows)
- **Frontend always defaults to limese datasource** (`CopilotPage.tsx:18`) — uploaded files are a separate datasource
- **Vector memory is optional** — Qdrant/FastEmbed only loaded if `QDRANT_ENABLED=true` in `.env`
- **Pre-filter saves LLM tokens** — only catches "hi", "hello", "gm", "gn" exactly. Everything else goes to LLM for classification.
- **Pre-filter sets `skip_pipeline=True`** on state, which `compose_response` handles by returning the greeting response directly.
- **`_should_skip_sql` router** in `graph.py` checks both pre-filter output and LLM intent to decide routing.
- **Schema cache is 1 hour** in `connector.py:get_schema()`, DB Intelligence cache is 24 hours.
- **LLM cache is Canary pattern** — 15-minute window where same question returns cached result. Only checked for non-follow-up questions.
- **Conversations stored in three places**: SQLite (SQLAlchemy, primary), MinIO (optional backup), Qdrant (vector memory).

## Common pitfalls

- ClickHouse SQL fix uses `lagInFrame()`/`leadInFrame()` not `lag()`/`lead()` — if adding SQL fixes, note this.
- Revenue column is `row_subtotal` (per line), NOT `order_price` (full order). LLM is instructed but agents working on SQL may need this reminder.
- Must exclude cancelled/returned orders: `WHERE final_status NOT IN ('cancelled','Cancelled','CANCELLED','returned','Returned')`
- Date filter: `date_created >= '2025-01-01'`, do NOT use `toYear()` (timezone issues)
- Frontend calls `/stream` SSE endpoint — SSE requires `text/event-stream` media type and `X-Accel-Buffering: no` header for nginx proxy compatibility.
- ClickHouse connection is read-only for the agent, but raw `clickhouse_connect` in DB intelligence is also read-only.