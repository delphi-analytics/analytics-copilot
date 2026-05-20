# Data Visualization Copilot — Project Documentation

## Table of Contents
1. [Project Overview](#1-project-overview)
2. [System Architecture](#2-system-architecture)
3. [Technology Stack](#3-technology-stack)
4. [Frontend Architecture](#4-frontend-architecture)
5. [Backend Architecture](#5-backend-architecture)
6. [The LangGraph Agent Pipeline](#6-the-langgraph-agent-pipeline)
7. [DB Intelligence Layer](#7-db-intelligence-layer)
8. [LLM Routing & Model Management](#8-llm-routing--model-management)
9. [Data Connectors & Security](#9-data-connectors--security)
10. [Vector Memory & Semantic Cache](#10-vector-memory--semantic-cache)
11. [Business RAG Layer](#11-business-rag-layer)
12. [Streaming Architecture](#12-streaming-architecture)
13. [API Endpoints](#13-api-endpoints)
14. [Data Models & Storage](#14-data-models--storage)
15. [Configuration & Environment](#15-configuration--environment)
16. [Setup & Deployment](#16-setup--deployment)
17. [Request-Response Flow](#17-request-response-flow)
18. [Key Features](#18-key-features)

---

## 1. Project Overview

### What is the Data Visualization Copilot?

The **Data Visualization Copilot** (DVC) is an AI-powered analytics platform that allows users to ask questions about business data in plain English and receive:

- **Interactive Charts** (Apache ECharts)
- **SQL Queries** (the actual code generated)
- **Key Metrics** (summarized numbers)
- **AI-Generated Insights** (patterns, anomalies, explanations)
- **Follow-up Questions** (smart suggestions for next queries)

### Target Audience
- Business analysts exploring sales, inventory, and product data
- Non-technical users who want answers without writing SQL
- Teams working with the **Limese** beauty brand data (e-commerce across Nykaa, Myntra, Shopify, etc.)

### Primary Data Source
- **Limese ClickHouse** — Production database with ~340K orders, ₹570 Cr revenue
- **SQLite Demo** — Local testing with synthetic sales, users, and support ticket data

---

## 2. System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         BROWSER (React 19)                          │
│   Chat UI · ECharts · Table · Streaming Progress · Export · Auth UI   │
└────────────────────────────────┬────────────────────────────────────┘
                                 │  HTTP / SSE
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    FASTAPI BACKEND (:8001)                           │
│      /query · /export · /health · JWT auth · SSE streaming          │
└────────────────────────────────┬────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    SMART INTENT ROUTER                               │
│         data query · analytical question · follow-up · greeting      │
└──────────────┬──────────────────────────┬───────────────────────────┘
               │                          │
               ▼                          ▼
┌──────────────────────────┐    ┌─────────────────────────────────────┐
│   Track A: SQL Pipeline   │    │   Track B: Analytical Responder      │
│   LangGraph 7-step DAG   │    │   Data + RAG → Narrative Answer      │
│   SQL → chart → insights │    │   (for analytical questions only)    │
└──────────────┬───────────┘    └──────────────────────┬──────────────┘
               │                                      │
               └──────────────┬───────────────────────┘
                              │
                              ▼
          ┌───────────────────┴───────────────────┐
          │                                       │
          ▼                                       ▼
┌─────────────────────┐                ┌────────────────────────┐
│   LLM Router        │                │   Business RAG Layer   │
│   (LiteLLM)         │                │   Glossary + Metrics  │
│ Groq 70B → Gemini → │                │   Platform Q&A         │
│   Claude            │                │                        │
└──────────┬──────────┘                └────────────────────────┘
           │
           └─────────────────┬────────────────────┘
                             │
                             ▼
          ┌──────────────────┴──────────────────┐
          │                                     │
          ▼                                     ▼
┌─────────────────────┐            ┌────────────────────────┐
│  Limese ClickHouse  │            │   Vector Store         │
│  340K orders · ₹570 │            │   (Qdrant)             │
│  Cr (read-only)     │            │   Semantic Cache       │
└─────────────────────┘            └────────────────────────┘

                    ─── Side Services ───

┌───────────┐  ┌──────────┐  ┌────────┐  ┌──────────────────┐
│ SQLite/PG │  │  Redis   │  │  Auth  │  │     Export        │
│ conv hist │  │ sessions │  │   JWT  │  │ PDF · Excel · PNG │
└───────────┘  └──────────┘  └────────┘  └──────────────────┘
```

### Architectural Principles

1. **Separation of Concerns** — Each layer has a distinct responsibility
2. **Provider Agnosticism** — LiteLLM allows swapping LLM providers without code changes
3. **Read-Only Enforcement** — Multiple security layers prevent data modification
4. **Progressive Disclosure** — Easy questions get fast responses; complex ones go through full pipeline
5. **Caching at Every Level** — Schema, DB context, LLM responses, semantic cache

---

## 3. Technology Stack

| Layer | Technology | Version | Purpose |
|---|---|---|---|
| **Frontend** | React | 19.x | SPA framework |
| **Language** | TypeScript | 5.x | Type-safe frontend |
| **Build Tool** | Vite | 6.x | Fast dev server & build |
| **UI State** | Zustand | 4.x | Lightweight state management |
| **Charts** | Apache ECharts | 5.x | Interactive visualizations |
| **Styling** | TailwindCSS | 3.x | Utility-first CSS |
| **API** | FastAPI | 0.115.x | REST + SSE endpoints |
| **Server** | Uvicorn | 0.32.x | ASGI server |
| **DB ORM** | SQLAlchemy | 2.0.x | Async database operations |
| **Agent** | LangGraph | 0.2.x | StateGraph DAG orchestration |
| **LLM** | LiteLLM | 1.x | Provider-agnostic LLM calls |
| **Vector DB** | Qdrant | 1.x | Semantic query caching |
| **Embeddings** | FastEmbed (BAAI/bge-small) | 1.x | Text embeddings |
| **Logging** | structlog | 24.x | Structured JSON logs |
| **Auth** | python-jose | 3.x | JWT token handling |
| **ClickHouse** | clickhouse-connect | 4.x | ClickHouse client |
| **PostgreSQL** | asyncpg | 0.30.x | Async PostgreSQL driver |
| **Dataframes** | pandas + DuckDB | 2.x / 1.x | CSV/Excel SQL processing |

---

## 4. Frontend Architecture

### File Structure
```
frontend/src/
├── App.tsx                      # Root component (routes to CopilotPage)
├── pages/
│   └── CopilotPage.tsx          # Main chat interface, SSE handling, timer
├── store/
│   └── chat.ts                  # Zustand store — sessions, messages, loading
├── api/
│   └── client.ts                # Axios client — REST + SSE endpoints
├── components/
│   └── Chat/
│       ├── ChatMessage.tsx      # Renders user/assistant messages + chart
│       ├── ChatInput.tsx        # Text input with send button
│       └── charts/              # ECharts wrapper components
├── hooks/                       # Custom React hooks
└── lib/                         # Utility functions
```

### Key Components

#### CopilotPage.tsx
The main page component that orchestrates the chat interface:
- **Header** — App title, datasource indicator, session management buttons
- **Message List** — Renders all chat messages (user + assistant)
- **Welcome Screen** — Shows sample questions when no history exists
- **Chat Input** — Text input at bottom
- **Delete Modals** — Confirmation for deleting sessions/messages

**State Management (Zustand):**
```typescript
interface ChatState {
  sessions: ChatSession[]         // All chat sessions
  activeSessionId: string | null  // Current session
  isLoading: boolean              // API call in progress
  datasourceId: string             // "limese" or uploaded file ID
  
  // Actions
  addUserMessage(text: string)
  addAssistantMessage(response: any, sessionId?: string)
  setLoading(loading: boolean)
  startNewSession()
  loadSession(sessionId: string)
  deleteSession(sessionId: string)
}
```

#### ChatMessage.tsx
Renders a single message with:
- **User messages** — Right-aligned, blue background
- **Assistant messages** — Left-aligned, with:
  - Natural language text
  - Interactive chart (if `chart` data present)
  - SQL query (collapsible)
  - Key metrics (highlighted numbers)
  - AI insights (bullet points)
  - Follow-up suggestions (clickable chips)

#### SSE Streaming
The frontend connects to `/api/v1/copilot/stream` via `EventSource` (or POST with `fetch` for longer questions). It receives:
- `{"type": "progress", "step": "generate_sql", "progress": 45, "data": {...}}`
- `{"type": "complete", "result": {...}}`
- `{"type": "error", "error": "..."}`

**Progress Bar:** 7 pips, one per pipeline step, fills as seconds elapse.

**Thinking Indicator:** Shows current stage label + elapsed timer.

---

## 5. Backend Architecture

### File Structure
```
backend/
├── main.py                      # FastAPI app, startup, all /api routes
├── config.py                    # Pydantic settings from .env
├── database.py                  # SQLAlchemy async setup
├── agent/                       # THE CORE — LangGraph pipeline
│   ├── graph.py                 # Non-streaming pipeline (main path)
│   ├── streaming_graph.py       # SSE-capable pipeline with progress
│   ├── state.py                 # AnalyticsState TypedDict
│   ├── llm.py                  # LiteLLM wrapper + multi-model fallback
│   ├── memory.py               # Qdrant vector memory
│   ├── pre_filter.py           # Rule-based greeting skip
│   └── nodes/                  # 7 pure async node functions
├── data/
│   ├── connector.py            # Universal connector (all DB types)
│   └── clickhouse_connector.py # Raw ClickHouse client
├── services/
│   ├── db_intelligence.py      # Deep schema scan + caching
│   ├── business_rag.py         # Glossary, metrics, Q&A
│   ├── llm_cache.py            # 15-min Canary pattern cache
│   ├── minio_conversation.py   # MinIO conversation store
│   └── universal_db_scanner.py # Multi-DB schema scanner
├── routers/
│   ├── copilot.py              # POST /query endpoint
│   ├── streaming.py            # GET/POST /stream SSE endpoint
│   ├── dashboards.py           # Dashboard CRUD
│   └── canary_compat.py        # Legacy compatibility
├── models/                     # SQLAlchemy ORM models
│   ├── conversation.py         # Conversation table
│   ├── message.py              # Message table
│   ├── user.py                 # User table
│   └── ...
├── integrations/               # Third-party integrations
└── visualization/              # Chart helpers
```

---

## 6. The LangGraph Agent Pipeline

### Overview

The heart of the system is a **LangGraph StateGraph** — a directed acyclic graph (DAG) where each node is a pure async function that reads from and writes to a shared `AnalyticsState` object.

```
understand_intent → [discover_schema] → [generate_sql] → [execute_sql]
                                                            ↓
                                               [analyze_insights]
                                                            ↓
                                               [generate_viz_config]
                                                            ↓
                                               [compose_response] → END
```

### AnalyticsState (the shared state object)

```python
class AnalyticsState(TypedDict, total=False):
    # INPUT
    session_id: str
    conversation_id: str
    user_question: str
    datasource_id: str
    conversation_history: list[dict]  # [{role, content}]
    user_id: str

    # NODE 1 OUTPUT: Intent
    intent: dict  # {type, chart_type_hint, entities, confidence, rephrased_question}

    # NODE 2 OUTPUT: Schema
    schema_context: dict  # {relevant_tables, columns, joins}

    # NODE 3 OUTPUT: SQL
    sql_query: str
    sql_validated: bool

    # NODE 4 OUTPUT: Results
    query_results: dict  # {columns, rows, row_count, execution_time_ms}

    # NODE 5 OUTPUT: Analysis
    insights: list[str]
    key_metrics: dict
    anomalies: list[str]

    # NODE 6 OUTPUT: Visualization
    viz_config: dict  # Apache ECharts JSON
    viz_type: str  # bar | line | pie | scatter | heatmap | gauge | table

    # NODE 7 OUTPUT: Response
    response_text: str
    follow_up_questions: list[str]
    final_response: dict  # Complete response to frontend

    # ROUTING
    skip_pipeline: bool  # Pre-filter said skip
    error: str | None

    # METADATA
    model_used: str
    total_latency_ms: int
    step_errors: list[str]
```

### The 7 Nodes (Pipeline Steps)

#### Node 1: `understand_intent` (intent.py)
**Purpose:** Classify what the user wants.

**Process:**
1. First checks `pre_filter.py` — if question is "hi", "hello", "gm", "gn" → skip LLM
2. If not a greeting, calls LLM (fast 8B model) with conversation history
3. Returns structured intent with:
   - `type` — `chart_request | data_query | follow_up | analytical_question | insight_request | comparison | trend_analysis | export_request | greeting | conversational`
   - `chart_type_hint` — `bar | line | pie | scatter | heatmap | gauge | table | null`
   - `entities` — list of mentioned data entities
   - `time_range` — date range hint
   - `aggregation` — sum/count/avg/max/min
   - `is_follow_up` — boolean
   - `rephrased_question` — clearer standalone version

**Speed target:** <500ms

#### Node 2: `discover_schema` (schema.py)
**Purpose:** Find which tables/columns are relevant to the question.

**Process:**
1. Loads DB Intelligence context (cached schema scan)
2. Uses intent entities to filter relevant tables
3. Builds schema context for the SQL generation node
4. Includes:
   - Table names and descriptions
   - Column names with types and annotations
   - Sample values for categorical columns
   - Join patterns between tables

**Key insight:** Uses the **DB Intelligence layer** (not raw introspection) — it already knows which columns to use for revenue, units, dates, etc.

#### Node 3: `generate_sql` (sql_gen.py)
**Purpose:** Generate the SQL query to answer the user's question.

**Process:**
1. Builds a prompt with:
   - DB Intelligence schema context (compact version)
   - Business RAG context (glossary, metrics)
   - Conversation history (for follow-ups)
   - The user's question (rephrased version)
   - Critical rules (column names, mandatory filters, ClickHouse functions)
2. Calls LLM (smart 70B model)
3. Parses JSON response to extract SQL
4. Stores SQL in state for execution

**Critical rules passed to LLM:**
- Revenue column: `row_subtotal` (NOT `order_price`)
- Units column: `quantity_ordered` (NOT `shipped_qty`)
- Date filter: `date_created >= '2025-01-01'`
- Mandatory exclusion: `final_status NOT IN ('cancelled','Returned')`
- Use `formatDateTime(date_created, '%Y-%m')` for month grouping
- Use `lagInFrame()`/`leadInFrame()` for window functions
- Always add `LIMIT` (max 10000 for detail, 50 for aggregations)

#### Node 4: `execute_sql` (executor.py)
**Purpose:** Run the SQL against the datasource.

**Process:**
1. Security check — verify SQL is read-only (SELECT/WITH only)
2. Execute via universal connector (SQLite, ClickHouse, PostgreSQL, CSV)
3. If ClickHouse error is fixable (syntax error, unknown identifier) → one auto-fix attempt via LLM
4. Return raw results (columns + rows)

**Self-healing:** If ClickHouse returns an error like "unknown_identifier", the node calls the LLM with the error message and asks for a fix. This handles cases where the LLM-generated SQL has a typo in column names.

**Timeout:** 30 seconds (configurable)

#### Node 5: `analyze_insights` (analyst.py)
**Purpose:** Find patterns, anomalies, and key metrics in the results.

**Process:**
1. Calls LLM (smart 70B model) with:
   - Query results (first 50 rows)
   - The original question
   - DB Intelligence context
   - Business RAG context
2. Returns:
   - `insights` — list of natural language observations
   - `key_metrics` — dict of important numbers (e.g., {"total_revenue": "₹45.2 Cr", "order_count": 12450})
   - `anomalies` — surprising patterns worth highlighting

**Example output:**
```
insights: [
  "Nykaa Beauty contributes 62% of total revenue",
  "Skincare category grew 28% MoM, outpacing Makeup (12%)"
]
key_metrics: {
  "total_revenue": "₹563 Cr",
  "order_count": "340K",
  "avg_order_value": "₹16,559"
}
anomalies: [
  "Shopify D2C revenue dropped 15% in March despite consistent trend"
]
```

#### Node 6: `generate_viz_config` (viz_config.py)
**Purpose:** Generate the Apache ECharts configuration JSON.

**Process:**
1. Based on `intent.chart_type_hint` and data shape, selects best chart type:
   - Time series data → line chart
   - Categorical comparisons → bar chart
   - Proportions of a whole → pie chart
   - Two numeric variables → scatter plot
   - Multi-dimensional data → heatmap
   - Single KPI → gauge
   - Tabular data → table
2. Builds ECharts option object with:
   - Data series (from query results)
   - Axis labels, titles, legends
   - Color scheme matching app theme
   - Tooltip configuration
   - Responsive sizing

**Output:** Full ECharts JSON config object that the frontend renders with `echarts-for-react`.

#### Node 7: `compose_response` (responder.py)
**Purpose:** Assemble the final response for the frontend.

**Process:**
1. Takes all outputs from previous nodes
2. Generates natural language answer explaining the results
3. Adds follow-up question suggestions based on the data
4. Returns the `final_response` dict:
   ```python
   {
     "text": "Here's the revenue breakdown by platform...",
     "chart": { /* ECharts JSON */ },
     "insights": [...],
     "key_metrics": {...},
     "follow_up_questions": [
       "Compare this month's performance with last month",
       "Which SKUs are driving Nykaa's growth?"
     ],
     "sql": "SELECT sales_platform, SUM(row_subtotal)...",
     "row_count": 5,
     "viz_type": "bar"
   }
   ```

### Conditional Routing (`_should_skip_sql`)

After Node 1 (intent), the router decides where to go:

| Intent Type | Route |
|---|---|
| `greeting`, `off_topic` | `skip_to_respond` → Node 7 |
| `insight_followup` ("why is X dropping?") | `insight_followup` → special node → Node 7 |
| `analytical_question` ("why is X? explain Y") | `generate_sql` (gets data) → responds narratively |
| Everything else | `generate_sql` → normal 7-step path |

---

## 7. DB Intelligence Layer

### Purpose

The DB Intelligence layer solves a fundamental problem: **how does the LLM know what tables and columns exist, what they mean, and how to write correct SQL?**

Instead of dumping raw `DESCRIBE TABLE` output (which is verbose and confusing), it:
1. **Deep-scans** the ClickHouse database on startup
2. **Extracts** business-meaningful context (exact values, ranges, relationships)
3. **Annotates** columns with human-readable instructions
4. **Caches** the result to disk for fast loading
5. **Refreshes** automatically every 24 hours

### What It Extracts Per Table

For each table in `PRIORITY_TABLES`, it captures:
- **Row count** — how many rows
- **Column types** — data type of each column
- **Unique counts** — how many distinct values
- **Exact categorical values** — if ≤200 unique, stores all values (e.g., platform names)
- **Date ranges** — min/max dates for date columns
- **Numerical ranges** — min/max/avg for numeric columns
- **Constant values** — columns that always have the same value (can be skipped)
- **Business facts** — aggregated stats (total revenue, order count, etc.)

### Column Annotations (Hard-Coded)

These tell the LLM the "correct" way to use each column:

```python
COLUMN_ANNOTATIONS = {
    "combined_sales_final": {
        "sales_platform": "DIMENSION — use this to GROUP BY platform.",
        "client_name": "CONSTANT 'Limese' for all rows — NEVER group by this.",
        "row_subtotal": "REVENUE per line item — USE THIS. Do NOT use order_price.",
        "quantity_ordered": "UNITS per line — USE THIS. Do NOT use shipped_qty.",
        "date_created": "Primary date column. Filter: date_created >= '2025-01-01'.",
        "final_status": "Order outcome. ALWAYS exclude: NOT IN ('cancelled','Returned').",
        "internal_sku": "Join key → product_master.internal_sku for product names.",
    },
    "product_master": {
        "category_l1": "Top-level category. Values: Skincare, Makeup, Haircare.",
        "cogs": "Cost of Goods Sold — use for margin: mrp - cogs.",
    },
    "inventory_sales_overview_new": {
        "inventory": "Units on hand RIGHT NOW.",
        "burn_period": "Fixed 90-day config — do NOT use for calculations.",
    }
}
```

### Priority Tables Scanned

```python
PRIORITY_TABLES = [
    "combined_sales_final",      # Main sales (~340K rows)
    "product_master",            # Product catalog
    "product_catlog",            # Product listing
    "inventory_sales_overview_new",  # Current inventory
    "platform_sku_mapping",       # SKU to platform mapping
    "shopify_orders",             # Shopify orders
    "unicomm_sales_final",        # B2B sales
    "zoho_sales_final",           # CRM sales
    "lead_time",                  # Lead time data
]
```

### Startup Behavior

1. **Daemon thread** starts on app startup
2. **Initial scan** after 5-second delay (lets server start)
3. **Scans take 30-90 seconds** (9 tables deep-scanned)
4. **Cached to** `backend/data/db_intelligence.json`
5. **Periodic refresh** every 24 hours (background thread)

### The `build_sql_context_prompt` Function

This is the key function that converts the DB Intelligence context into a compact LLM prompt. It:
- Only includes **relevant tables** (not all 9)
- Only includes **useful columns** (annotated or categorical first)
- Caps categorical values at **13** (for token efficiency)
- Limits columns per table to **15**
- Always includes **global rules** (mandatory filters, ClickHouse functions)

Example output:
```
=== CRITICAL RULES ===
• REVENUE COLUMN: row_subtotal in combined_sales_final (NOT order_price).
• UNITS COLUMN: quantity_ordered in combined_sales_final (NOT shipped_qty).
• DATE FILTER: date_created >= '2025-01-01'
• MANDATORY FILTER: WHERE final_status NOT IN ('cancelled','Returned').
• LIMIT: Always add LIMIT (max 10000 for detail, 50 for aggregations).

=== DATABASE SCHEMA ===

TABLE: combined_sales_final (340,000 rows)
  Facts: {"total_revenue_crore": 563.0, "total_orders": 340000}

  • `sales_platform` (String) — DIMENSION — use this to GROUP BY platform.
    VALUES: ['Nykaa Beauty', 'Myntra_PPMP', 'Shopify', 'Unicomm', 'Zoho']
  • `row_subtotal` (Float64)
    range: 49 to 2,45,000 (avg: 16,559)
    ↳ REVENUE per line item — USE THIS. Do NOT use order_price.
  • `quantity_ordered` (Int32)
    range: 1 to 500 (avg: 4)
    ↳ UNITS per line — USE THIS. Do NOT use shipped_qty.
  • `date_created` (DateTime)
    range: 2024-01-01 to 2026-01-15
    ↳ Primary date column. Filter: date_created >= '2025-01-01'.
  • `final_status` (String)
    VALUES: ['delivered', 'shipped', 'cancelled', 'returned', ...]
    ↳ Order outcome. ALWAYS exclude: NOT IN ('cancelled','Returned').
```

---

## 8. LLM Routing & Model Management

### LiteLLM Wrapper

The `llm.py` file wraps **LiteLLM** — a library that provides a unified interface to 100+ LLM providers. This means you can switch from Groq to Gemini to Claude without changing any code.

### Model Tiers

| Tier | Model | Use Case |
|---|---|---|
| **Fast** | `groq/llama-3.1-8b-instant` | Intent classification, routing decisions (<500ms) |
| **Smart** | `groq/llama-3.3-70b-versatile` | SQL generation, insight analysis (higher quality) |
| **Premium** | `anthropic/claude-sonnet-4-6` | Complex analysis (optional, costs more) |

### Multi-Model Fallback Chain

For each task, the system tries models in order and falls back on error:

**SQL Generation:**
```
groq/llama-3.3-70b-versatile
    ↓ (rate limit or error)
groq/llama-3.1-8b-instant
    ↓ (rate limit or error)
gemini/gemini-1.5-flash
    ↓ (rate limit or error)
gemini/gemini-1.5-pro
    ↓ (rate limit or error)
deepseek/deepseek-coder
    ↓ (rate limit or error)
mistral/mistral-large-latest
    ↓ (total failure)
❌ RuntimeError: All LLM models failed
```

**Routing (intent classification):**
```
groq/llama-3.1-8b-instant
    ↓ (rate limit)
gemini/gemini-1.5-flash
    ↓ (total failure)
❌ Falls back to default intent
```

### Rate Limit Handling

When a rate limit error occurs:
1. **Retry once** on the same model (0.5 second backoff)
2. **If still failing**, move to the next model in the chain
3. **For SQL tasks**, total failure raises an exception (pipeline can't continue)
4. **For routing/analysis**, total failure returns a stub response (pipeline continues)

### Token Management

- **Intent classification:** max 350 tokens output
- **SQL generation:** max 700 tokens output
- **Insight analysis:** max 2000 tokens output
- **All models:** temperature 0.0 (deterministic for SQL)

---

## 9. Data Connectors & Security

### Universal Connector (`connector.py`)

One entry point — `execute_query(datasource_id, sql)` — works with multiple database types:

#### Supported Datasources

| Type | Driver | Use Case |
|---|---|---|
| `sqlite` | sqlite3 | Local demo, testing |
| `clickhouse` | clickhouse-connect | Limese production |
| `postgresql` | asyncpg | External PostgreSQL |
| `csv` | DuckDB | Uploaded CSV/Excel files |

### Two-Layer Read-Only Enforcement

**Layer 1 (router-level):** The copilot router checks that SQL starts with `SELECT` or `WITH` before calling the connector.

**Layer 2 (connector-level):** Even if Layer 1 is bypassed, the connector re-checks:
1. SQL must start with `SELECT` or `WITH`
2. Scans for dangerous keywords: `INSERT`, `UPDATE`, `DELETE`, `DROP`, `TRUNCATE`, `ALTER`, `CREATE`, `GRANT`, `REVOKE`, `COMMIT`, `ROLLBACK`, `INTO OUTFILE`, `LOAD DATA`
3. Rejects multi-statement queries (semicolons followed by dangerous ops)

If either layer detects modification attempt:
```python
raise PermissionError(
    "READ-ONLY ACCESS: Data modification is not allowed. "
    "Only SELECT queries are permitted. This action has been logged."
)
```

### Schema Introspection

Each datasource type has its own introspection function (`_sqlite_schema`, `_clickhouse_schema`, etc.) that returns:
- Table names
- Column names, types, nullability
- Primary keys
- Sample data (first 3 rows)
- Row counts

Schema is cached for **1 hour** per datasource to avoid repeated introspection.

---

## 10. Vector Memory & Semantic Cache

### Purpose

Instead of re-computing the same query within a short time window, the system checks if a semantically similar question was recently asked. If so, it reuses the cached SQL.

### How It Works

1. **Qdrant** stores vector embeddings of (question, SQL, results)
2. **FastEmbed** (`BAAI/bge-small-en-v1.5`) generates 384-dimensional embeddings
3. **On each query**, `search_semantic_cache(question)` finds similar questions using cosine similarity
4. **Threshold:** 0.92 similarity — must be very close to use cache

### Smart Validation (Not Just Similarity)

The cache lookup isn't just "is the question similar?" — it validates:
- **Year match** — 2025 question won't match 2024 cached result
- **Month match** — March question won't match February
- **Chart intent match** — "show me sales" won't match "show me sales as a pie chart" (different viz type)

```python
def _validate_match(q1: str, q2: str) -> bool:
    # Check year parts match
    q1_years = set(re.findall(r'\b(20[12]\d)\b', q1))
    q2_years = set(re.findall(r'\b(20[12]\d)\b', q2))
    if q1_years != q2_years:
        return False

    # Check month parts match
    q1_months = extract_months(q1)
    q2_months = extract_months(q2)
    if q1_months != q2_months:
        return False

    # Check chart intent match
    q1_is_trend = contains_trend_words(q1)
    q2_is_trend = contains_trend_words(q2)
    if q1_is_trend != q2_is_trend:
        return False

    return True
```

### Cache Storage

Each cached point stores:
```python
{
    "question": "Show revenue by platform for Nykaa in March 2025",
    "sql": "SELECT sales_platform, SUM(row_subtotal) ...",
    "user_id": "user-123",
    "results": { ... },
    "timestamp": "2026-01-15T..."
}
```

### Optional Service

Vector memory is **disabled by default**. It only activates if:
- `QDRANT_ENABLED=true` in `.env`
- Qdrant service is running (`docker compose up -d qdrant`)

---

## 11. Business RAG Layer

### Purpose

The LLM doesn't just need schema information — it needs **business context**. What does "Nykaa Beauty" mean? How is revenue calculated? What platforms does Limese sell on?

### What It Provides

#### Business Glossary
```python
BUSINESS_GLOSSARY = {
    "Nykaa Beauty": "Leading Indian beauty e-commerce platform",
    "Myntra_PPMP": "Myntra fashion marketplace platform",
    "Shopify": "E-commerce platform for D2C sales",
    "Unicomm": "B2B distribution channel",
    "GMV": "Gross Merchandise Value - Total value of merchandise sold",
    "D2C": "Direct-to-Consumer - Selling directly to customers",
    "MoM": "Month-over-Month growth comparison",
    "PPMP": "Pay Per Marketplace Platform - Commission-based selling model",
}
```

#### Metric Definitions
```python
METRIC_DEFINITIONS = {
    "revenue": "row_subtotal from orders where final_status is NOT cancelled/returned",
    "aov": "Average Order Value = Total Revenue / Number of Orders",
    "inventory value": "Current stock quantity * MRP",
    "return rate": "Percentage of orders marked as 'returned'",
}
```

#### Platform-Specific Insights
```python
PLATFORM_INSIGHTS = {
    "Nykaa": "Beauty marketplace, high volume, competitive commission",
    "Myntra": "Fashion marketplace, seasonal trends important",
    "Shopify": "D2C channel, higher margins, direct customer relationship",
    "Unicomm": "B2B distribution, bulk orders, different pricing model",
}
```

#### Common Q&A Pairs
```python
COMMON_QA = [
    {
        "q": "What platforms does Limese sell on?",
        "a": "Nykaa Beauty, Myntra, Shopify (D2C), and B2B partners like Unicomm."
    },
    {
        "q": "How is revenue calculated?",
        "a": "Revenue = SUM(row_subtotal) excluding cancelled/returned orders."
    }
]
```

### How It's Used

For each query, `get_business_context(query)` keyword-matches the question against the glossary, metrics, platforms, and Q&A. Relevant matches are assembled into a prompt section called "BUSINESS CONTEXT FOR THIS QUERY".

This context is injected into:
1. **SQL generation prompt** — so the LLM knows what platform names mean
2. **Insight analysis prompt** — so the LLM can explain results in business terms

---

## 12. Streaming Architecture

### Two Parallel Pipelines

The system runs **two complete agent pipelines**:

1. **Non-streaming (`graph.py`)**
   - Used by `POST /query`
   - Blocks until complete, returns final response
   - Simpler, used for most requests

2. **Streaming (`streaming_graph.py`)**
   - Used by `GET /stream` and `POST /stream`
   - Yields progress events as each node completes
   - Real-time updates to frontend

### Streaming Progress Events

As each node completes, the streaming graph emits:

```json
{
  "type": "progress",
  "step": "execute_sql",
  "progress": 60,
  "message": "Running query on database...",
  "data": {
    "status": "complete",
    "row_count": 5,
    "columns": ["sales_platform", "revenue"]
  }
}
```

### Frontend Display

The CopilotPage shows a **7-step progress bar** that fills as each stage completes. The bar has one pip per stage:

```javascript
const stages = [
  { at: 0, label: 'Understanding your question...' },     // Node 1
  { at: 3, label: 'Discovering schema & tables...' },    // Node 2
  { at: 6, label: 'Generating SQL query...' },           // Node 3
  { at: 10, label: 'Executing on ClickHouse...' },      // Node 4
  { at: 13, label: 'Analysing results...' },            // Node 5
  { at: 16, label: 'Building chart & insights...' },    // Node 6
  { at: 19, label: 'Composing response...' },           // Node 7
]
```

The elapsed timer counts up in seconds, and the progress bar fills based on which stage has been reached.

---

## 13. API Endpoints

### Core Endpoints

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/v1/copilot/query` | POST | Non-streaming query (main path) |
| `/api/v1/copilot/stream` | GET | SSE streaming with progress |
| `/api/v1/copilot/stream` | POST | SSE streaming (longer questions) |
| `/api/v1/copilot/upload` | POST | Upload CSV/Excel for analysis |
| `/api/v1/copilot/datasource` | POST | Register new datasource |
| `/api/v1/copilot/datasource` | GET | List datasources |
| `/api/v1/dashboards` | GET/POST | Dashboard CRUD |

### DB Intelligence Endpoints

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/v1/db/context` | GET | Get DB intelligence summary |
| `/api/v1/db/context/refresh` | POST | Trigger fresh schema scan |
| `/api/v1/db/scan` | POST | Scan any database, generate docs |
| `/api/v1/db/scan/{scan_id}` | GET | Get previous scan results |

### System Endpoints

| Endpoint | Method | Purpose |
|---|---|---|
| `/health` | GET | Health check |
| `/docs` | GET | Swagger API docs |
| `/` | GET | Serve frontend (SPA fallback) |

### Request/Response Examples

#### POST /api/v1/copilot/query

**Request:**
```json
{
  "question": "Show total revenue by platform as a pie chart",
  "datasource_id": "limese",
  "conversation_id": "optional-existing-id",
  "user_id": "user-123"
}
```

**Response:**
```json
{
  "text": "Here's the revenue breakdown by platform for Limese in 2025...",
  "chart": {
    "option": { /* ECharts JSON */ },
    "type": "pie"
  },
  "insights": [
    "Nykaa Beauty leads with 62% of total revenue",
    "Shopify D2C shows 15% MoM growth"
  ],
  "key_metrics": {
    "total_revenue": "₹563 Cr",
    "top_platform": "Nykaa Beauty"
  },
  "follow_up_questions": [
    "Compare Nykaa's performance with Myntra",
    "What SKUs drive Nykaa's revenue?"
  ],
  "sql": "SELECT sales_platform, SUM(row_subtotal) AS revenue ...",
  "row_count": 5,
  "viz_type": "pie",
  "total_latency_ms": 4523,
  "model_used": "groq/llama-3.3-70b-versatile"
}
```

---

## 14. Data Models & Storage

### SQLAlchemy Models

#### Conversation
```python
class Conversation(Base):
    __tablename__ = "conversations"
    id: Mapped[str] = Column(String, primary_key=True)
    user_id: Mapped[str] = Column(String, nullable=False, index=True)
    title: Mapped[str] = Column(String, nullable=False)
    datasource_id: Mapped[str] = Column(String)
    created_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = Column(DateTime, onupdate=datetime.utcnow)
    # Relationships
    messages: Mapped[List["Message"]] = relationship("Message", back_populates="conversation")
```

#### Message
```python
class Message(Base):
    __tablename__ = "messages"
    id: Mapped[str] = Column(String, primary_key=True)
    conversation_id: Mapped[str] = Column(String, ForeignKey("conversations.id"), index=True)
    role: Mapped[str] = Column(String)  # "user" or "assistant"
    content: Mapped[str] = Column(Text)
    sql_query: Mapped[Optional[str]] = Column(Text)
    query_results: Mapped[Optional[dict]] = Column(JSON)
    viz_config: Mapped[Optional[dict]] = Column(JSON)
    insights: Mapped[Optional[list]] = Column(JSON)
    follow_up_questions: Mapped[Optional[list]] = Column(JSON)
    model_used: Mapped[Optional[str]] = Column(String)
    latency_ms: Mapped[Optional[int]] = Column(Integer)
    error: Mapped[Optional[str]] = Column(Text)
    created_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow)
```

### Storage Layers

The system stores data in **three places**:

| Layer | Storage | Purpose |
|---|---|---|
| **Primary** | SQLite (`dvc.db`) via SQLAlchemy | Conversations & messages |
| **Backup** | MinIO (S3-compatible) | Conversation history backup |
| **Vector** | Qdrant | Semantic query cache (optional) |

---

## 15. Configuration & Environment

### Environment Variables (`.env`)

```bash
# LLM Providers
GROQ_API_KEY=              # Required for Groq models
ANTHROPIC_API_KEY=         # Optional for Claude
GEMINI_API_KEY=            # Optional for Gemini
DEEPSEEK_API_KEY=          # Optional for DeepSeek
MISTRAL_API_KEY=           # Optional for Mistral

# Model Configuration
LLM_FAST_MODEL=groq/llama-3.1-8b-instant
LLM_SMART_MODEL=groq/llama-3.3-70b-versatile
LLM_PREMIUM_MODEL=anthropic/claude-sonnet-4-6

# Database
DATABASE_URL=sqlite:///./dvc.db

# Vector Memory (optional)
QDRANT_ENABLED=false
QDRANT_URL=http://localhost:6333
QDRANT_COLLECTION=dvc_cache

# Redis (optional)
REDIS_URL=redis://localhost:6380/0

# MinIO (optional)
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET=conversations

# Query Settings
MAX_ROWS_RETURNED=10000
QUERY_TIMEOUT_SECONDS=30

# App
APP_NAME=Data Visualization Copilot
LOG_LEVEL=INFO
```

---

## 16. Setup & Deployment

### Quick Start

```bash
# 1. Clone the repository
git clone <repo-url>
cd analytics_copilot

# 2. Start everything (creates .env, venv, deps, Docker, frontend build)
./start.sh

# 3. Open in browser
# http://localhost:8001
```

### What `start.sh` Does (Step by Step)

1. **Creates `.env`** from `.env.example` if missing
2. **Creates virtual environment** at `venv/`
3. **Installs dependencies** (only if `requirements.txt` changed)
4. **Starts Docker services** — Redis + Qdrant (if Docker available)
5. **Waits for Redis** to be ready (up to 15 seconds)
6. **Waits for Qdrant** to be ready (up to 15 seconds)
7. **Builds frontend** (if not already built) → `backend/static/`
8. **Pre-warms FastEmbed** embedding model
9. **Starts uvicorn** on port 8001 with hot reload

### Individual Component Commands

```bash
# Backend only (after venv setup)
source venv/bin/activate
PYTHONPATH=. python -m uvicorn backend.main:app --host 0.0.0.0 --port 8001 --reload

# Frontend only (dev mode)
cd frontend && npm run dev

# Frontend production build
cd frontend && npm run build

# Docker services only
docker compose up -d redis qdrant

# Trigger DB context refresh
curl -X POST http://localhost:8001/api/v1/db/context/refresh
```

---

## 17. Request-Response Flow

A complete end-to-end flow for the question **"Show revenue by platform as a pie chart"**:

```
1. USER submits question
   ↓
2. FastAPI receives POST /api/v1/copilot/query
   ↓
3. copilot.py router calls run_analytics_agent()
   ↓
4. graph.py starts LangGraph pipeline with AnalyticsState
   ↓
5. pre_filter.py checks: "Show revenue..." → not a greeting → continue
   ↓
6. NODE 1: understand_intent()
   - Calls LLM (groq/8b) with conversation history + question
   - Returns: type="chart_request", chart_type_hint="pie", entities=["revenue", "platform"]
   ↓
7. Router checks: type is "chart_request" → normal pipeline
   ↓
8. NODE 2: discover_schema()
   - Loads DB Intelligence context (cached JSON)
   - Filters relevant tables: combined_sales_final, product_master
   - Builds compact schema prompt for SQL generation
   ↓
9. NODE 3: generate_sql()
   - Calls LLM (groq/70b) with: question + schema context + RAG context + rules
   - LLM generates: SELECT sales_platform, SUM(row_subtotal) FROM combined_sales_final
                   WHERE final_status NOT IN ('cancelled','Returned')
                   GROUP BY sales_platform ORDER BY revenue DESC
   ↓
10. NODE 4: execute_sql()
    - Security check: SQL is read-only ✓
    - Execute against ClickHouse (limese datasource)
    - Returns: columns=["sales_platform", "revenue"], rows=[{...}, {...}]
    ↓
11. NODE 5: analyze_insights()
    - Calls LLM (groq/70b) with: query results + question + context
    - Returns: insights=["Nykaa leads with 62%"], key_metrics={...}, anomalies=[...]
    ↓
12. NODE 6: generate_viz_config()
    - chart_type_hint="pie" → generates pie chart ECharts config
    - Maps data to series: [{name: "Nykaa", value: 348}, {...}]
    ↓
13. NODE 7: compose_response()
    - Assembles natural language explanation
    - Adds follow-up questions
    - Returns final_response dict
   ↓
14. graph.py returns response to copilot.py router
   ↓
15. FastAPI returns JSON to frontend
   ↓
16. Frontend renders: text + pie chart + insights + follow-ups
```

**Total latency:** ~3-5 seconds (depending on LLM response times)

---

## 18. Key Features

### For Users

1. **Natural language queries** — No SQL knowledge required
2. **Interactive charts** — Hover, zoom, export as PNG
3. **Follow-up questions** — "Compare with last month" context-aware
4. **SQL transparency** — See the generated SQL, learn as you go
5. **Key metrics highlighted** — Most important numbers at a glance
6. **AI insights** — Patterns and anomalies explained in plain English
7. **Multi-platform data** — Nykaa, Myntra, Shopify, Unicomm, Zoho unified

### For Developers

1. **Modular pipeline** — Each node is a pure async function, easy to test
2. **Provider agnostic** — Swap LLM providers without code changes
3. **Fallback chains** — System continues working even if one LLM fails
4. **Self-healing SQL** — Auto-fixes common ClickHouse syntax errors
5. **Semantic cache** — Same question returns instantly within 15 minutes
6. **DB Intelligence** — LLM always knows the schema without hallucinating
7. **Business RAG** — Domain context prevents incorrect interpretations

### Security Features

1. **Two-layer read-only enforcement** — Connector refuses all modifications
2. **Multi-statement prevention** — Semicolons with dangerous ops rejected
3. **Query timeout** — Long-running queries killed after 30 seconds
4. **Rate limiting** — Automatic fallback when LLM rate limits hit

### Performance Features

1. **Schema caching** — 1 hour cache, no repeated introspection
2. **DB Intelligence cache** — 24 hour cache, 30-90 second scan on startup
3. **Vector semantic cache** — O(1) lookup for repeated questions
4. **Canary LLM cache** — 15-minute window for identical questions
5. **MinIO conversation backup** — Persistent storage beyond SQLite
6. **Background refresh** — DB Intelligence updates without downtime

---

*Last updated: May 2026*