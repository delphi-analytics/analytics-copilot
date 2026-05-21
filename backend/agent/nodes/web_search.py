"""Web Search Node - Handle external data queries and comparisons."""
import asyncio
import structlog
from backend.agent.state import AnalyticsState

log = structlog.get_logger(__name__)


async def handle_web_search(state: AnalyticsState) -> AnalyticsState:
    """
    Handle questions that require external web search.
    For comparison questions, runs both web search AND analytics in parallel.
    """
    question = state.get("user_question", "")
    datasource_id = state.get("datasource_id", "")

    from backend.services.web_search import search_web, is_comparison_question
    from backend.config import settings
    from backend.agent.graph import run_analytics_agent

    # Get API key from config (TAVILY_API_KEY or SERPER_API_KEY)
    api_key = getattr(settings, "tavily_api_key", "") or getattr(settings, "serper_api_key", "")
    provider = "tavily" if getattr(settings, "tavily_api_key", "") else "serper"

    # Check if this is a comparison question (needs both web + analytics)
    is_comparison = is_comparison_question(question)

    if is_comparison:
        log.info("web_search.comparison_question", question=question[:50])

        # Create a task for web search
        web_task = asyncio.create_task(search_web(question, api_key, provider))

        # Create a task for the analytics pipeline
        # Build initial state for the analytics pipeline
        analytics_task = asyncio.create_task(
            run_analytics_agent(
                question=question,
                datasource_id=datasource_id,
                session_id=state.get("session_id", ""),
                conversation_id=state.get("conversation_id", ""),
                conversation_history=state.get("conversation_history", []),
                user_id=state.get("user_id", "anonymous")
            )
        )

        # Run both in parallel and wait for both to complete
        web_result, analytics_result = await asyncio.gather(web_task, analytics_task)

        log.info(
            "web_search.parallel_complete",
            web_sources=len(web_result.get("sources", [])),
            analytics_rows=analytics_result.get("row_count", 0)
        )

        # Store both results in state for responder to merge
        return {
            **state,
            "web_search_results": web_result,
            "analytics_results": analytics_result,
            "is_comparison_query": True,
            "skip_pipeline": True,  # Skip rest of pipeline, go straight to responder
            "pre_filter_response": None,  # Clear any pre-filter response
        }
    else:
        # Pure web search question (not a comparison)
        log.info("web_search.pure_web_question", question=question[:50])
        web_result = await search_web(question, api_key, provider)

        # Format as a response
        summary = web_result.get("summary", "No results found.")
        sources = web_result.get("sources", [])

        response_text = summary
        if sources:
            response_text += "\n\n**Sources:**\n"
            for i, source in enumerate(sources[:3], 1):
                response_text += f"{i}. [{source['title']}]({source['url']})\n"

        return {
            **state,
            "skip_pipeline": True,
            "pre_filter_response": {
                "text": response_text,
                "chart": None,
                "insights": [],
                "key_metrics": {},
                "follow_up_questions": [
                    f"Tell me more about our data on {question[:30]}",
                    "Compare with our internal metrics",
                    "Show me trends in our data"
                ],
                "sql": "",
                "sql_explanation": "",
                "row_count": 0,
                "viz_type": None,
                "columns": [],
                "rows": [],
                "total_latency_ms": 500,
                "model_used": "web_search",
            }
        }
