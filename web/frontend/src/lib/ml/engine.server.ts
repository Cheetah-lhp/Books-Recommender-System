/**
 * Legacy ML helpers for AI chat. Discover recommendations are scored only by
 * the FastAPI hybrid model service (ALS + content + popularity) — not here.
 */

import { categorySearchTerms } from "@/lib/categories";
import { THEME_TAGS } from "@/lib/preferences";

import { fetchCatalog, type CatalogBook } from "./catalog.server";
import { callModel } from "./models.server";
import type { ParsedQuery } from "./query.server";

export type Signals = {
  genres: string[];
  themes: string[];
  mood: string | null;
  frequency: string | null;
  length: string | null;
  favoriteBookIds: string[];
  shelves: { book_id: string; status: string }[];
  ratings: { book_id: string; rating: number; body: string | null }[];
  positiveBookIds: string[];
  hidden: string[];
  dislikedBookIds: string[];
  likedBookIds: string[];
};

export const EMPTY_SIGNALS: Signals = {
  genres: [],
  themes: [],
  mood: null,
  frequency: null,
  length: null,
  favoriteBookIds: [],
  shelves: [],
  ratings: [],
  positiveBookIds: [],
  hidden: [],
  dislikedBookIds: [],
  likedBookIds: [],
};

export type Recommendation = { book: CatalogBook; score: number; why: string };
export type Section = { key: string; title: string; books: Recommendation[] };

/** Prefer FastAPI `/api/recommendations/sections` for Discover; this stub stays empty. */
export async function buildSections(_userId: string | null, _signals: Signals): Promise<Section[]> {
  return [];
}

/**
 * Chat intent search: optional hybrid model retrieve, otherwise simple keyword
 * overlap against the local catalog (no heuristic recommender scoring).
 */
export async function searchByIntent(parsed: ParsedQuery, signals: Signals, limit = 8): Promise<Recommendation[]> {
  const remote = await callModel<{
    books?: { id: string; score?: number; reason?: string }[];
    id_namespace?: string;
  }>("recommender", {
    userId: null,
    preferences: { genres: parsed.genres.length ? parsed.genres : signals.genres, favorite_books: [] },
    history: signals.shelves,
    ratings: signals.ratings.map((r) => ({ book_id: r.book_id, rating: r.rating })),
    feedback: { liked: signals.likedBookIds, disliked: signals.dislikedBookIds, hidden: signals.hidden },
    candidates: [],
    limit,
  });

  const catalog = await fetchCatalog();
  if (!catalog.length) return [];

  const byId = new Map(catalog.map((b) => [b.id, b]));
  const byGoodreads = new Map(
    catalog.filter((b) => b.goodreads_id != null).map((b) => [String(b.goodreads_id), b]),
  );

  if (remote?.books?.length) {
    const out: Recommendation[] = [];
    for (const item of remote.books) {
      const book =
        byId.get(item.id) ??
        (remote.id_namespace === "web" ? undefined : byGoodreads.get(item.id));
      if (!book) continue;
      out.push({
        book,
        score: item.score ?? 0,
        why: item.reason ?? "Recommended by the hybrid model.",
      });
      if (out.length >= limit) break;
    }
    if (out.length) return out;
  }

  const queryTags = new Set(parsed.themes.flatMap((t) => THEME_TAGS[t] ?? []));
  const excluded = new Set([...signals.hidden, ...signals.dislikedBookIds]);
  const keywords = parsed.keywords.map((k) => k.toLowerCase());

  return catalog
    .filter((b) => !excluded.has(b.id))
    .map((book) => {
      const tags = (book.tags ?? []).map((t) => t.toLowerCase());
      const cats = (book.categories ?? []).map((c) => c.toLowerCase());
      const text = `${book.title} ${book.author_name} ${book.description ?? ""}`.toLowerCase();
      let score = 0;
      const reasons: string[] = [];

      for (const g of parsed.genres) {
        const terms = categorySearchTerms(g);
        if (cats.some((c) => terms.includes(c)) || tags.some((t) => terms.includes(t))) {
          score += 2;
          reasons.push(`matches ${g}`);
        }
      }
      score += tags.filter((t) => queryTags.has(t)).length;
      score += keywords.filter((k) => text.includes(k)).length;
      if (!score) return null;
      return {
        book,
        score,
        why: reasons.length
          ? `Suggested because ${reasons.slice(0, 2).join(", and ")}.`
          : "Matched your search terms.",
      } satisfies Recommendation;
    })
    .filter((x): x is Recommendation => Boolean(x))
    .sort((a, b) => b.score - a.score)
    .slice(0, limit);
}

export async function collectSignals(_userId: string, _accessToken: string): Promise<Signals> {
  // Discover/auth signals live in FastAPI; chat path uses EMPTY_SIGNALS when this returns empty.
  return { ...EMPTY_SIGNALS };
}
