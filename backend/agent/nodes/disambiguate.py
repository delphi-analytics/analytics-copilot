"""
Disambiguation node.
"""
from backend.agent.state import AnalyticsState
import structlog

log = structlog.get_logger(__name__)

AMBIGUOUS_TERMS = {
    "roi": {
        "keyword": "ROI",
        "options": [
            "Return on Investment",
            "Republic of India",
            "Rate of Interest"
        ]
    }
}

async def disambiguate(state: AnalyticsState) -> AnalyticsState:
    question = state.get("user_question", "").lower()
    history = state.get("conversation_history", [])
    
    # Simple check if the user already specified an option in this turn
    for key, data in AMBIGUOUS_TERMS.items():
        if key in question.split() or key in question:
            # Check if any of the options are already explicitly mentioned
            already_clear = any(opt.lower() in question for opt in data["options"])
            
            # Or if it was mentioned in the last turn
            if not already_clear and history:
                last_msg = history[-1].get("content", "").lower()
                already_clear = any(opt.lower() in last_msg for opt in data["options"])
                
            if not already_clear:
                log.info("disambiguation.triggered", keyword=data["keyword"])
                return {
                    **state,
                    "error": f"DISAMBIGUATION_NEEDED:{data['keyword']}",
                    "skip_pipeline": True,
                    "pre_filter_response": {
                        "text": "I need clarification to answer this.",
                        "error": f"DISAMBIGUATION_NEEDED:{data['keyword']}",
                        "follow_up_questions": data["options"],
                        "chart": None,
                        "insights": [],
                        "key_metrics": {},
                        "sql": "",
                        "row_count": 0,
                        "viz_type": None,
                    }
                }
                
    return state
