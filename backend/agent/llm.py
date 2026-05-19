"""
LLM routing for the Data Visualization Copilot.
Uses LiteLLM for provider-agnostic calls.
Groq (free) by default — upgrade to Claude/GPT via .env.
"""
from __future__ import annotations
import asyncio
import os
import time
from dataclasses import dataclass

import litellm
import structlog

from backend.config import settings

log = structlog.get_logger(__name__)
litellm.set_verbose = False


def _inject_keys() -> None:
    if settings.groq_api_key:
        os.environ["GROQ_API_KEY"] = settings.groq_api_key
    if settings.anthropic_api_key:
        os.environ["ANTHROPIC_API_KEY"] = settings.anthropic_api_key
    if settings.openai_api_key:
        os.environ["OPENAI_API_KEY"] = settings.openai_api_key
    if settings.gemini_api_key:
        os.environ["GEMINI_API_KEY"] = settings.gemini_api_key
        os.environ["GOOGLE_API_KEY"] = settings.gemini_api_key
    if settings.mistral_api_key:
        os.environ["MISTRAL_API_KEY"] = settings.mistral_api_key
    if settings.openrouter_api_key:
        os.environ["OPENROUTER_API_KEY"] = settings.openrouter_api_key
    if settings.deepseek_api_key:
        os.environ["DEEPSEEK_API_KEY"] = settings.deepseek_api_key
    if settings.cohere_api_key:
        os.environ["COHERE_API_KEY"] = settings.cohere_api_key


_inject_keys()


@dataclass
class LLMResponse:
    content: str
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: int


def _get_key(model: str) -> str | None:
    if "groq" in model:
        return settings.groq_api_key or None
    if "claude" in model or "anthropic" in model:
        return settings.anthropic_api_key or None
    if "gpt" in model or "openai" in model:
        return settings.openai_api_key or None
    if "gemini" in model:
        return settings.gemini_api_key or None
    if "mistral" in model:
        return settings.mistral_api_key or None
    if "openrouter" in model:
        return settings.openrouter_api_key or None
    if "deepseek" in model:
        return settings.deepseek_api_key or None
    if "cohere" in model or "command" in model:
        return settings.cohere_api_key or None
    return None


async def call_llm(
    messages: list[dict],
    model: str | None = None,
    max_tokens: int = 2000,
    temperature: float = 0.1,
    task: str = "general",
) -> LLMResponse:
    """
    Single LLM call with automatic fallback and rate-limit retry.
    model=None → uses smart model (Groq 70B) for SQL/analysis, fast model for routing.
    On rate limit: waits 15s and retries once, then falls back to next model.
    """
    if model is None:
        model = settings.llm_fast_model if task == "routing" else settings.llm_smart_model

    # Build fallback chain with multiple FREE providers:
    # Order: retry → deepseek (best SQL, ~free) → mistral → gemini → cohere
    # This ensures we always have a working model even if some hit rate limits
    models_to_try = [model]
    is_large_model = "70b" in model or "versatile" in model or "pro" in model
    if not is_large_model and settings.llm_fallback_model != model:
        models_to_try.append(settings.llm_fallback_model)  # only add 8B fallback for routing tasks
    if settings.deepseek_api_key and "deepseek" not in model:
        models_to_try.append("deepseek/deepseek-coder")  # Best for SQL, very cheap
    if settings.mistral_api_key and "mistral" not in model:
        models_to_try.append("mistral/mistral-large-latest")  # Good quality, free tier
    if settings.gemini_api_key and "gemini" not in model and "gemini/gemini-1.5-flash" not in models_to_try:
        models_to_try.append("gemini/gemini-1.5-flash")  # Free, 1M context
    if settings.cohere_api_key and "cohere" not in model and "command" not in model:
        models_to_try.append("cohere/command-r-plus-08-2024")  # Free tier available
    last_error = None

    for m in models_to_try:
        # Retry once on rate limit with backoff
        for attempt in range(2):
            try:
                t0 = time.perf_counter()
                kwargs: dict = {
                    "model": m,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                }
                api_key = _get_key(m)
                if api_key:
                    kwargs["api_key"] = api_key

                resp = await litellm.acompletion(**kwargs)
                latency_ms = int((time.perf_counter() - t0) * 1000)
                usage = resp.usage

                log.info("llm.call", model=m, task=task, latency_ms=latency_ms,
                         tokens=getattr(usage, "total_tokens", 0))

                return LLMResponse(
                    content=resp.choices[0].message.content or "",
                    model=m,
                    input_tokens=getattr(usage, "prompt_tokens", 0),
                    output_tokens=getattr(usage, "completion_tokens", 0),
                    latency_ms=latency_ms,
                )
            except Exception as exc:
                last_error = exc
                err_str = str(exc).lower()
                if "rate_limit" in err_str or "rate limit" in err_str or "429" in err_str:
                    if attempt == 0:
                        wait = 15  # wait 15s on first rate limit hit
                        log.warning("llm.rate_limited", model=m, wait_seconds=wait)
                        await asyncio.sleep(wait)
                        continue  # retry same model
                log.warning("llm.failed", model=m, attempt=attempt, error=str(exc)[:100])
                break  # try next model

    raise RuntimeError(f"All LLM models failed. Last: {last_error}")
