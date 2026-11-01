import { categorySearchTerms, normalizeGenres } from "@/lib/categories";
import { MOOD_TAGS, THEME_TAGS } from "@/lib/preferences";

import { fetchCatalog, rest, type CatalogBook } from "./catalog.server";
import { callModelWithStatus } from "./models.server";
import { analyzeSentiment } from "./sentiment.server";
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
export type ModelReport = {
  source: "model" | "heuristic";
  status: "used" | "unconfigured" | "unavailable" | "unmapped";
  runId: string | null;
  durationMs: number;
  candidates: number;
  returned: number;
};

/** Collect every available recommendation signal for a user (RLS-scoped read). */
export async function collectSignals(userId: string, accessToken: string): Promise<Signals> {
  const [profiles, shelves, reviews, hidden, feedback] = await Promise.all([
    rest<{
      genres: string[];
      themes: string[];
      reading_mood: string | null;
      reading_frequency: string | null;
      preferred_book_length: string | null;
      favorite_books: string[];
    }>(`recommendation_profiles?select=*&user_id=eq.${userId}`, accessToken),
    rest<{ book_id: string; status: string }>(
      `user_books?select=book_id,status&user_id=eq.${userId}`,
      accessToken,
    ),
    rest<{ book_id: string; rating: number; body: string | null }>(
      `reviews?select=book_id,rating,body&user_id=eq.${userId}`,
      accessToken,
    ),
    rest<{ book_id: string }>(
      `not_interested_books?select=book_id&user_id=eq.${userId}`,
      accessToken,
    ),
    rest<{ book_id: string; feedback: string }>(
      `recommendation_feedback?select=book_id,feedback&user_id=eq.${userId}`,
      accessToken,
    ),
  ]);

  const profile = profiles[0];
  const sentiments = await analyzeSentiment(reviews.map((r) => r.body ?? ""));
  const positiveBookIds = reviews
    .filter((r, i) => r.rating >= 4 || sentiments[i]?.label === "positive")
    .map((r) => r.book_id);

  return {
    genres: normalizeGenres(profile?.genres ?? []),
    themes: profile?.themes ?? [],
    mood: profile?.reading_mood ?? null,
    frequency: profile?.reading_frequency ?? null,
    length: profile?.preferred_book_length ?? null,
    favoriteBookIds: profile?.favorite_books ?? [],
    shelves,
    ratings: reviews,
    positiveBookIds,
    hidden: hidden.map((h) => h.book_id),
    dislikedBookIds: feedback.filter((f) => f.feedback === "not_for_me").map((f) => f.book_id),
    likedBookIds: feedback.filter((f) => f.feedback === "good").map((f) => f.book_id),
  };
}

function lengthBucket(pages: number | null): "short" | "medium" | "long" | null {
  if (!pages) return null;
  if (pages < 250) return "short";
  if (pages <= 450) return "medium";
  return "long";
}

function preferredBucket(pref: string | null): "short" | "medium" | "long" | null {
  if (!pref) return null;
  if (pref.startsWith("Short")) return "short";
  if (pref.startsWith("Medium")) return "medium";
  if (pref.startsWith("Long")) return "long";
  return null;
}

function lc(list: string[] | null | undefined) {
  return (list ?? []).map((v) => v.toLowerCase());
}

/** Score a single book against the user's signals and explain the score. */
export function scoreBook(book: CatalogBook, s: Signals, catalog: CatalogBook[]) {
  const reasons: string[] = [];
  let score = Number(book.rating) || 0;

  const tags = lc(book.tags);
  const cats = lc(book.categories);
  const genres = lc(s.genres);

  // Match official categories against both the book's categories and its raw
  // dataset tags/subgenres through the shared mapping layer.
  const genreHits = s.genres.filter((g) => {
    const terms = categorySearchTerms(g);
    return cats.some((c) => terms.includes(c)) || tags.some((t) => terms.includes(t));
  });
  if (genreHits.length) {
    score += 4 * genreHits.length;
    reasons.push(`you enjoy ${genreHits.slice(0, 2).join(" and ")}`);
  }

  const themeHits = s.themes.filter((t) => (THEME_TAGS[t] ?? []).some((tag) => tags.includes(tag)));
  if (themeHits.length) {
    score += 2 * themeHits.length;
    reasons.push(`you like ${themeHits.slice(0, 2).join(" and ").toLowerCase()} reads`);
  }

  const moodTags = MOOD_TAGS[s.mood ?? ""] ?? [];
  const moodHit = moodTags.some((tag) => tags.includes(tag));
  if (moodHit && s.mood) {
    score += 2;
    reasons.push(`you're looking for ${s.mood.toLowerCase()}`);
  }

  const pref = preferredBucket(s.length);
  const bucket = lengthBucket(book.pages);
  if (pref && bucket) {
    if (pref === bucket) {
      score += 2;
      reasons.push(`it's a ${bucket} read, matching your preference`);
    } else {
      score -= 1.5;
    }
  }

  // Behaviour: books close to titles the reader rated highly or loved.
  const loved = catalog.filter(
    (b) => s.positiveBookIds.includes(b.id) || s.favoriteBookIds.includes(b.id),
  );
  for (const fav of loved) {
    if (fav.id === book.id) continue;
    if (fav.author_name === book.author_name) {
      score += 3;
      reasons.push(`you liked ${fav.title} by the same author`);
      break;
    }
    const overlap = lc(fav.tags).filter((t) => tags.includes(t)).length;
    const catOverlap = lc(fav.categories).filter((c) => cats.includes(c)).length;
    if (overlap + catOverlap >= 2) {
      score += 2 + overlap * 0.5;
      reasons.push(`it's close to ${fav.title}, which you rated highly`);
      break;
    }
  }

  if (s.likedBookIds.length) {
    const likedTags = new Set(
      catalog.filter((b) => s.likedBookIds.includes(b.id)).flatMap((b) => lc(b.tags)),
    );
    const hit = tags.filter((t) => likedTags.has(t)).length;
    if (hit) score += hit;
  }

  if (s.dislikedBookIds.length) {
    const dislikedTags = new Set(
      catalog.filter((b) => s.dislikedBookIds.includes(b.id)).flatMap((b) => lc(b.tags)),
    );
    score -= tags.filter((t) => dislikedTags.has(t)).length * 1.5;
  }

  if (!genres.length && !s.themes.length) {
    score += (book.trending_rank ? 1 : 0) + Math.min(Number(book.ratings_count) / 5000, 2);
  }

  const why = reasons.length
    ? `You may like this because ${reasons.slice(0, 2).join(", and ")}.`
    : `Highly rated in the READORA library (${Number(book.rating).toFixed(1)}★).`;

  return { score, why };
}

