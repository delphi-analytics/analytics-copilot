"""
Business Knowledge RAG Layer
Stores and retrieves business context, glossary, and Q&A using ChromaDB.
"""
from __future__ import annotations
import json
from pathlib import Path

import structlog

log = structlog.get_logger(__name__)

# Business glossary for Limese Analytics domain
BUSINESS_GLOSSARY = {
    "Nykaa Beauty": "Leading Indian beauty e-commerce platform, one of Limese's main sales channels",
    "Myntra_PPMP": "Myntra fashion marketplace platform, another key sales channel",
    "Shopify": "E-commerce platform for D2C (direct-to-consumer) sales",
    "Unicomm": "B2B distribution channel for Limese products",
    "Zoho": "CRM and sales management system",
    "GMV": "Gross Merchandise Value - Total value of merchandise sold on a platform",
    "D2C": "Direct-to-Consumer - Selling directly to customers without intermediaries",
    "MoM": "Month-over-Month growth comparison",
    "PPMP": "Pay Per Marketplace Platform - Commission-based selling model",
    "row_subtotal": "Total order value before returns/cancellations",
    "final_status": "Order completion status (cancelled, returned, delivered)",
    "SKU": "Stock Keeping Unit - Unique product identifier",
    "Limese": "Beauty and personal care products company, sells across multiple platforms",
    "inventory": "Current stock quantity available for sale",
    "category_l1": "Top-level product category (e.g., Skincare, Makeup, Haircare)",
    "category_l2": "Sub-category within L1 (e.g., Face Wash, Foundation, Shampoo)",
}

# Metric definitions
METRIC_DEFINITIONS = {
    "revenue": "row_subtotal from orders where final_status is NOT cancelled/returned",
    "total revenue": "SUM(row_subtotal) excluding cancelled and returned orders",
    "orders": "Count of orders with valid order_id",
    "aov": "Average Order Value = Total Revenue / Number of Orders",
    "inventory value": "Current stock quantity * MRP (maximum retail price)",
    "return rate": "Percentage of orders marked as 'returned'",
    "cancellation rate": "Percentage of orders marked as 'cancelled'",
}

# Common question-answer pairs
COMMON_QA = [
    {
        "q": "What platforms does Limese sell on?",
        "a": "Limese sells on Nykaa Beauty, Myntra, Shopify (D2C), and through B2B partners like Unicomm."
    },
    {
        "q": "How is revenue calculated?",
        "a": "Revenue = SUM(row_subtotal) from orders where final_status is NOT 'cancelled' or 'returned'. Only completed/delivered orders count."
    },
    {
        "q": "What is the difference between Nykaa and Myntra?",
        "a": "Nykaa is a beauty-focused marketplace while Myntra is a fashion marketplace. Both are key sales channels for Limese products."
    },
    {
        "q": "What is category_l1 vs category_l2?",
        "a": "category_l1 is the top-level category (Skincare, Makeup, Haircare). category_l2 is the specific sub-category within that (Face Wash, Foundation, Shampoo)."
    },
]

# Platform-specific insights
PLATFORM_INSIGHTS = {
    "Nykaa": "Beauty marketplace, high volume, competitive commission structure",
    "Myntra": "Fashion marketplace, seasonal trends important",
    "Shopify": "D2C channel, higher margins, direct customer relationship",
    "Unicomm": "B2B distribution, bulk orders, different pricing model",
}


def get_business_context(query: str) -> dict:
    """
    Get relevant business context for a user query.
    Uses keyword matching to find relevant glossary terms and definitions.
    """
    query_lower = query.lower()
    context = {
        "glossary": {},
        "metrics": {},
        "platforms": {},
        "qa": [],
    }

    # Find relevant glossary terms
    for term, definition in BUSINESS_GLOSSARY.items():
        if term.lower() in query_lower or any(word in query_lower for word in term.lower().split()):
            context["glossary"][term] = definition

    # Find relevant metrics
    for metric, definition in METRIC_DEFINITIONS.items():
        if metric.lower() in query_lower:
            context["metrics"][metric] = definition

    # Find relevant platforms
    for platform, insight in PLATFORM_INSIGHTS.items():
        if platform.lower() in query_lower:
            context["platforms"][platform] = insight

    # Find relevant Q&A
    for qa in COMMON_QA:
        if any(word in query_lower for word in qa["q"].lower().split()):
            context["qa"].append(qa)

    return context


def build_rag_prompt(query: str) -> str:
    """
    Build a prompt with relevant business context for the LLM.
    This enhances responses with domain-specific knowledge.
    """
    context = get_business_context(query)

    prompt_parts = ["BUSINESS CONTEXT FOR THIS QUERY:\n"]

    if context["glossary"]:
        prompt_parts.append("Relevant Terms:")
        for term, definition in context["glossary"].items():
            prompt_parts.append(f"  • {term}: {definition}")

    if context["metrics"]:
        prompt_parts.append("\nMetric Definitions:")
        for metric, definition in context["metrics"].items():
            prompt_parts.append(f"  • {metric}: {definition}")

    if context["platforms"]:
        prompt_parts.append("\nPlatform Insights:")
        for platform, insight in context["platforms"].items():
            prompt_parts.append(f"  • {platform}: {insight}")

    if context["qa"]:
        prompt_parts.append("\nRelated Information:")
        for qa in context["qa"]:
            prompt_parts.append(f"  • Q: {qa['q']}\n    A: {qa['a']}")

    if not any(context.values()):
        prompt_parts.append("  (No specific business context needed for this query)")

    return "\n".join(prompt_parts)


# Store initialization (persistent file-based cache)
CACHE_FILE = Path("/tmp/dvc_metadata/business_rag_cache.json")

def load_business_knowledge() -> dict:
    """Load business knowledge from cache file."""
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE) as f:
                return json.load(f)
        except:
            pass

    # Default knowledge
    return {
        "glossary": BUSINESS_GLOSSARY,
        "metrics": METRIC_DEFINITIONS,
        "qa": COMMON_QA,
        "platforms": PLATFORM_INSIGHTS,
    }


def save_business_knowledge(knowledge: dict) -> None:
    """Save business knowledge to cache file."""
    try:
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CACHE_FILE, "w") as f:
            json.dump(knowledge, f, indent=2)
    except Exception as e:
        log.warning("rag.cache_save_failed", error=str(e))


def add_custom_entry(entry_type: str, key: str, value: str) -> None:
    """
    Add a custom business knowledge entry.
    Types: glossary, metric, qa, platform
    """
    knowledge = load_business_knowledge()

    if entry_type == "glossary":
        knowledge["glossary"][key] = value
    elif entry_type == "metric":
        knowledge["metrics"][key] = value
    elif entry_type == "qa":
        knowledge["qa"].append({"q": key, "a": value})
    elif entry_type == "platform":
        knowledge["platforms"][key] = value

    save_business_knowledge(knowledge)
    log.info("rag.entry_added", type=entry_type, key=key)


def get_all_knowledge() -> dict:
    """Get all business knowledge for display/editing."""
    return load_business_knowledge()
