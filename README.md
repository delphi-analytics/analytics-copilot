# Data Visualization Copilot

AI-powered analytics platform — ask questions in plain English and get interactive charts, SQL queries, and insights. Built with a 7-step LangGraph agent pipeline.

![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)
![React](https://img.shields.io/badge/React-19+-cyan.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

## Features

- **Natural Language Queries** — Ask questions like "Show me sales by region last quarter" and get charts
- **Multi-Database Support** — SQLite, PostgreSQL, ClickHouse, CSV/Excel
- **Auto-Generated Visualizations** — Apache ECharts with smart type detection
- **SQL Generation** — View and edit the generated SQL queries
- **Insights & Metrics** — Automatic analysis with key findings and follow-up suggestions
- **Conversation Memory** — Context-aware follow-up questions
- **LLM Caching** — 15-min cache for repeat queries (80% latency reduction)

## Tech Stack

### Backend
- **FastAPI** — Async REST API with automatic OpenAPI docs
- **LangGraph** — 7-step agent orchestration pipeline
- **LiteLLM** — Provider-agnostic LLM calls (Groq, Claude, Gemini, OpenAI)
- **SQLAlchemy** — Async ORM with PostgreSQL/SQLite support
- **Redis** — Query result caching
- **DuckDB** — CSV/Excel file analysis

### Frontend
- **React 19** + **TypeScript** — Modern React with hooks
- **Vite** — Lightning-fast build tool
- **Apache ECharts** — Rich charting library
- **Zustand** — Lightweight state management
- **TailwindCSS** — Utility-first styling

## Quick Start

### Prerequisites
- Python 3.12+
- Node.js 20+
- Docker (optional, for PostgreSQL/Redis)

### 1. Clone the Repository

```bash
git clone https://github.com/sharvarijiwtode0/analytics-copilot.git
cd analytics-copilot
```

### 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` and add your **Groq API Key** (free):
```bash
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxx  # Get from console.groq.com
```

### 3. Start the Application

```bash
./start.sh
```

This will:
- Create a virtual environment
- Install Python dependencies
- Build the frontend
- Start the backend server on port 8001

### 4. Open in Browser

Navigate to:
- **App**: http://localhost:8001
- **API Docs**: http://localhost:8001/docs

## Usage Examples

### Example Queries

| Query | Output |
|-------|--------|
| "Show me monthly revenue trends" | Line chart with monthly sales |
| "Top 5 products by units sold" | Bar chart with product rankings |
| "What's the customer distribution by country?" | Pie chart with country breakdown |
| "Compare sales across regions this quarter" | Grouped bar chart with regional comparison |

### Upload Your Own Data

Upload CSV/Excel files via the UI and immediately query them with natural language.

## Architecture

### Agent Pipeline

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Intent    │───▶│   Schema    │───▶│ SQL Gen     │
│ Understand  │    │ Discovery   │    │             │
└─────────────┘    └─────────────┘    └─────────────┘
                                              │
┌─────────────┐    ┌─────────────┐    ┌─────▼─────┐
│   Response  │◀───│   Viz       │◀───│  Execute  │
│  Compose    │    │   Config    │    │    SQL    │
└─────────────┘    └─────────────┘    └───────────┘
                           ▲
                           │
                    ┌──────┴──────┐
                    │   Insights  │
                    │   Analysis  │
                    └─────────────┘
```

### DB Intelligence Layer

On startup, the system scans connected databases to build comprehensive schema context:
- Column types, unique counts, exact categorical values
- Business facts (total revenue, order counts, date ranges)
- Query patterns validated against real data

Context cached at `/tmp/dvc_metadata/db_intelligence.json`, refreshes every 24 hours.

## API Endpoints

### Chat & Analysis

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/copilot/query` | POST | Send question, get chart + insights |
| `/api/v1/copilot/upload` | POST | Upload CSV/Excel file |
| `/api/v1/copilot/history/{id}` | GET | Get conversation history |
| `/api/v1/copilot/schema/{id}` | GET | Get datasource schema |

### Database Intelligence

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/db/context` | GET | Get DB intelligence summary |
| `/api/v1/db/context/refresh` | POST | Trigger database scan |

## Configuration

### LLM Providers

The system uses Groq's free models by default. Configure premium models in `.env`:

```bash
# Free models (Groq)
LLM_FAST_MODEL=groq/llama-3.1-8b-instant
LLM_SMART_MODEL=groq/llama-3.3-70b-versatile

# Premium models (optional)
LLM_PREMIUM_MODEL=anthropic/claude-sonnet-4-6
ANTHROPIC_API_KEY=sk-ant-...
```

### Datasources

Two datasources are registered by default:
- **default** — SQLite demo database with sample sales data
- **limese** — ClickHouse production database (optional)

Register new datasources via API or in `backend/main.py`.

## Development

### Backend Development

```bash
source venv/bin/activate
PYTHONPATH=. python -m uvicorn backend.main:app --host 0.0.0.0 --port 8001 --reload
```

### Frontend Development

```bash
cd frontend
npm install
npm run dev  # Runs on port 5173 with hot reload
```

### Docker Compose

```bash
docker compose up -d  # PostgreSQL + Redis + Qdrant
docker compose --profile vector up -d  # Include Qdrant vector DB
```

### Building for Production

```bash
cd frontend && npm run build
```

Frontend assets are served from `backend/static/` by FastAPI.

## Project Structure

```
analytics-copilot/
├── backend/
│   ├── agent/              # LangGraph nodes and orchestration
│   │   ├── nodes/          # 7 agent pipeline steps
│   │   ├── graph.py        # DAG definition
│   │   ├── state.py        # Shared state object
│   │   └── llm.py          # LLM routing & calls
│   ├── data/               # Database connectors
│   ├── models/             # SQLAlchemy ORM models
│   ├── routers/            # FastAPI route handlers
│   ├── services/           # DB intelligence, caching
│   ├── visualization/      # Chart generation logic
│   └── main.py             # FastAPI app entry point
├── frontend/
│   ├── src/
│   │   ├── api/            # API client
│   │   ├── components/     # React components
│   │   ├── pages/          # Page components
│   │   ├── store/          # Zustand state
│   │   └── hooks/          # Custom hooks
│   └── package.json
├── infrastructure/         # Terraform/K8s configs (optional)
├── scripts/                # Utility scripts
├── docker-compose.yml
├── requirements.txt
└── CLAUDE.md               # AI assistant guide
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License.

## Acknowledgments

- **LangGraph** — Agent orchestration framework
- **LiteLLM** — Unified LLM API
- **Groq** — Free, fast LLM inference
- **Apache ECharts** — Powerful charting library
