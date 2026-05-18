import hashlib
import structlog
from backend.agent.state import AnalyticsState
from backend.services.cache import redis_cache

log = structlog.get_logger(__name__)

async def check_query_cache(state: AnalyticsState) -> AnalyticsState:
    """
    Step 0: Check if this exact question has a cached response in Redis.
    Uses a hash of (question + datasource_id) as the key.
    """
    question = state["user_question"].strip().lower()
    ds_id = state["datasource_id"]
    
    # Generate cache key
    cache_key = f"query_cache:{hashlib.md5(f'{question}:{ds_id}'.encode()).hexdigest()}"
    
    cached_data = await redis_cache.get(cache_key)
    if cached_data:
        log.info("cache.hit", question=question)
        # Populate state with cached data to skip processing
        return {
            **state,
            "final_response": cached_data,
            "is_cached": True
        }
    
    log.info("cache.miss", question=question)
    return {**state, "is_cached": False, "cache_key": cache_key}
