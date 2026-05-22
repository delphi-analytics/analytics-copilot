# Data Storage Documentation

This document describes where all data is stored in the Analytics Copilot system.

## 1. Database Storage (SQLite/PostgreSQL)

### Location
- **Development**: `dvc.db` (SQLite)
- **Production**: Configured via `DATABASE_URL` environment variable

### Tables

#### users
User accounts and authentication data.
```sql
- id (VARCHAR, PRIMARY KEY)
- email (VARCHAR, UNIQUE)
- name (VARCHAR)
- hashed_password (VARCHAR)
- role (VARCHAR)  -- admin, business_analyst, team_member, non_tech_user
- is_active (BOOLEAN)
- created_at (DATETIME)
- last_login (DATETIME)
- preferences (JSON)  -- User preferences like theme, etc.
```

#### datasources
Registered data sources for analytics queries.
```sql
- id (VARCHAR, PRIMARY KEY)
- name (VARCHAR)
- type (VARCHAR)  -- sqlite, postgresql, clickhouse, csv
- connection_config (JSON)  -- Connection details
- is_active (BOOLEAN)
- created_at (DATETIME)
```

#### conversations
User conversation sessions.
```sql
- id (VARCHAR, PRIMARY KEY)
- user_id (VARCHAR, FOREIGN KEY → users.id)
- datasource_id (VARCHAR)
- title (VARCHAR)
- created_at (DATETIME)
- updated_at (DATETIME)
```

#### messages
Individual messages within conversations.
```sql
- id (VARCHAR, PRIMARY KEY)
- conversation_id (VARCHAR, FOREIGN KEY → conversations.id)
- role (VARCHAR)  -- user, assistant
- content (TEXT)
- metadata (JSON)  -- Chart, insights, etc.
- created_at (DATETIME)
```

#### dashboards
User-created dashboards.
```sql
- id (VARCHAR, PRIMARY KEY)
- user_id (VARCHAR, FOREIGN KEY → users.id)
- name (VARCHAR)
- layout_config (JSON)
- created_at (DATETIME)
- updated_at (DATETIME)
```

#### dashboard_charts
Charts within dashboards.
```sql
- id (VARCHAR, PRIMARY KEY)
- dashboard_id (VARCHAR, FOREIGN KEY → dashboards.id)
- title (VARCHAR)
- query_config (JSON)
- chart_config (JSON)
- position (JSON)
```

#### query_log
History of all queries executed.
```sql
- id (VARCHAR, PRIMARY KEY)
- user_id (VARCHAR)
- question (TEXT)
- sql_query (TEXT)
- row_count (INTEGER)
- latency_ms (INTEGER)
- created_at (DATETIME)
```

## 2. Browser LocalStorage

### Chat Session Storage
**Key**: `analytics-copilot-chat-storage`

Per-user chat sessions stored locally in the browser.
```javascript
{
  userId: "user-id",
  sessions: [
    {
      id: "session-id",
      conversationId: "backend-conversation-id",
      messages: [...],
      title: "session title",
      initiatedAt: timestamp,
      updatedAt: timestamp,
      pinned: boolean
    }
  ],
  activeSessionId: "current-session-id",
  datasourceId: "limese",
  uploadedFile: null
}
```

**Important**: Chat history is now isolated per user. When a different user logs in, the chat history is cleared and only their sessions are shown.

### Authentication Storage
**Key**: `auth-storage`

User authentication state.
```javascript
{
  state: {
    user: { id, email, name, role, ... },
    accessToken: "jwt-token"
  }
}
```

### Theme Storage
**Key**: `theme-storage`

User theme preference.
```javascript
{
  theme: "dark" | "light"
}
```

## 3. File System Storage

### Database Intelligence Cache
**Location**: `/tmp/dvc_metadata/db_intelligence.json`

Cached schema metadata for the ClickHouse database.
- Column types and statistics
- Business facts (total revenue, order counts)
- Column annotations
- Global query rules

Refreshes every 24 hours.

### Uploaded Files
**Location**: `./uploads/`

User-uploaded CSV/Excel files for analysis.

### Frontend Static Assets
**Location**: `backend/static/`

Built React frontend assets (after running `npm run build`).

## 4. External Storage (Optional)

### Redis (if configured)
**Purpose**: Query result caching
- Key: `cache:query:{hash}`
- TTL: 15 minutes

### Qdrant (if configured)
**Purpose**: Vector memory for semantic search
- Collection: `analytics_queries`
- Stores: Query-SQL embeddings for retrieval

### MinIO (if configured)
**Purpose**: Conversation history backup
- Bucket: `analytics-copilot-conversations`
- Stores: JSON backups of conversations

## 5. ClickHouse Production Database

### Connection
**Host**: Configured via environment (see `.env`)
**Database**: limese_production

### Key Tables

#### combined_sales_final
Final cleaned sales data.
- `order_id`, `date_created`, `sales_platform`
- `item_name`, `internal_sku`, `category_l1`, `category_l2`
- `quantity_ordered`, `row_subtotal` (revenue)
- `final_status`

#### product_master
Product catalog and metadata.
- `internal_sku`, `item_name`
- `brand`, `category_l1`, `category_l2`
- `mrp`, `pack_size`

#### inventory_sales_overview_new
Current inventory levels.
- `internal_sku`, `available_inventory`
- `warehouse_location`

## 6. Data Flow

### Query Execution Flow
1. User asks question (frontend)
2. Intent classification (LLM)
3. Schema discovery (DB Intelligence)
4. SQL generation (LLM)
5. Query execution (ClickHouse/SQLite)
6. Result analysis (LLM)
7. Visualization generation
8. Response storage (database + localStorage)

### User Authentication Flow
1. User submits credentials
2. Backend validates against `users` table
3. JWT tokens generated (access + refresh)
4. Access token stored in localStorage
5. Refresh token stored as httpOnly cookie

## 7. Configuration

### Environment Variables

```bash
# Database
DATABASE_URL=sqlite+aiosqlite:///./dvc.db

# LLM Providers
GROQ_API_KEY=xxx
LLM_FAST_MODEL=groq/llama-3.1-8b-instant
LLM_SMART_MODEL=groq/llama-3.3-70b-versatile

# Optional Storage
REDIS_URL=redis://localhost:6380/0
QDRANT_URL=http://localhost:6333
MINIO_ENDPOINT=localhost:9000
```

## 8. Security Notes

1. **User Isolation**: Chat history is now properly isolated per user ID
2. **Password Hashing**: All passwords are hashed using bcrypt
3. **JWT Tokens**: Access tokens expire in 15 minutes, refresh tokens in 7 days
4. **HttpOnly Cookies**: Refresh tokens stored in httpOnly cookies to prevent XSS
5. **SQL Injection**: All queries use parameterized statements via SQLAlchemy
6. **CORS**: Configured to allow only specific origins in production

## 9. Backup Recommendations

### Daily Backups
- SQLite database: `dvc.db`
- ClickHouse: `clickhouse-backup` tool
- MinIO buckets: Versioning enabled

### Weekly Backups
- Full database dumps
- DB intelligence cache

### Monthly Archives
- Long-term query logs
- User analytics and usage patterns