function eligible(catalog: CatalogBook[], s: Signals) {
  const read = new Set(s.shelves.filter((x) => x.status === "read").map((x) => x.book_id));
  const lowRated = s.ratings.filter((r) => r.rating > 0 && r.rating <= 2).map((r) => r.book_id);
  const excluded = new Set([
    ...s.hidden,
    ...s.dislikedBookIds,
    ...read,
    ...lowRated,
    ...s.favoriteBookIds,
    ...s.likedBookIds,
  ]);
  return catalog.filter((b) => !excluded.has(b.id));
}

/** ML model 1 — recommender. Re-ranks candidates when the service is connected. */
async function mlRerank(
  userId: string | null,
  s: Signals,
  ranked: Recommendation[],
  reportModel?: (report: ModelReport) => void,
): Promise<Recommendation[]> {
  const candidates = ranked.slice(0, 60).map((r) => r.book.id);
  const call = await callModelWithStatus<{
    books?: { id: string; score?: number; reason?: string; work_id?: string }[];
    run_id?: string;
    mapped_candidates?: number;
  }>("recommender", {
    userId,
    preferences: {
      genres: s.genres,
      themes: s.themes,
      mood: s.mood,
      frequency: s.frequency,
      length: s.length,
      favorite_books: s.favoriteBookIds,
    },
    history: s.shelves,
    ratings: s.ratings.map((r) => ({ book_id: r.book_id, rating: r.rating })),
    feedback: { liked: s.likedBookIds, disliked: s.dislikedBookIds, hidden: s.hidden },
    candidates,
  });
  const remote = call.data;
  if (!Array.isArray(remote?.books) || (!remote.books.length && !remote.mapped_candidates)) {
    reportModel?.({
      source: "heuristic",
      status: call.status === "used" ? "unmapped" : call.status,
      runId: remote?.run_id ?? null,
      durationMs: call.durationMs,
      candidates: candidates.length,
      returned: 0,
    });
    return ranked;
  }

  const byId = new Map(ranked.map((r) => [r.book.id, r]));
  const out: Recommendation[] = [];
  const works = new Set<string>();
  for (const item of remote.books) {
    const match = byId.get(item.id);
    const work = item.work_id ?? item.id;
    if (!match || !candidates.includes(item.id) || works.has(work)) continue;
    out.push({
      ...match,
      score: item.score ?? match.score,
      ...(item.reason ? { why: item.reason } : {}),
    });
    works.add(work);
    byId.delete(item.id);
  }
  // A successful model response has already removed seen/hidden works and
  // duplicate editions. Re-appending its omitted candidates would undo that.
  reportModel?.({
    source: "model",
    status: "used",
    runId: remote.run_id ?? null,
    durationMs: call.durationMs,
    candidates: candidates.length,
    returned: out.length,
  });
  return out;
}

