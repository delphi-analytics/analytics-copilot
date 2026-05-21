"""Web Search Service - External data integration for comparison questions."""
import structlog
from typing import Any
import httpx

log = structlog.get_logger(__name__)


async def search_web(query: str, api_key: str = "", provider: str = "tavily") -> dict[str, Any]:
    """
    Search the web for external data to compare with internal analytics.

    Args:
        query: The search query
        api_key: API key for the search provider
        provider: "tavily" or "serper"

    Returns:
        dict with search results including summary and sources
    """
    if not api_key:
        log.warning("web_search.no_api_key", provider=provider)
        return {
            "summary": "Web search is not configured. Please add an API key.",
            "sources": [],
            "query": query
        }

    try:
        if provider == "tavily":
            return await _search_tavily(query, api_key)
        elif provider == "serper":
            return await _search_serper(query, api_key)
        else:
            return {
                "summary": f"Unknown search provider: {provider}",
                "sources": [],
                "query": query
            }
    except Exception as e:
        log.error("web_search.failed", error=str(e), provider=provider)
        return {
            "summary": f"Web search failed: {str(e)}",
            "sources": [],
            "query": query
        }


async def _search_tavily(query: str, api_key: str) -> dict[str, Any]:
    """Search using Tavily API (optimized for LLMs)."""
    url = "https://api.tavily.com/search"
    params = {
        "api_key": api_key,
        "query": query,
        "search_depth": "basic",
        "max_results": 5,
        "include_answer": True,
        "include_raw_content": False
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        data = response.json()

    return {
        "summary": data.get("answer", ""),
        "sources": [
            {
                "title": result.get("title", ""),
                "url": result.get("url", ""),
                "snippet": result.get("content", "")
            }
            for result in data.get("results", [])
        ],
        "query": query
    }


async def _search_serper(query: str, api_key: str) -> dict[str, Any]:
    """Search using Serper API (Google Search)."""
    url = "https://google.serper.dev/search"
    payload = {
        "q": query,
        "num": 5
    }
    headers = {
        "X-API-KEY": api_key,
        "Content-Type": "application/json"
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()

    # Build summary from knowledge graph if available
    summary = ""
    if "knowledgeGraph" in data:
        kg = data["knowledgeGraph"]
        summary = f"{kg.get('description', '')} {kg.get('descriptionLink', '')}"

    return {
        "summary": summary,
        "sources": [
            {
                "title": item.get("title", ""),
                "url": item.get("link", ""),
                "snippet": item.get("snippet", "")
            }
            for item in data.get("organic", [])
        ],
        "query": query
    }


def is_comparison_question(question: str) -> bool:
    """Check if the question asks for external comparison (world vs our data)."""
    comparison_keywords = [
        "vs", "versus", "compared to", "compared with", "against",
        "globally", "worldwide", "international", "market",
        "industry", "benchmark", "competitor", "competition"
    ]
    question_lower = question.lower()
    return any(keyword in question_lower for keyword in comparison_keywords)
