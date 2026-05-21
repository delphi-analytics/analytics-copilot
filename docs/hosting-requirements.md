# Hosting & Infrastructure Requirements — Analytics Copilot

> **Project**: AI-powered analytics platform where users type natural-language questions and get back interactive Apache ECharts, SQL, key metrics, and follow-up suggestions.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [VM Sizing Quick Reference](#2-vm-sizing-quick-reference)
3. [Component Breakdown](#3-component-breakdown)
4. [CPU Requirements](#4-cpu-requirements)
5. [RAM Requirements](#5-ram-requirements)
6. [Storage Requirements](#6-storage-requirements)
7. [Network Requirements](#7-network-requirements)
8. [External Service Dependencies](#8-external-service-dependencies)
9. [Scaling & Multi-User Considerations](#9-scaling--multi-user-considerations)
10. [Deployment Topologies](#10-deployment-topologies)
11. [Cost Estimates](#11-cost-estimates)
12. [Environment Variables & Configuration](#12-environment-variables--configuration)

---

## 1. Architecture Overview

```
                         ┌──────────────────────────────────┐
                         │  Cloud LLM APIs (Groq, Gemini,   │
                         │  Claude, DeepSeek, Mistral, etc.) │
                         └──────────┬───────────────────────┘
                                    │ HTTP (outbound)
                         ┌──────────▼───────────────────────┐
                         │     FastAPI (Uvicorn)             │
                         │   ┌───────────────────────────┐   │
                         │   │  LangGraph Pipeline        │   │
                         │   │  (9 nodes, cache-first)    │   │
                         │   │                            │   │
                         │   │  check_qa_memory ──cache─┐ │   │
                         │   │  understand_intent        │ │   │
                         │   │  general_llm (greeting)   │ │   │
                         │   │  discover_schema          │ │   │
                         │   │  generate_sql             │ │   │
                         │   │  execute_sql              │ │   │
                         │   │  analyze_insights         │ │   │
                         │   │  generate_viz_config      │ │   │
                         │   │  compose_response ◄───────┘ │   │
                         │   └───────────────────────────┘   │
                         └──┬──────┬──────────┬────────┬────┘
                            │      │          │        │
                    ┌───────▼──┐ ┌─▼──────┐ ┌─▼──────┐ ┌▼──────────┐
                    │ Redis    │ │ Qdrant │ │ MinIO  │ │ClickHouse │
                    │ (cache)  │ │(3 vec  │ │(conv.  │ │(primary   │
                    │ optional │ │collections)│ history│ │ data)     │
                    └──────────┘ └────────┘ └────────┘ └───────────┘
                                       ┌────────────┐
                                       │ SQLite /   │
                                       │ PostgreSQL │
                                       │ (metadata) │
                                       └────────────┘
```

### Qdrant is now a core dependency

Qdrant hosts **3 separate vector collections** (was 1 in the original architecture):

| Collection | Purpose | Grows with |
|---|---|---|
| `qa_memory` | Semantic Q&A cache — checked **first** in the pipeline | Unique queries asked |
| `business_knowledge` | KPI definitions, glossary, ambiguous keywords, business rules | Business knowledge updates |
| `db_knowledge` | Indexed table schemas, column descriptions | DB schema changes |

### New cache-first pipeline flow

```
start → check_qa_memory (Qdrant qa_memory)
  │
  ├─ cache hit (≥0.92) ──→ compose_response         ← instant response, no LLM calls
  ├─ partial hit (≥0.75) ──→ understand_intent       ← reuse cached SQL, re-execute + analyze + viz
  │                              (pre-fills sql_query from cache)
  └─ cache miss ──→ understand_intent                ← full pipeline
                      │
                      ├─ greeting/conversational/off_topic ──→ general_llm (LLM generates varied response)
                      ├─ insight_followup ──→ insight_followup node ──→ compose_response
                      ├─ export_request ──→ compose_response
                      └─ data/analytical ──→ discover_schema → generate_sql
                              → execute_sql → analyze_insights → generate_viz_config
                              → compose_response (also stores result in Qdrant qa_memory + MinIO)
```

### Key behavioral changes from v1

- **Cache-first**: Qdrant `qa_memory` is checked before any LLM call. Cache hits (≥0.92 similarity) return instantly, skipping the entire LLM pipeline. Saves $0.005–0.02 per cached query.
- **Greeting/conversational handled by LLM**: No more hardcoded responses. The new `general_llm` node generates varied, context-aware responses using the 8B model. Slightly higher latency (~2s) but better UX.
- **MinIO for conversation storage**: Every query's response is saved to MinIO. Conversation history is loaded from MinIO on new requests if no history is provided via the API.
- **3 Qdrant collections instead of 1**: More RAM needed if enabling Qdrant.
- **Auth system**: JWT-based authentication with 4 user roles (admin, business_analyst, non_tech_user, team_member). Optional but adds DB writes on every request for session tracking.
- **Universal DB scanner**: Can scan any SQLAlchemy database to auto-generate documentation. Useful for onboarding new datasources but consumes CPU/memory during scans.

### LLM calls per query (updated)

| Scenario | Fast LLM (8B) calls | Smart LLM (70B) calls |
|---|---|---|
| Cache hit (≥0.92) | 0 | 0 |
| Cache partial (≥0.75) | 2–3 (intent + response) | 1–2 (analysis + viz) |
| Normal full pipeline | 2–3 (intent + response + follow-ups) | 2–3 (SQL + analysis + optional fix) |
| Greeting/conversational | 1 (general_llm) | 0 |

### Typical query latency (updated)

| Scenario | Latency | LLM Calls |
|---|---|---|
| Cache hit (≥0.92) | **0.2–1s** (Qdrant lookup only) | 0 |
| Cache partial (≥0.75) | 10–20s (re-execute SQL + analyze) | 2–4 |
| Normal (miss, no fix) | 20–40s | 4–5 |
| Normal (miss, with auto-fix) | 30–55s | 5–6 |
| Greeting/conversational | 2–3s | 1 |
| Insight follow-up ("why?") | 15–25s | 2–3 |

---

## 2. VM Sizing Quick Reference

| Tier | Users | vCPUs | RAM | Storage | Monthly Cost (approx) |
|---|---|---|---|---|---|
| **Development / Single-user** | 1–3 | 2 vCPU | 4 GB | 20 GB | $15–25 |
| **Small Team** | 5–20 | 4 vCPU | 8 GB | 50 GB | $40–80 |
| **Medium Team** | 20–100 | 8 vCPU | 16 GB | 100 GB | $150–300 |
| **Production (100+)** | 100+ | 16 vCPU | 32 GB | 200 GB | $400–800+ |

> Costs exclude external LLM API usage fees (see §9), ClickHouse hosting (see §8), and MinIO (if self-hosted).

### What limits each tier

| Bottleneck | Effect |
|---|---|
| **LLM API rate limits** | Max ~20–30 queries/minute on free Groq tier. Primary bottleneck regardless of VM size. |
| **Qdrant query throughput** | Each request makes 1–3 Qdrant searches (qa_memory check + optional knowledge lookups). At high QPS, Qdrant's HNSW search becomes CPU-bound. |
| **Python GIL + asyncio** | Single uvicorn worker handles many concurrent requests via async, but CPU-bound work (pandas, JSON processing, FastEmbed) blocks the event loop. |
| **Thread pool** | Default 5–10 threads for SQLite/DuckDB. At high concurrency, database queries queue up. |
| **Memory (RAM)** | Each concurrent request holds query results (1–20 MB). At 50 concurrent users, that's 1+ GB just for result buffers. |
| **MinIO writes** | Every query results in a MinIO write. At high volume, network I/O to MinIO adds latency. |

---

## 3. Component Breakdown

### 3.1 Backend (FastAPI + Uvicorn)

**What it does**: Web server + LangGraph pipeline orchestrator. Every user request flows through this process.

| Resource | Minimum | Recommended | Why |
|---|---|---|---|
| vCPU | 2 cores | 4+ cores | Python is single-threaded (GIL) per process. Async I/O benefits from multiple cores when running multiple workers (`--workers N`). More cores = more concurrent request handling. |
| RAM | 2 GB | 4–8 GB | Base Python runtime ~150 MB. FastEmbed embedding model loads ~200–400 MB. Each concurrent request adds ~5–20 MB for query results. Multiple workers multiply this. |

**Key memory consumers within the backend process:**

| Component | RAM | Detail |
|---|---|---|
| Python runtime + imports | 80–150 MB | FastAPI, LangGraph, LangChain, LiteLLM, SQLAlchemy, pandas, numpy, minio, jose |
| FastEmbed model (BAAI/bge-small) | 200–400 MB | Loaded into RAM on first use. ~33 MB on disk, expands in memory for inference. Used by all 3 Qdrant collections (qa_memory + business_knowledge + db_knowledge). Single shared instance. |
| DB Intelligence JSON cache | 5–50 MB | Parsed ClickHouse schema context in memory as a Python dict |
| LLM response cache (in-memory) | 5–50 MB | ~200 entries × ~250 KB average — stores (question, SQL, results) tuples |
| Query results per request | 1–20 MB | Up to 10,000 rows × 50 columns of mixed data. Held until response is composed and sent. |
| Schema cache (ClickHouse introspection) | 5–15 MB | Table definitions, column types, cardinalities cached for SQL generation |
| Business knowledge JSON | ~1 MB | Hardcoded KPI definitions, glossary, ambiguous keywords (loaded into dict) |

### 3.2 Frontend (Vite dev server / static build)

**In production** the frontend is pre-built (`npm run build`) and served as static files from the backend itself — no separate server needed.

**If running the dev server** for development:

| Resource | Minimum | Recommended |
|---|---|---|
| vCPU | 1 core | 2 cores |
| RAM | 512 MB | 1 GB |

**In production**, the frontend build output is ~1–10 MB of static HTML/JS/CSS served directly by the backend (no extra process needed).

### 3.3 Redis (Optional — LLM Response Cache)

**Purpose**: 15-minute Canary-pattern cache. If the exact same question is asked within 15 minutes, Redis returns the cached SQL+results instead of re-running the pipeline.

| Resource | Minimum | Recommended | Why |
|---|---|---|---|
| vCPU | Negligible | 0.5 core | Redis is single-threaded and extremely efficient. |
| RAM | 256 MB | 512 MB–1 GB | Stores cached responses (question → SQL → results). Each entry ~1–50 KB. 1 GB holds ~20,000–100,000 entries. |
| Storage | 100 MB | 1 GB (persistent) | AOF persistence (append-only file). Grows with write volume. |

**When you need it**: If you expect repeated questions (e.g., dashboard-style "what was revenue yesterday?" asked daily). Without Redis, every query hits the full pipeline (4–6 LLM calls + DB query).

**When you can skip it**: Low-traffic single-user or demo deployments. The 15-minute window is short enough that the cost savings are modest at low volume.

### 3.4 Qdrant (Strongly Recommended — 3 Vector Collections)

**Purpose**: Now the **primary cache layer**. Hosts 3 vector collections:

1. **`qa_memory`** — Semantic Q&A cache. Checked **first** on every query. Cache hit (≥0.92) bypasses entire LLM pipeline. Partial hit (0.75–0.92) reuses cached SQL.
2. **`business_knowledge`** — KPI definitions, glossary, ambiguous keywords, business rules. Queried during SQL generation and response composition.
3. **`db_knowledge`** — Indexed table schemas and column descriptions. Queried during schema discovery for relevant table/column selection.

| Resource | Minimum | Recommended | Why |
|---|---|---|---|
| vCPU | 1 core | 2–4 cores | Qdrant uses HNSW for approximate nearest neighbor search. 3 concurrent collections mean 3× the search operations. At 50+ QPS, 4 cores is recommended. |
| RAM | 1 GB | 2–4 GB | **3 collections instead of 1**. HNSW index per collection lives in RAM. 100K vectors × 384 dimensions × 4 bytes = ~150 MB per collection. 3 collections = ~450 MB + overhead. |
| Storage | 2 GB | 10–20 GB | Vectors + payloads stored on disk with WAL. 3 collections × growth. 100K unique queries ≈ 600–1500 MB total. |

**Why it's now strongly recommended (not optional):**

| Feature | Without Qdrant | With Qdrant |
|---|---|---|
| Cache-first semantic matching | Skip — every query runs full pipeline | ~80% of repeated/similar queries return in <1s |
| Business knowledge retrieval | Uses hardcoded JSON fallback | Vector search finds relevant KPI/glossary entries |
| DB schema context | Only uses structured cache | Can search indexed column descriptions |
| LLM cost per query (avg) | $0.005–0.02 | $0.001–0.01 (more cache hits lower avg) |
| Avg query latency | 20–40s | 5–25s (cache hits drop to <1s) |

**When you can skip it**: Low-traffic demos or development. All features degrade gracefully with non-Qdrant fallbacks.

### 3.5 ClickHouse (Primary Production Datasource — External)

**This is assumed to be hosted separately** (currently at `118.95.209.221:8123`). The analytics copilot queries it but does not host it.

The enhanced ClickHouse connector now scans **12 priority tables** (previously fewer):

| Table | Rows | Purpose |
|---|---|---|
| `combined_sales_final` | ~340,000 | Main sales — revenue, units, platform-level |
| `inventory_sales_overview_new` | ~1,100,000 | Daily inventory snapshots |
| `product_master` | ~1,383 | Product master data |
| `product_catlog` | ~5,586 | Platform SKU mappings |
| `platform_sku_mapping` | varies | Cross-platform SKU mapping |
| `shopify_orders` | varies | Shopify-specific orders |
| `unicomm_sales_final` | varies | Unicommerce sales |
| `zoho_sales_final` | varies | Zoho sales |
| `zoho_purchase_orders` | varies | Purchase orders |
| `inventory_ledger` | varies | Inventory movements |
| `product_hierarchy` | varies | Product categorization |
| `lead_time` | varies | Supply chain lead times |

| Resource | Minimum (for the analytics copilot to query it) |
|---|---|
| Network | Low-latency connection (< 10 ms). Every query result is streamed over the network. |
| Bandwidth | 10–100 Mbps. A single query may return 10,000+ rows. |

**The ClickHouse server itself** (if you self-host):

| Resource | Minimum | Recommended | Why |
|---|---|---|---|
| vCPU | 4 cores | 8–16 cores | ClickHouse is CPU-bound for aggregation queries. 340K order rows + 1.1M inventory rows. |
| RAM | 4 GB | 16–32 GB | ClickHouse uses RAM for query processing. Aggregation on 1M+ rows can consume several GB. |
| Storage | 50 GB (SSD) | 200+ GB (NVMe SSD) | Current dataset across 12+ tables. Compressed ClickHouse storage is ~5–10× smaller than raw data. |

### 3.6 MinIO (Now Required for Conversation History)

**Purpose**: Every query response is saved to MinIO as a JSON object (`users/{user_id}/conversations/{conversation_id}.json`). Conversation history is loaded from MinIO on subsequent requests.

| Resource | Minimum | Recommended | Why |
|---|---|---|---|
| vCPU | 0.5 core | 1 core | MinIO is I/O-bound, not CPU-bound. |
| RAM | 256 MB | 512 MB–1 GB | MinIO uses memory for metadata caching and write buffers. |
| Storage | 10 GB | 50–100 GB | Each query response (with chart configs, SQL, results, analysis) is 5–50 KB. 10,000 queries ≈ 50–500 MB. Over time, this grows linearly with query volume. |

**What happens if MinIO is unavailable**: The backend falls back silently — conversations are not saved but the query still completes. No crash, but users lose conversation history across sessions.

**Can MinIO be replaced?**: Yes — any S3-compatible store (AWS S3, DigitalOcean Spaces, Cloudflare R2) works. Set `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`.

### 3.7 PostgreSQL (Recommended for Production Metadata)

Replaces SQLite for app metadata. Stores:
- Conversations + messages (from SQLite → moved here in production)
- User accounts and auth data (users, roles, hashed passwords)
- Approval queue (pending schema/knowledge changes)
- Session tracking

| Resource | Minimum | Recommended |
|---|---|---|
| vCPU | 1 core | 2 cores |
| RAM | 512 MB | 2 GB |
| Storage | 10 GB (SSD) | 50 GB |

**Why**: Conversations, messages, user accounts, approvals. Not heavily queried — primarily inserts on each query + reads for conversation history. Fast to moderate growth as 50–500 MB per 10K queries.

### 3.8 SQLite (Demo Database + App Metadata — Dev Only)

**Two databases**:
- `demo.db` — Demo sales/users/support_tickets (3,500 rows, ~500 KB)
- `dvc.db` — App metadata: conversations, messages, users (grows with usage)

| Resource | Minimum | Why |
|---|---|---|
| Storage | 100 MB | `demo.db` is tiny. `dvc.db` grows with usage — each conversation + messages + chart configs adds ~1–50 KB. 10,000 conversations ≈ 50–500 MB. |

**No separate process needed** — SQLite runs in-process. Reads/writes are serialized (single-writer), which becomes a bottleneck at high concurrency. For production with 50+ concurrent users, **migrate to PostgreSQL**.

### 3.9 Universal DB Scanner (On-Demand)

**Purpose**: Scans any SQLAlchemy-supported database and generates comprehensive documentation (table schemas, column stats, relationships, sample data, suggested JOINs). Used when onboarding new datasources.

| Resource | Per-scan cost | Why |
|---|---|---|
| CPU | Medium (30–120s on a 4-core VM) | Scans each table: row count, column stats, sample values, unique counts, min/max ranges |
| RAM | 50–200 MB during scan | Holds metadata for all tables + columns in memory during scan |
| Storage | 50–500 KB per scan (saved to `./data/db_scans/{scan_id}/`) | Generates `documentation.json`, `README.md`, `llm_context.txt` |

**When it runs**: Only on-demand via `POST /api/v1/db/scan` or the admin trigger endpoint. Not a persistent resource consumer.

---

## 4. CPU Requirements — Detailed

### What consumes CPU (updated)

| Operation | CPU Intensity | Why |
|---|---|---|
| **Python request routing + JSON serialization** | Low | FastAPI + Uvicorn are async and event-driven. Minimal CPU per request. |
| **LLM API calls** | Minimal (waiting on network) | The process mostly sleeps waiting for HTTP responses. CPU usage is near-zero during the 15–45 second query window. |
| **FastEmbed inference** | Medium | Runs on CPU (not GPU). Each embedding takes 50–200 ms on a single core. **Now called up to 3× per query** (qa_memory check + optionally business_knowledge + db_knowledge lookups). |
| **Qdrant HNSW search** | Low-Medium | Each vector search takes 5–50ms. 3 collections × 1–2 searches per query = 3–6 searches. At 10 QPS (queries per second), that's 30–60 searches/s. |
| **Pandas data processing** | Medium-High | Sorting, filtering, aggregating query results (especially 10K+ rows) uses pandas/numpy which are CPU-bound. |
| **General LLM node** | Low | Single 8B LLM call per greeting/conversational query. ~2s latency, minimal CPU. |
| **DB Universal Scanner** | Medium-High | Only during active scans. Analyzes each table's schema, sample data, min/max, unique counts. |
| **MinIO I/O** | Low | Writes are async network I/O. Minimal CPU. |
| **Zustand / React rendering** | Low (client-side) | ECharts rendering happens in the browser, not on the server. |
| **Multiple uvicorn workers** | Scales linearly | Each worker is a separate Python process. 4 workers = 4× the CPU usage. |

### CPU Recommendations by scenario (updated)

| Scenario | vCPUs | Workers | Rationale |
|---|---|---|---|
| Single dev user | 2 | 1 | Only one request at a time. 1 worker is sufficient. Qdrant single-collection searches are fast. |
| 5–20 concurrent users | 4 | 2–3 | Some overlap. 2–3 workers handle concurrent requests. Each worker handles ~5–10 simultaneous async requests. FastEmbed + Qdrant searches add CPU load. |
| 20–100 concurrent users | 8 | 4 | 4 workers × ~10 simultaneous async requests = 40 in-flight. Qdrant becomes more active with 3 collections. LLM still dominates wall time. |
| 100+ concurrent users | 16 | 8 | 8 workers × ~15 async requests each = 120 simultaneous. CPU-bound work from pandas aggregations + Qdrant search throughput. |

> **Note**: The cache-first architecture reduces average CPU per query because cache hits skip the entire LLM pipeline. At high traffic, cache hit rates of 20–40% are expected, significantly reducing both CPU and LLM cost.

---

## 5. RAM Requirements — Detailed

### Updated per-component breakdown

| Component | Base RAM | Per-query overhead | Notes |
|---|---|---|---|
| **Uvicorn worker** | 80–150 MB | +5–20 MB | Per-worker. 4 workers = 320–600 MB just for Python. |
| **FastEmbed model** | 200–400 MB | — | Shared across workers via copy-on-write. **Required if Qdrant is enabled** (which it now should be for 3 collections). |
| **DB Intelligence cache** | 5–50 MB | — | Loaded once per worker. |
| **Business knowledge JSON** | 1–2 MB | — | KPI definitions, glossary, ambiguous keywords. |
| **LLM cache (in-memory)** | 5–50 MB | — | Per-worker cache of recent responses. |
| **Query result buffers** | — | 1–20 MB per active query | 20 concurrent queries = 20–400 MB. |
| **Redis** | 256 MB–1 GB | — | Separate process. RAM used grows with cache size. |
| **Qdrant** | **1–4 GB** | — | Separate process. **3 HNSW indexes** (qa_memory, business_knowledge, db_knowledge) in RAM. Previously 512 MB–2 GB for 1 collection. |
| **MinIO** | 256 MB–1 GB | — | Separate process. RAM used for metadata caching. |

### RAM formulas (updated)

```
Minimal (Qdrant disabled, MinIO disabled, no Redis):
  Workers × (150 MB base + 10 MB × avg_concurrent_queries)
  = 2 × (150 + 10×10) = 2 × 250 = 500 MB → Use 2 GB VM

Recommended (Qdrant enabled, MinIO enabled, Redis enabled):
  Workers × (150 MB + 400 MB FastEmbed + 10 MB × queries)
  + Redis(1 GB) + Qdrant(3 GB) + MinIO(512 MB)
  = 2 × (150 + 400 + 100) + 1000 + 3000 + 512
  = 2 × 650 + 4512 = 1300 + 4512 = 5812 MB → Use 8 GB VM

Full production (4 workers, all services):
  4 × (150 + 400 + 200) + 1000 + 3000 + 512
  = 4 × 750 + 4512 = 3000 + 4512 = 7512 MB → Use 16 GB VM
```

### RAM by deployment type (updated)

| Deployment | Services Running | Total RAM Needed |
|---|---|---|
| All-in-one (dev, minimal) | Uvicorn (1 worker) + SQLite | 1–2 GB |
| All-in-one (dev, full) | Uvicorn (2 workers) + Redis + Qdrant + MinIO + SQLite | 4–8 GB |
| Production minimal | Uvicorn (4 workers) + PostgreSQL + Redis + MinIO | 4–8 GB |
| Production + vectors | Uvicorn (4 workers) + PostgreSQL + Redis + Qdrant + MinIO | **8–16 GB** |
| Production + ClickHouse (self-hosted) | Above + ClickHouse server | 16–32 GB |

---

## 6. Storage Requirements — Detailed

### 6.1 Persistent storage needs (updated with MinIO + Qdrant)

| Mount | Size | Contents | Growth Rate |
|---|---|---|---|
| `/app/backend/` (code) | 500 MB | Python source code, static frontend build | Never grows |
| `/app/venv/` | 300–600 MB | Python virtual environment | Stable after install |
| `/app/backend/data/` | 1–50 MB | `db_intelligence.json`, `business_knowledge.json`, demo data | Grows slowly (schema cache overwritten) |
| `/app/backend/data/db_scans/` | 1–100 MB | DB scanner output (per scan: 50–500 KB) | Grows with each new scan |
| `/app/demo.db` | ~500 KB | SQLite demo database | Never grows |
| `/app/dvc.db` (or PostgreSQL) | 1–500 MB | Conversations, messages, users, approvals | Grows with usage (~1–50 KB per query) |
| `/app/uploads/` | 1–10 GB | User-uploaded CSV files | Grows with each file upload. Set a per-user quota. |
| **Docker volumes:** | | | |
| `redis_data` (AOF) | 100 MB–1 GB | Redis persistence | Grows with cache write volume |
| `qdrant_data` | **2–20 GB** | **3 collections** of vector embeddings + WAL | Grows with unique queries (~2 KB per query per collection) |
| `postgres_data` | 1–10 GB | Production metadata | Grows with conversation count |
| **MinIO storage:** | | | |
| `minio_data` | 10–100 GB | Conversation JSON objects | Grows with every query (~5–50 KB per response) |

### 6.2 Total storage by setup (updated)

| Setup | Storage Needed | Notes |
|---|---|---|
| **Minimal (dev)** | 2–5 GB | Code + venv + Node modules + SQLite DB |
| **Production (no vectors)** | 15–30 GB | Code + venv + PostgreSQL + Redis + MinIO + uploaded files |
| **Production (full)** | 30–100 GB | Above + Qdrant (3 collections) + more headroom |
| **Production + ClickHouse (self-hosted)** | 230–300+ GB | Above + ClickHouse data (200+ GB) |

**Disk type**: **SSD is strongly recommended** for all paths. HDD will cause noticeable latency for:
- MinIO reads/writes (each query = file I/O)
- Qdrant HNSW index writes + WAL
- SQLite/PostgreSQL reads/writes
- ClickHouse queries (if self-hosted)
- Redis AOF persistence

---

## 7. Network Requirements

### Outbound (backend → external)

| Destination | Protocol | Port | Required | Bandwidth | Why |
|---|---|---|---|---|---|
| **LLM API providers** (Groq, etc.) | HTTPS | 443 | **Yes** | Low (< 1 Mbps) | Every query makes 2–6 API calls. Each call sends ~1–10 KB and receives ~1–50 KB. 100 queries/day ≈ 50 MB/day total. |
| **ClickHouse** (limese) | HTTPS/TCP | 8123/8443 | **Yes** | Low-Medium | Query results up to 10 MB per query. 100 queries/day ≈ 1 GB/day. Latency-sensitive — keep RTT < 10 ms. |
| **MinIO / S3** (if hosted externally) | HTTPS | 443 | **Required** | Low | Every query writes a JSON conversation record (~5–50 KB) and reads history. 100 queries/day ≈ 10 MB/day. |
| **Qdrant cloud** (if hosted) | gRPC/HTTP | 6333/6334 | Optional | Very low | Small vectors (~2 KB per search). 3 collections × 1–2 searches per query. |
| **Redis cloud** (if hosted) | TCP | 6379 | Optional | Very low | Small cache entries. |
| **Web search APIs** (Tavily/Serper) | HTTPS | 443 | Optional | Very low | Only used for knowledge-grounded responses. |

### Inbound (users → frontend/backend)

| Source | Protocol | Port | Bandwidth |
|---|---|---|---|
| **Browser users** | HTTPS | 443 (with reverse proxy) or 8001 | Low — mostly text + chart JSON. Static frontend assets < 5 MB total. |
| **API clients** | HTTPS | 443 or 8001 | Low — REST + SSE responses. Each response is 5–100 KB of JSON. |

### Network requirements summary

| Scenario | Outbound Bandwidth | Inbound Bandwidth | Latency Requirement |
|---|---|---|---|
| 1–10 daily users | < 1 Mbps | < 1 Mbps | Standard (> 50 ms acceptable) |
| 100–500 daily users | 5–20 Mbps | 2–10 Mbps | Low (< 20 ms to ClickHouse, < 10 ms to MinIO) |
| 1000+ daily users | 50–100 Mbps | 20–50 Mbps | Very low to ClickHouse (< 5 ms), MinIO in same datacenter |

### Critical network path: Backend ↔ MinIO

MinIO is now written to on **every query** (for conversation persistence). Latency to MinIO directly affects user-perceived response time:

| MinIO location | RTT | Effect |
|---|---|---|
| Same VM (localhost:9000) | < 1 ms | Negligible |
| Same datacenter (Docker network) | 1–3 ms | Negligible |
| Same region (S3-compatible service) | 5–20 ms | Adds 5–20 ms to response composition |
| Cross-region | 50–200 ms | Adds noticeable delay |

**Recommendation**: Run MinIO on the same VM or in the same datacenter as the backend.

---

## 8. External Service Dependencies

### 8.1 LLM API Providers (Required)

The pipeline will not function without at least one working LLM API provider.

| Provider | Default Model | Free Tier Limits | Paid Tier | Cost Estimate |
|---|---|---|---|---|
| **Groq** | `llama-3.1-8b-instant` (fast), `llama-3.3-70b-versatile` (smart) | 30 req/min (8B), 20 req/min (70B) | Pay-per-token | ~$0.10–0.50/1K queries on 8B, ~$1–5/1K queries on 70B |
| **Gemini** | `gemini-1.5-flash` (fallback), `gemini-1.5-pro` | 1,500 req/day (flash), 50 req/day (pro) | Pay-per-token | Free tier is generous — many deployments won't exceed it |
| **DeepSeek** | `deepseek-coder` (fallback) | — | Pay-per-token | ~$0.14/1M input tokens |
| **Claude (Anthropic)** | `claude-sonnet-4` (premium) | No free tier | Pay-per-token | ~$3/1M input tokens, ~$15/1M output tokens |
| **Mistral** | `mistral-large-latest` (fallback) | — | Pay-per-token | ~$2/1M input tokens |

**Typical cost per query:**

| Scenario | 8B Calls | 70B Calls | Est. Cost (Groq Free) | Est. Cost (Groq Paid) |
|---|---|---|---|---|
| Cache hit (≥0.92) | 0 | 0 | $0 | $0 |
| Cache partial (≥0.75) | 2–3 | 1–2 | $0 (free tier) | ~$0.002–0.005 |
| Full pipeline (miss) | 2–3 | 2–3 | $0 (free tier) | ~$0.005–0.02 |
| Greeting/conversational | 1 | 0 | $0 (free tier) | ~$0.0003–0.001 |

### 8.2 ClickHouse (Required for production)

The production Limese datasource is a ClickHouse server. The app defaults to an embedded SQLite demo DB for testing — but real value comes from the ClickHouse connection.

The enhanced ClickHouse connector now understands 12 tables with detailed column annotations, platform names, business facts, and JOIN hints. Without ClickHouse access, the platform works in demo mode only.

### 8.3 MinIO (Strongly Recommended)

**Not just for backup anymore** — MinIO is the primary conversation store. Every query response is saved here and loaded back on subsequent requests.

| Resource | Minimum | Recommended |
|---|---|---|
| vCPU | 0.5 core | 1 core |
| RAM | 256 MB | 512 MB–1 GB |
| Storage | 10 GB SSD | 50–100 GB SSD |

**Can be replaced by**: Any S3-compatible service (AWS S3, DigitalOcean Spaces, Cloudflare R2, GCS with S3 interoperability).

### 8.4 Optional Services Summary

| Service | CPU | RAM | Storage | Production Recommend? | Why Changed |
|---|---|---|---|---|---|
| **Redis** | Negligible | 256 MB–1 GB | 100 MB–1 GB | Yes | Reduces LLM costs 10–30% via exact-match caching |
| **Qdrant** | **2–4 cores** | **1–4 GB** | **2–20 GB** | **Strongly Yes** | **Now hosts 3 collections instead of 1** — powers cache-first architecture, business knowledge, and DB knowledge |
| **MinIO** | 0.5–1 core | 256 MB–1 GB | 10–100 GB | **Yes** | **Now primary conversation store** (not just backup) |
| **PostgreSQL** | 1–2 cores | 512 MB–2 GB | 1–10 GB | Yes | Replaces SQLite for production metadata + auth |

---

## 9. Scaling & Multi-User Considerations

### 9.1 The real bottleneck: LLM API rate limits

**This is the single most important scaling constraint.** No amount of VM resources can bypass it.

| Users | Queries/Hour (avg) | Cache Hit Rate (est.) | LLM Calls/Hour | Groq Free Limit | Status |
|---|---|---|---|---|---|
| 1 | ~5–10 | ~10% | 18–36 (70B) | 1,200/hr | ✅ OK |
| 10 | ~50–100 | ~25% | 150–300 (70B) | 1,200/hr | ⚠️ May hit 70B limit |
| 50 | ~250–500 | ~35% | 650–1,300 (70B) | 1,200/hr | ❌ Exceeds 70B limit |
| 100 | ~500–1,000 | ~40% | 1,200–2,400 (70B) | 1,200/hr | ❌ Exceeds both limits |

**How the new architecture helps with this:**

1. **Cache-first design**: Qdrant `qa_memory` check runs first. Cache hits (≥0.92) use **zero** LLM calls. Expected hit rate: 20–40% for repeat users.
2. **Partial cache reuse**: Medium-similarity questions (0.75–0.92) reuse cached SQL, saving 1–2 LLM calls per query.
3. **Business knowledge + DB knowledge**: Vector search for relevant context reduces the prompt size for SQL generation, saving tokens.
4. **Fallback chain distributes load**: Across Groq, Gemini, DeepSeek, Mistral, and Claude — reducing single-provider rate limit pressure.

**Solutions to go beyond free tier limits**:
1. **Paid Groq tier** — higher rate limits (quotas by request)
2. **Add all fallback providers** — the chain spreads load across 5+ providers
3. **Maximize cache hit rate** — a well-populated `qa_memory` with 1,000+ entries can achieve 40–60% hit rate
4. **Pre-fetch scheduled queries** — common dashboards pre-computed and cached

### 9.2 Concurrent user scaling

| Users | Uvicorn Workers | Recommended VM | Key Limiter |
|---|---|---|---|
| 1–10 | 2 | 4 vCPU / 8 GB RAM | LLM rate limits |
| 10–50 | 4 | 8 vCPU / 16 GB RAM | LLM rate limits + Qdrant search throughput |
| 50–200 | 8 | 16 vCPU / 32 GB RAM | LLM rate limits + ClickHouse + Qdrant (3 collections) |
| 200+ | 8–16 | 32 vCPU / 64 GB RAM | Need dedicated ClickHouse + paid LLM tier + Qdrant cluster |

### 9.3 Horizontal scaling

The backend is stateless (except for local file caches) and can be horizontally scaled:

```
            ┌──────────┐
            │  LB/NGINX │
            └────┬─────┘
         ┌───────┼───────┐
         │       │       │
    ┌────▼───┐ ┌▼───┐ ┌─▼────┐
    │Worker 1│ │Wk 2│ │Wk N  │
    └────┬───┘ └────┘ └──────┘
         │       │       │
    ┌────┴───────┴───────┴──────────┐
    │  Shared: Redis + Qdrant +     │
    │  MinIO + PostgreSQL +         │
    │  ClickHouse                   │
    └───────────────────────────────┘
```

Each worker:
- Shares Redis, Qdrant (all 3 collections), MinIO, PostgreSQL, ClickHouse
- Has its own in-memory FastEmbed model (200–400 MB each) **or** shares via a single-process embedding service
- Has its own in-memory LLM cache (plus shared Redis cache)
- Can be run on separate VMs behind a load balancer

### 9.4 Database scaling

At very high volumes (1,000+ queries/day, 100+ users):

1. **PostgreSQL connection pooling**: Use `pgbouncer` or managed PostgreSQL to handle 100+ concurrent connections from workers.
2. **ClickHouse read replicas**: If query volume saturates a single ClickHouse node, add read replicas.
3. **Qdrant cluster**: Qdrant supports distributed mode for >1M vectors per collection. Configure replication factor for HA.
4. **MinIO as separate service**: Don't co-locate MinIO on the same VM as the backend at scale. Use dedicated storage or S3-compatible cloud service.

---

## 10. Deployment Topologies

### 10.1 All-in-One (Single VM) — Development / Small Team

```
Single VM (4 vCPU, 8 GB RAM, 50 GB SSD)
├── Uvicorn (2 workers)
├── Redis (Docker)
├── Qdrant (Docker) — 3 collections
├── MinIO (Docker)
├── SQLite (in-process, or PostgreSQL)
└── Static frontend (served by Uvicorn)
```

**Pros**: Simple. Single machine to manage. Everything local.
**Cons**: No redundancy. LLM rate limits cap at ~20 queries/min. MinIO + Qdrant on same disk can cause I/O contention.

**MinIO access**: Uses `localhost:9000`. Set `MINIO_ENDPOINT=http://localhost:9000`.

### 10.2 Two-Tier (Backend + Storage) — Medium Team

```
VM 1: Backend (8 vCPU, 16 GB RAM, 50 GB SSD)
├── Uvicorn (4 workers)
├── Redis (Docker)
└── Static frontend

VM 2: Storage (4 vCPU, 8 GB RAM, 100 GB SSD)
├── Qdrant (Docker) — 3 collections
├── MinIO (Docker)
├── PostgreSQL (Docker)

External: ClickHouse (existing production)
External: LLM APIs (Groq, Gemini, etc.)
```

**Pros**: Storage scales independently. Backend can be horizontally scaled. Disk I/O separation.
**Cons**: Two VMs to manage. Network latency between VMs for Qdrant/MinIO.

### 10.3 Production (Multi-AZ / K8s) — Large Team

```
Load Balancer (NGINX / AWS ALB)
    ↕
Auto-scaling Backend Group (min 2, max 8)
├── Uvicorn (4 workers per instance)
├── Static frontend (built into each)
    ↕
Managed Services:
├── Managed Redis (ElastiCache / Upstash)
├── Managed Qdrant Cloud (Qdrant Cloud / self-hosted cluster)
├── Managed PostgreSQL (RDS / Cloud SQL)
├── Managed S3 (AWS S3 / Cloudflare R2) — replaces MinIO

External: ClickHouse (production or self-hosted cluster)
External: LLM APIs (with paid tier for rate limits)
```

**Pros**: Auto-scaling, redundancy, managed services reduce ops burden. S3 replaces self-hosted MinIO for durability.
**Cons**: Higher cost. More complex setup. Qdrant Cloud costs add up (see §11).

### 10.4 Minimal Viable Production (Budget)

The cheapest production-ready setup:

| Component | Service | Monthly Cost |
|---|---|---|
| VM (4 vCPU, 8 GB RAM) | Hetzner / DigitalOcean / Linode | ~$25–40 |
| Cloudflare (free) | DNS + CDN for static assets | Free |
| MinIO (on same VM) | Docker — localhost:9000 | Included |
| Qdrant (on same VM) | Docker — localhost:6333 | Included |
| LLM API | Groq free tier | Free |
| ClickHouse | Existing hosted instance | — |
| **Total** | | **~$25–40/month** |

**Limitations**: ~20 queries/minute max (Groq free tier). Single point of failure. All storage on one disk.

---

## 11. Cost Estimates

### 11.1 Infrastructure (updated with MinIO)

| Component | Dev / Single User | Small Team | Medium Team | Production |
|---|---|---|---|---|
| **VM / Cloud compute** | $15–25/mo | $40–80/mo | $150–300/mo | $400–800/mo |
| **Managed Redis** | — | $15–30/mo | $30–60/mo | $60–150/mo |
| **Managed Qdrant** | — | $50–100/mo | $100–300/mo | $300–800/mo |
| **Managed PostgreSQL** | — | $15–30/mo | $30–100/mo | $100–300/mo |
| **MinIO / S3 storage** | — | $5–15/mo | $15–50/mo | $50–150/mo |
| **ClickHouse (self-hosted)** | — | $40–80/mo | $150–300/mo | $400–1,000/mo |
| **Storage / backups** | $5/mo | $10/mo | $25/mo | $50/mo |

> Note: Qdrant costs are higher than v1 due to 3 collections instead of 1.

### 11.2 LLM API Costs (Beyond Free Tier)

| Usage | Fast+Smart Calls/mo | Est. Cost (Groq Paid) | With Cache (40% hit rate) |
|---|---|---|---|
| 1K queries | 6K total | ~$0.50–2.00 | ~$0.30–1.20 |
| 10K queries | 60K total | ~$5–20 | ~$3–12 |
| 100K queries | 600K total | ~$50–200 | ~$30–120 |
| 1M queries | 6M total | ~$500–2,000 | ~$300–1,200 |

### 11.3 Total Monthly Cost Comparison (updated)

| Scenario | Infra | LLM API (est.) | Total |
|---|---|---|---|
| Dev (1 user, no extras) | $15–25 | $0 (free tier) | **$15–25** |
| Small team (10 users, with Qdrant + MinIO) | $90–180 | $3–12 | **$93–192** |
| Medium team (50 users, paid LLM, full stack) | $310–640 | $20–100 | **$330–740** |
| Production (200 users, paid LLM, managed services) | $860–1,900 | $100–500 | **$960–2,400** |

---

## 12. Environment Variables & Configuration

### 12.1 Required

| Variable | Example | Purpose |
|---|---|---|
| `GROQ_API_KEY` | `gsk_...` | Primary LLM provider. Copilot will not work without at least one LLM API key. |
| `SECRET_KEY` | random 32+ char string | Used for JWT signing, session security. |

### 12.2 Strongly Recommended for Production

| Variable | Recommended Value | Purpose |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://user:pass@host/db` | Replace SQLite with PostgreSQL for production metadata + auth |
| `REDIS_URL` | `redis://host:6379/0` | Enable LLM response cache (15-min TTL) |
| `QDRANT_ENABLED` | `true` | Enable all 3 vector collections (qa_memory, business_knowledge, db_knowledge) |
| `QDRANT_URL` | `http://host:6333` | Qdrant server address |
| `MINIO_ENDPOINT` | `http://localhost:9000` | MinIO/S3 server for conversation history |
| `MINIO_ACCESS_KEY` | your-key | MinIO access credentials |
| `MINIO_SECRET_KEY` | your-secret | MinIO secret credentials |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | JWT access token expiry |
| `CORS_ORIGINS` | `["https://yourdomain.com"]` | Restrict CORS in production |

### 12.3 Optional (LLM Fallbacks)

| Variable | Fallback For | Free Tier Available |
|---|---|---|
| `GEMINI_API_KEY` | Groq fallback (fast + smart) | Yes (1,500 flash req/day) |
| `ANTHROPIC_API_KEY` | Premium tier (claude-sonnet) | No |
| `DEEPSEEK_API_KEY` | Groq fallback (coding) | No |
| `MISTRAL_API_KEY` | Final fallback tier | No |
| `OPENAI_API_KEY` | Additional fallback | No |

### 12.4 Optional (Integrations)

| Variable | Purpose |
|---|---|
| `TAVILY_API_KEY` | Web search for knowledge-grounded responses |
| `SERPER_API_KEY` | Alternative web search API |
| `SLACK_BOT_TOKEN` | Slack integration for alerts |
| `SLACK_SIGNING_SECRET` | Slack request verification |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASSWORD` | Email notifications (approvals, alerts) |
| `OLLAMA_BASE_URL` | Local LLM (development only) |

### 12.5 New Configs Since v1

| Variable | What Changed |
|---|---|
| `MINIO_ENDPOINT` | **New** — MinIO is now the primary conversation store |
| `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY` | **New** — Required for MinIO auth |
| `MINIO_SECURE` | **New** — Whether to use HTTPS for MinIO (default: false) |
| `MINIO_BUCKET_NAME` | **New** — Default: `analytics-copilot-conversations` |
| `SLACK_BOT_TOKEN` / `SLACK_SIGNING_SECRET` | **New** — Integration |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASSWORD` | **New** — Email integration |
| `TAVILY_API_KEY` / `SERPER_API_KEY` | **New** — Web search |
| `JWT_SECRET_KEY` | **New** — Separate JWT key (falls back to SECRET_KEY) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | **New** — JWT TTL (was hardcoded before) |
| `REFRESH_TOKEN_EXPIRE_DAYS` | **New** — Refresh token TTL |
| `QDRANT_ENABLED` | **Changed** — Default changed to `false` in env (explicit opt-in required) |

---

## Quick Decision Guide (v2)

```
Q1: How many concurrent users?
  ├─ < 20  → 4 vCPU / 8 GB RAM / 50 GB SSD
  └─ ≥ 20  → 8+ vCPU / 16+ GB RAM / 100 GB SSD

Q2: Do you want conversation history to persist?
  ├─ Yes → Add MinIO (or S3-compatible). REQUIRES:
  │         MINIO_ENDPOINT, MINIO_ACCESS_KEY, MINIO_SECRET_KEY
  └─ No  → Skip MinIO (conversations won't carry across sessions)

Q3: Do you want caching and context?
  ├─ Yes → Add Qdrant (3 collections). REQUIRES:
  │         QDRANT_ENABLED=true, QDRANT_URL
  │         Expect: 1–4 GB RAM for Qdrant process
  └─ No  → Skip Qdrant (longer latencies, higher LLM cost)

Q4: Do you want to reduce LLM costs?
  ├─ Yes → Add Redis (exact-match cache) + Qdrant (semantic cache)
  │        Expected 30–50% cost reduction
  └─ No  → Accept full LLM cost per query (~$0.01/per)

Q5: In production?
  ├─ No  → 4 vCPU / 8 GB RAM / 50 GB SSD + DOCKER (Redis + Qdrant + MinIO)
  │        → $25–40/mo
  └─ Yes → 8 vCPU / 16 GB RAM / 100 GB SSD
  │        + PostgreSQL + Redis + Qdrant + MinIO
  │        + Load balancer if >50 users
  │        → $100–300/mo

Q6: Are you using LLM free tiers?
  ├─ Yes → Max ~20 queries/minute (Groq 70B limit).
  │        Cache hit rate becomes critical.
  └─ No  → Paid LLM = higher throughput, add $5–500/mo

Q7: Self-hosting ClickHouse?
  ├─ Yes → Add 8 vCPU / 16 GB RAM / 200+ GB NVMe → $40–1,000/mo
  └─ No  → Ensure low-latency connection to existing ClickHouse
```

---

## What Changed From v1 → v2 (Summary)

| Area | v1 | v2 | Impact |
|---|---|---|---|
| **Pipeline nodes** | 7 | 9 (added `check_qa_memory`, `general_llm`) | More LLM calls for greeting (was free, now costs) but cache hits save far more. |
| **Graph entry point** | `understand_intent` | `check_qa_memory` (cache-first) | Cache hits skip entire pipeline. 0 LLM calls for repeated similar questions. |
| **Greeting response** | Hardcoded strings | LLM-generated via `general_llm` node | More varied UX, but costs ~1 fast LLM call per greeting. |
| **Qdrant collections** | 1 (`dvc_memory`) | 3 (`qa_memory`, `business_knowledge`, `db_knowledge`) | **More RAM needed** (1–4 GB instead of 512 MB–2 GB). **Now strongly recommended.** |
| **MinIO** | Optional backup | Primary conversation store | **Now required for session persistence.** Adds storage + network dependency. |
| **Auth system** | None | JWT + roles + refresh tokens | Adds PostgreSQL dependency, user DB, approval queue. |
| **Business knowledge** | Hardcoded in `business_rag.py` | `business_knowledge.json` + Qdrant vector index | Easier to update. Enables semantic search of KPI definitions. |
| **ClickHouse tables** | ~6 tables | 12 tables (detailed annotations) | No infra impact. LLM prompt is slightly larger. |
| **Analytics** | Pure LLM | Hybrid (LLM + client-side stats + rule-based fallbacks) | Less LLM token usage per query. Same infra. |
| **Frontend** | Light theme only | Light + Dark theme + disambiguation modal + message editing | No server impact. All client-side. |
| **Dependencies** | ~30 packages | + `minio` | 1 more pip package. |

---

> **Document version**: 2.0  
> **Last updated**: May 2026  
> **Project repo**: `analytics_copilot/`