export async function buildSections(
  userId: string | null,
  signals: Signals,
  reportModel?: (report: ModelReport) => void,
): Promise<Section[]> {
  const catalog = await fetchCatalog();
  if (catalog.length === 0) return [];

  const pool = eligible(catalog, signals);
  let ranked: Recommendation[] = pool
    .map((book) => {
      const { score, why } = scoreBook(book, signals, catalog);
      return { book, score, why };
    })
    .sort((a, b) => b.score - a.score);

  ranked = await mlRerank(userId, signals, ranked, reportModel);

  const sections: Section[] = [];
  const take = (list: Recommendation[], n = 6) => list.slice(0, n);

  sections.push({ key: "for-you", title: "Recommended for You", books: take(ranked, 12) });

  const topGenre = signals.genres[0];
  if (topGenre) {
    const inGenre = ranked.filter((r) =>
      r.book.categories
        .concat(r.book.tags ?? [])
        .some((v) => v.toLowerCase().includes(topGenre.toLowerCase())),
    );
    if (inGenre.length)
      sections.push({ key: "genre", title: `Because You Like ${topGenre}`, books: take(inGenre) });
  }

  if (signals.positiveBookIds.length) {
    const ratedIds = new Set(signals.positiveBookIds);
    const basedOnRatings = ranked.filter(
      (r) => /rated highly|same author/.test(r.why) && !ratedIds.has(r.book.id),
    );
    if (basedOnRatings.length)
      sections.push({
        key: "ratings",
        title: "Based on Your Ratings",
        books: take(basedOnRatings),
      });
  }

  const lastRead = signals.shelves.find((x) => x.status === "reading") ?? signals.shelves[0];
  const lastBook = lastRead ? catalog.find((b) => b.id === lastRead.book_id) : undefined;
  if (lastBook) {
    const tags = lc(lastBook.tags);
    const cats = lc(lastBook.categories);
    const similar = ranked
      .filter((r) => r.book.id !== lastBook.id)
      .map((r) => ({
        rec: r,
        overlap:
          lc(r.book.tags).filter((t) => tags.includes(t)).length +
          lc(r.book.categories).filter((c) => cats.includes(c)).length +
          (r.book.author_name === lastBook.author_name ? 2 : 0),
      }))
      .filter((x) => x.overlap > 0)
      .sort((a, b) => b.overlap - a.overlap)
      .map((x) => x.rec);
    if (similar.length)
      sections.push({
        key: "because-read",
        title: `Because You Read ${lastBook.title}`,
        books: take(similar),
      });
  }

  const gems = ranked
    .filter((r) => Number(r.book.rating) >= 4.2 && Number(r.book.ratings_count) < 40000)
    .slice(0, 6);
  if (gems.length) sections.push({ key: "gems", title: "Hidden Gems", books: gems });

  if (signals.genres.length) {
    const trending = ranked
      .filter(
        (r) =>
          r.book.trending_rank !== null &&
          signals.genres.some((g) =>
            r.book.categories
              .concat(r.book.tags ?? [])
              .some((v) => v.toLowerCase().includes(g.toLowerCase())),
          ),
      )
      .slice(0, 6);
    if (trending.length)
      sections.push({
        key: "trending-genres",
        title: "Trending in Your Favorite Genres",
        books: trending,
      });
  }

  return sections.filter((s) => s.books.length > 0);
}

/** Natural-language / chatbot driven search over the catalog. */
export async function searchByIntent(
  parsed: ParsedQuery,
  signals: Signals,
  limit = 8,
): Promise<Recommendation[]> {
  const catalog = await fetchCatalog();
  const queryTags = new Set(parsed.themes.flatMap((t) => THEME_TAGS[t] ?? []));
  const similar = parsed.similarTo
    ? catalog.find((b) => b.title.toLowerCase().includes(parsed.similarTo!.toLowerCase()))
    : undefined;

  const scored = eligible(catalog, signals)
    .filter((b) => !similar || b.id !== similar.id)
    .map((book) => {
      const base = scoreBook(book, signals, catalog);
      const tags = lc(book.tags);
      const cats = lc(book.categories);
      let score = base.score * 0.4;
      const reasons: string[] = [];

      const genreHit = parsed.genres.filter((g) => {
        const terms = categorySearchTerms(g);
        return cats.some((c) => terms.includes(c)) || tags.some((t) => terms.includes(t));
      });
      if (genreHit.length) {
        score += 6 * genreHit.length;
        reasons.push(`it's ${genreHit.join(" / ")}`);
      }
      const tagHit = tags.filter((t) => queryTags.has(t)).length;
      if (tagHit) {
        score += 3 * tagHit;
        reasons.push(`it matches the ${parsed.themes.join(", ").toLowerCase()} mood you asked for`);
      }
      if (parsed.length) {
        const bucket = lengthBucket(book.pages);
        if (bucket === parsed.length) {
          score += 4;
          reasons.push(`it's a ${parsed.length} book`);
        } else if (bucket) score -= 3;
      }
      if (similar) {
        if (similar.author_name === book.author_name) score += 4;
        const overlap =
          lc(similar.tags).filter((t) => tags.includes(t)).length +
          lc(similar.categories).filter((c) => cats.includes(c)).length;
        score += overlap * 2;
        if (overlap) reasons.push(`it shares themes with ${similar.title}`);
      }
      const text = `${book.title} ${book.author_name} ${book.description ?? ""}`.toLowerCase();
      score += parsed.keywords.filter((k) => text.includes(k)).length * 0.75;

      const why = reasons.length
        ? `Suggested because ${reasons.slice(0, 2).join(", and ")}.`
        : base.why;
      return { book, score, why };
    })
    .sort((a, b) => b.score - a.score)
    .slice(0, limit);

  return scored;
}
