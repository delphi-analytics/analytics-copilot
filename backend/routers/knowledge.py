from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from backend.auth.dependencies import get_current_user, require_role
from backend.models.user import User
from backend.services.knowledge.business_knowledge import (
    get_business_knowledge_service,
    get_db_knowledge_service,
    get_qa_memory_service,
    BusinessKnowledgeService,
    DBKnowledgeService,
)

router = APIRouter(prefix="/knowledge", tags=["Knowledge Management"])


# ─── Business Knowledge Endpoints ─────────────────────────────────────────────

class BusinessKnowledgeResponse(BaseModel):
    kpi_definitions: list[dict]
    ambiguous_keywords: list[dict]
    business_rules: list[str]
    industry_context: str | None = None
    glossary: list[dict]


@router.get("/business", response_model=BusinessKnowledgeResponse)
async def get_business_knowledge(
    current_user: Annotated[User, Depends(get_current_user)] = None
) -> dict:
    """Get the current business knowledge base."""
    service = get_business_knowledge_service()
    knowledge = service.load_knowledge_base()
    return knowledge


@router.post("/business/index")
async def index_business_knowledge(
    current_user: Annotated[User, Depends(require_role("admin", "business_analyst"))] = None
) -> dict:
    """Re-index business knowledge into Qdrant."""
    service = get_business_knowledge_service()
    service.index_knowledge()
    return {"status": "indexed", "message": "Business knowledge indexed successfully"}


@router.post("/business/search")
async def search_business_knowledge(
    query: str,
    limit: int = 5,
    current_user: Annotated[User, Depends(get_current_user)] = None
) -> list[dict]:
    """Search business knowledge for relevant context."""
    service = get_business_knowledge_service()
    results = service.search(query, limit=limit)
    return results


# ─── DB Knowledge Endpoints ───────────────────────────────────────────────────

class TableSchemaInput(BaseModel):
    table_name: str
    description: str = ""
    row_count: int = 0
    aliases: list[str] = []
    columns: list[dict]


@router.post("/db/index-table")
async def index_db_table(
    schema: TableSchemaInput,
    current_user: Annotated[User, Depends(require_role("admin", "business_analyst"))] = None
) -> dict:
    """Index a table's schema into the DB knowledge base."""
    service = get_db_knowledge_service()
    service.index_table_schema(
        schema.table_name,
        {
            "description": schema.description,
            "row_count": schema.row_count,
            "aliases": schema.aliases,
            "columns": schema.columns,
        }
    )
    return {"status": "indexed", "table": schema.table_name}


@router.post("/db/search")
async def search_db_knowledge(
    query: str,
    limit: int = 5,
    current_user: Annotated[User, Depends(get_current_user)] = None
) -> list[dict]:
    """Search DB knowledge for relevant tables/columns."""
    service = get_db_knowledge_service()
    results = service.search(query, limit=limit)
    return results


@router.post("/db/resolve-tables")
async def resolve_table_names(
    query: str,
    current_user: Annotated[User, Depends(get_current_user)] = None
) -> list[str]:
    """Resolve table names from natural language query."""
    service = get_db_knowledge_service()
    tables = service.resolve_table_name(query)
    return tables


# ─── QA Memory Endpoints ───────────────────────────────────────────────────────

class QASearchResponse(BaseModel):
    question: str
    answer: str
    sql: str
    tables: list[str]
    similarity: float | None = None


@router.get("/memory/similar")
async def check_similar_questions(
    question: str,
    threshold: float = 0.92,
    current_user: Annotated[User, Depends(get_current_user)] = None
) -> QASearchResponse | None:
    """Check if a similar question has been asked before."""
    service = get_qa_memory_service()
    result = service.search(question, threshold=threshold)
    if result:
        return QASearchResponse(
            question=result["question"],
            answer=result["answer"],
            sql=result["sql"],
            tables=result["tables"],
            similarity=None,
        )
    return None


# ─── Disambiguation Endpoint ──────────────────────────────────────────────────

class DisambiguationRequest(BaseModel):
    query: str


class DisambiguationResponse(BaseModel):
    requires_disambiguation: bool
    keyword: str | None = None
    options: list[str] = []


@router.post("/disambiguate", response_model=DisambiguationResponse)
async def check_disambiguation(
    request: DisambiguationRequest,
    current_user: Annotated[User, Depends(get_current_user)] = None
) -> DisambiguationResponse:
    """Check if query contains ambiguous keywords that need clarification."""
    service = get_business_knowledge_service()
    result = service.check_ambiguous_keywords(request.query)

    if result:
        return DisambiguationResponse(
            requires_disambiguation=True,
            keyword=result["keyword"],
            options=result["meanings"]
        )

    return DisambiguationResponse(requires_disambiguation=False)


# ─── Admin: Re-index All Knowledge ────────────────────────────────────────────

@router.post("/reindex-all")
async def reindex_all_knowledge(
    current_user: Annotated[User, Depends(require_role("admin"))] = None
) -> dict:
    """Re-index all knowledge bases. Admin only."""
    business_service = get_business_knowledge_service()
    business_service.index_knowledge()

    # Re-index DB knowledge from current DB intelligence
    from backend.services.db_intelligence import get_db_context
    db_context = get_db_context()
    db_service = get_db_knowledge_service()

    indexed_count = 0
    for table_name, table_data in db_context.get("tables", {}).items():
        columns = []
        for col in table_data.get("columns", []):
            columns.append({
                "name": col["name"],
                "type": col.get("type", ""),
                "description": col.get("annotation", ""),
                "sample_values": col.get("exact_values", [])[:10],
                "is_categorical": col.get("is_categorical", False)
            })

        db_service.index_table_schema(
            table_name,
            {
                "description": f"Table {table_name}",
                "row_count": table_data.get("row_count", 0),
                "aliases": [],
                "columns": columns
            }
        )
        indexed_count += 1

    return {
        "status": "reindexed",
        "business_knowledge": "indexed",
        "db_knowledge_tables": indexed_count
    }
