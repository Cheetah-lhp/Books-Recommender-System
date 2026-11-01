from books_recommender.data.signals import (
    blend_scores,
    interaction_strength,
    normalize_component_scores,
)

SIGNALS = {
    "base": 1.0,
    "read": 2.0,
    "reviewed": 2.0,
    "rating_bonus": {"3": 1.0, "4": 2.0, "5": 3.0},
    "excluded_ratings": [1, 2],
}


def test_interaction_strength_and_exclusions():
    assert interaction_strength(1, True, True, SIGNALS) is None
    assert interaction_strength(0, False, False, SIGNALS) == 1.0
    assert interaction_strength(5, True, True, SIGNALS) == 8.0


def test_normalize_component_scores():
    assert normalize_component_scores({"a": 2.0, "b": 4.0}) == {"a": 0.0, "b": 1.0}
    assert normalize_component_scores({"a": 2.0, "b": 2.0}) == {"a": 1.0, "b": 1.0}


def test_blend_scores():
    assert blend_scores(1.0, 1.0, 1.0) == 1.0
