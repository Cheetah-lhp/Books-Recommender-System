"""HTTP client for the hybrid model service (ALS + content + popularity)."""

from __future__ import annotations

import logging
from typing import Any, Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


def recommend_from_model(payload: dict[str, Any]) -> Optional[dict[str, Any]]:
    """Call POST /recommend on the model service.

    Returns the parsed JSON body, or None when the service is unreachable/errors.
    Callers must not fall back to heuristic scoring.
    """
    base = (settings.ML_RECOMMENDER_URL or "").rstrip("/")
    if not base:
        logger.warning("ML_RECOMMENDER_URL is empty; recommendations unavailable")
        return None

    headers = {"content-type": "application/json"}
    if settings.ML_API_KEY:
        headers["authorization"] = f"Bearer {settings.ML_API_KEY}"

    timeout = httpx.Timeout(settings.ML_RECOMMEND_TIMEOUT_SECONDS, connect=2.0)
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(f"{base}/recommend", json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict):
                return None
            return data
    except (httpx.HTTPError, ValueError, TypeError) as error:
        logger.warning("Hybrid recommender unavailable: %s", error)
        return None
