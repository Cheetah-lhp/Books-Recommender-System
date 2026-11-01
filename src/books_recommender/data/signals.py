from __future__ import annotations

from typing import Any


def interaction_strength(
    rating: int | float | None,
    is_read: bool | int,
    is_reviewed: bool | int,
    signal_config: dict[str, Any],
) -> float | None:
    numeric_rating = int(rating or 0)
    if numeric_rating in {int(value) for value in signal_config["excluded_ratings"]}:
        return None
    bonus = float(signal_config["rating_bonus"].get(str(numeric_rating), 0.0))
    return (
        float(signal_config["base"])
        + float(signal_config["read"]) * int(bool(is_read))
        + float(signal_config["reviewed"]) * int(bool(is_reviewed))
        + bonus
    )


def normalize_component_scores(scores: dict[str, float]) -> dict[str, float]:
    if not scores:
        return {}
    minimum = min(scores.values())
    maximum = max(scores.values())
    if maximum == minimum:
        return {key: 1.0 for key in scores}
    return {key: (value - minimum) / (maximum - minimum) for key, value in scores.items()}


def blend_scores(
    als: float = 0.0,
    content: float = 0.0,
    popularity: float = 0.0,
    *,
    als_weight: float = 0.70,
    content_weight: float = 0.25,
    popularity_weight: float = 0.05,
) -> float:
    return als * als_weight + content * content_weight + popularity * popularity_weight
