from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow.dataset as ds
from scipy import sparse


def _normalize(values: np.ndarray, available: np.ndarray) -> np.ndarray:
    result = np.zeros(len(values), dtype=float)
    if available.any():
        selected = values[available]
        low, high = selected.min(), selected.max()
        result[available] = (selected - low) / (high - low) if high > low else 1.0
    return result


def _terms(value: str) -> set[str]:
    return set(re.findall(r"\w+", value.lower().replace("non-fiction", "nonfiction"))) - {"and"}


class DemoRecommender:
    """Hybrid retriever using trained ALS factors, sparse TF-IDF, and popularity.

    Readora user IDs identify application accounts, not Goodreads training users.
    Live positive book signals are folded into the trained item-factor space.
    When ``candidates`` is empty, the model retrieves from its own item universe.
    """

    def __init__(self, bundle: Path):
        self.manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
        if self.manifest.get("book_id_namespace") != "book_id_csv":
            raise ValueError("Unsupported serving ID namespace; re-export the model.")
        self.items = ds.dataset(bundle / "items", format="parquet").to_table().to_pylist()
        self.items.sort(key=lambda row: row["item_idx"])
        self.positions = {row["item_idx"]: i for i, row in enumerate(self.items)}
        self.aliases = {
            str(row["source_book_id"]): self.positions[row["item_idx"]]
            for row in ds.dataset(bundle / "aliases", format="parquet").to_table().to_pylist()
            if row["item_idx"] in self.positions
        }
        self.position_to_source: dict[int, str] = {}
        for source_id, position in self.aliases.items():
            self.position_to_source.setdefault(position, source_id)
        for position, item in enumerate(self.items):
            canonical = item.get("canonical_book_id")
            if canonical is not None:
                self.position_to_source[position] = str(canonical)
        indices, values, offsets = [], [], [0]
        for item in self.items:
            vector = item.pop("features")
            vector_indices = vector["indices"]
            if vector_indices is None:  # Spark DenseVector
                vector_indices = list(range(len(vector["values"])))
            indices.extend(vector_indices)
            values.extend(vector["values"])
            offsets.append(len(indices))
        self.features = sparse.csr_matrix(
            (values, indices, offsets),
            shape=(len(self.items), int(self.manifest["num_features"])),
        )
        rank = int(self.manifest["als"]["rank"])
        self.factors = np.zeros((len(self.items), rank), dtype=float)
        self.has_factor = np.zeros(len(self.items), dtype=bool)
        for row in ds.dataset(bundle / "als_items", format="parquet").to_table().to_pylist():
            position = self.positions.get(row["id"])
            if position is not None:
                self.factors[position] = row["features"]
                self.has_factor[position] = True
        self.gram = self.factors.T @ self.factors
        self.popularity = np.array([row["popularity"] for row in self.items], dtype=float)
        hybrid = self.manifest["hybrid"]
        self.pop_candidate_count = int(hybrid.get("popularity_candidates", 100))
        self.content_candidate_count = int(self.manifest.get("content_candidates", 300))
        self.als_candidate_count = int(self.manifest.get("als_candidates", 300))

    def rerank(self, payload: dict[str, Any], id_map: dict[str, str]) -> dict[str, Any]:
        """Backward-compatible entrypoint; retrieves when candidates are absent."""
        return self.recommend(payload, id_map)

    def recommend(self, payload: dict[str, Any], id_map: dict[str, str], limit: int = 50) -> dict[str, Any]:
        def position(web_id: Any) -> int | None:
            return self.aliases.get(id_map.get(str(web_id), ""))

        feedback = payload.get("feedback") or {}
        preferences = payload.get("preferences") or {}
        ratings = payload.get("ratings") or []
        history = payload.get("history") or []
        excluded_ids = [*feedback.get("disliked", []), *feedback.get("hidden", [])]
        excluded_ids += [r["book_id"] for r in ratings if 0 < r["rating"] <= 2]
        excluded_ids += [r["book_id"] for r in history if r.get("status") == "read"]
        excluded = {p for value in excluded_ids if (p := position(value)) is not None}
        seeds: dict[int, float] = {}

        def seed(web_id: Any, weight: float) -> None:
            p = position(web_id)
            if p is not None:
                seeds[p] = max(seeds.get(p, 0.0), weight)

        for value in [*preferences.get("favorite_books", []), *feedback.get("liked", [])]:
            seed(value, 8.0)
        for row in ratings:
            if row["rating"] >= 3:
                seed(row["book_id"], float(row["rating"]) + 3.0)
        for row in history:
            seed(row["book_id"], 3.0 if row.get("status") in {"read", "reading"} else 1.0)

        blocked_signals = {
            p
            for value in [
                *feedback.get("disliked", []),
                *feedback.get("hidden", []),
                *[r["book_id"] for r in ratings if 0 < r["rating"] <= 2],
            ]
            if (p := position(value)) is not None
        }
        seeds = {p: w for p, w in seeds.items() if p not in blocked_signals}
        excluded.update(seeds)
        seeds = dict(
            sorted(seeds.items(), key=lambda pair: (-pair[1], pair[0]))[
                : int(self.manifest["max_history"])
            ]
        )

        requested = payload.get("candidates") or []
        mapped_candidates = sum(position(value) is not None for value in requested)
        candidates: list[tuple[str, int, str]] = []
        unique_works: set[int] = set()

        for value in requested:
            web_id = str(value)
            p = position(web_id)
            if p is not None and p not in excluded and p not in unique_works:
                candidates.append((web_id, p, "web"))
                unique_works.add(p)

        content_profile: np.ndarray | None = None
        user_als: np.ndarray | None = None
        if seeds:
            seed_positions = np.array(list(seeds))
            weights = np.array(list(seeds.values()))
            profile = np.asarray(self.features[seed_positions].T @ weights).ravel()
            norm = np.linalg.norm(profile)
            if norm:
                content_profile = profile / norm
            factor_mask = self.has_factor[seed_positions]
            if factor_mask.any():
                factors = self.factors[seed_positions[factor_mask]]
                confidence_extra = float(self.manifest["als"]["alpha"]) * weights[factor_mask]
                reg = float(self.manifest["als"]["reg_param"]) * len(factors)
                matrix = self.gram + (factors.T * confidence_extra) @ factors
                matrix += np.eye(matrix.shape[0]) * max(reg, 1e-6)
                rhs = factors.T @ (1.0 + confidence_extra)
                user_als = np.linalg.solve(matrix, rhs)

        if not candidates:
            pool: set[int] = set()
            pop_order = np.argsort(-self.popularity)
            for p in pop_order:
                if int(p) in excluded:
                    continue
                pool.add(int(p))
                if len(pool) >= self.pop_candidate_count:
                    break

            if content_profile is not None:
                content_all = np.asarray(self.features @ content_profile).ravel()
                content_all[list(excluded)] = -np.inf
                for p in np.argsort(-content_all)[: self.content_candidate_count]:
                    if np.isfinite(content_all[p]):
                        pool.add(int(p))

            if user_als is not None:
                als_all = self.factors @ user_als
                als_all = als_all.copy()
                als_all[~self.has_factor] = -np.inf
                als_all[list(excluded)] = -np.inf
                for p in np.argsort(-als_all)[: self.als_candidate_count]:
                    if np.isfinite(als_all[p]):
                        pool.add(int(p))

            if not seeds:
                desired = [_terms(g) for g in preferences.get("genres", [])]
                if desired:
                    genre_scores = np.zeros(len(self.items))
                    for i, item in enumerate(self.items):
                        if i in excluded:
                            continue
                        tags = [_terms(g) for g in item["genres"]]
                        genre_scores[i] = sum(bool(wanted & tag) for wanted in desired for tag in tags)
                    for p in np.argsort(-genre_scores)[: self.content_candidate_count]:
                        if genre_scores[p] > 0:
                            pool.add(int(p))

            for p in sorted(pool):
                source_id = self.position_to_source.get(p)
                if source_id is None:
                    continue
                candidates.append((source_id, p, "book_id_csv"))

        if not candidates:
            return {
                "books": [],
                "run_id": self.manifest["run_id"],
                "mapped_candidates": mapped_candidates,
                "id_namespace": "book_id_csv",
                "mode": "retrieve",
            }

        candidate_positions = np.array([p for _, p, _ in candidates])
        content = np.zeros(len(candidates))
        als = np.zeros(len(candidates))
        has_als = False
        if content_profile is not None:
            content = np.asarray(self.features[candidate_positions] @ content_profile).ravel()
        if user_als is not None:
            als = self.factors[candidate_positions] @ user_als
            has_als = True
        elif not seeds:
            desired = [_terms(g) for g in preferences.get("genres", [])]
            for i, p in enumerate(candidate_positions):
                tags = [_terms(g) for g in self.items[p]["genres"]]
                content[i] = sum(bool(wanted & tag) for wanted in desired for tag in tags)

        options = self.manifest["hybrid"]
        content_norm = _normalize(content, content > 0)
        pop_norm = _normalize(self.popularity[candidate_positions], np.ones(len(candidates), bool))
        if has_als:
            als_norm = _normalize(als, self.has_factor[candidate_positions])
            scores = (
                float(options["als_weight"]) * als_norm
                + float(options["content_weight"]) * content_norm
                + float(options["popularity_weight"]) * pop_norm
            )
        elif (content > 0).any():
            scores = (
                float(options["cold_content_weight"]) * content_norm
                + float(options["cold_popularity_weight"]) * pop_norm
            )
        else:
            scores = pop_norm

        ranked = sorted(range(len(candidates)), key=lambda i: (-scores[i], candidates[i][0]))
        books = []
        namespaces = {ns for _, _, ns in candidates}
        id_namespace = "web" if namespaces == {"web"} else "book_id_csv"
        for i in ranked[: max(1, limit)]:
            reason = (
                "Based on your reading history and trained collaborative/content models."
                if has_als
                else "Based on your favorite books or genres."
                if content[i] > 0
                else "Popular with readers in the training sample."
            )
            books.append(
                {
                    "id": candidates[i][0],
                    "score": float(scores[i]),
                    "reason": reason,
                    "work_id": self.items[candidates[i][1]]["work_id"],
                }
            )
        return {
            "books": books,
            "run_id": self.manifest["run_id"],
            "mapped_candidates": mapped_candidates,
            "id_namespace": id_namespace,
            "mode": "rerank" if requested else "retrieve",
        }
