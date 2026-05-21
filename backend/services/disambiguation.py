"""Disambiguation Service - Detect and resolve ambiguous keywords."""
import structlog
from backend.services.knowledge.business_knowledge import get_business_knowledge_service

log = structlog.get_logger(__name__)


async def check_disambiguation(question: str) -> dict | None:
    """
    Check if the question contains ambiguous keywords that need clarification.

    Returns None if no ambiguity, or a dict with:
    {
        "keyword": "ROI",
        "options": ["Return on Investment", "Republic of India", "Rate of Interest"],
        "context_clues": ["profit", "investment", "return"]
    }
    """
    try:
        business_service = get_business_knowledge_service()
        result = business_service.check_ambiguous_keywords(question)
        return result
    except Exception as e:
        log.warning("disambiguation.check_failed", error=str(e))
        return None


def resolve_disambiguation(question: str, keyword: str, selected_meaning: str) -> str:
    """
    Inject the selected meaning into the question as context.

    Example:
        question: "What is our ROI?"
        keyword: "ROI"
        selected_meaning: "Return on Investment"
        returns: "What is our ROI? (Note: ROI refers to Return on Investment)"
    """
    return f"{question} [Context: {keyword} means '{selected_meaning}']"
