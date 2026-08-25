"""Phase 8: API Credit, Cost & Usage Tracking.

Calculates estimated cost in USD for model token usage and records UsageMetric
into the database using the existing model.
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import UsageMetric

logger = logging.getLogger("ai_interviewer.ai.cost_tracker")

# Pricing per 1,000,000 tokens in USD (rates as of standard provider tiers)
MODEL_PRICING: Dict[str, Dict[str, float]] = {
    # Gemini models
    "gemini-1.5-flash": {"input_per_million": 0.075, "output_per_million": 0.30},
    "gemini-1.5-pro": {"input_per_million": 1.25, "output_per_million": 5.00},
    "text-embedding-004": {"input_per_million": 0.025, "output_per_million": 0.0},
    
    # OpenAI models
    "gpt-4o-mini": {"input_per_million": 0.15, "output_per_million": 0.60},
    "gpt-4o": {"input_per_million": 2.50, "output_per_million": 10.00},
    "text-embedding-3-small": {"input_per_million": 0.02, "output_per_million": 0.0},
    "text-embedding-3-large": {"input_per_million": 0.13, "output_per_million": 0.0},
    
    # Mock / Default
    "mock": {"input_per_million": 0.0, "output_per_million": 0.0},
}


def calculate_estimated_cost(
    model_name: str,
    input_tokens: int = 0,
    output_tokens: int = 0
) -> float:
    """Calculate estimated USD cost based on token counts and model pricing."""
    model_clean = model_name.lower().strip()
    pricing = None
    for key, p in MODEL_PRICING.items():
        if key in model_clean:
            pricing = p
            break
            
    if not pricing:
        # Fallback default low-cost tier
        pricing = {"input_per_million": 0.15, "output_per_million": 0.60}

    input_cost = (input_tokens / 1_000_000.0) * pricing["input_per_million"]
    output_cost = (output_tokens / 1_000_000.0) * pricing["output_per_million"]
    return round(input_cost + output_cost, 7)


async def record_usage_metric(
    db: Optional[AsyncSession],
    provider: str,
    model_name: str,
    call_type: str,  # llm, embedding, stt, tts
    input_tokens: int = 0,
    output_tokens: int = 0,
    latency_ms: int = 0,
    audio_duration_sec: float = 0.0,
    interview_id: Optional[int] = None,
    user_id: Optional[int] = None
) -> Optional[UsageMetric]:
    """
    Safely persist an AI operation record into UsageMetric without interrupting main flow.
    """
    if db is None:
        return None

    cost_usd = calculate_estimated_cost(model_name, input_tokens, output_tokens)

    try:
        metric = UsageMetric(
            interview_id=interview_id,
            user_id=user_id,
            provider=provider,
            model_name=model_name,
            call_type=call_type,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            audio_duration_sec=audio_duration_sec,
            latency_ms=latency_ms,
            estimated_cost_usd=cost_usd,
            timestamp=datetime.utcnow()
        )
        db.add(metric)
        await db.commit()
        await db.refresh(metric)
        return metric
    except Exception as exc:
        await db.rollback()
        logger.warning(f"Failed to persist AI UsageMetric: {exc}", exc_info=True)
        return None
