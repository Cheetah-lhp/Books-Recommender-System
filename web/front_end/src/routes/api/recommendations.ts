import { createFileRoute } from "@tanstack/react-router";

import { READORA_CATEGORY_DEFS, categorySearchTerms, normalizeGenres } from "@/lib/categories";

type Book = Record<string, unknown> & { id: string; rating: number };

async function rest(path: string) {
  const url = process.env["SUPABASE_URL"];
  const key = process.env["SUPABASE_PUBLISHABLE_KEY"];
  if (!url || !key) return [];
  const res = await fetch(`${url}/rest/v1/${path}`, { headers: { apikey: key } });
  if (!res.ok) return [];
  return (await res.json()) as unknown[];
}

type Answers = {
  ageGroup?: string;
  genres?: string[];
  readingMood?: string;
  favoriteBook?: string;
  location?: string;
  preferredLanguage?: string;
  readingFrequency?: string;
  preferredBookLength?: string;
  userId?: string | null;
};

const MOOD_TAGS: Record<string, string[]> = {
  "Something inspiring": ["inspiring", "motivation", "self-help", "growth", "habits"],
  "A page-turner": ["thriller", "mystery", "adventure", "suspense", "fast-paced"],
  "Deep & intellectual": ["philosophy", "classic", "literary", "dystopia", "science"],
  "Light & fun": ["humor", "romance", "feel-good", "contemporary"],
  "Emotional journey": ["romance", "drama", "memoir", "coming-of-age", "family"],
  "Eye-opening facts": ["history", "science", "nonfiction", "psychology", "economics"],
};

const LANG_CODES: Record<string, string[]> = {
  Arabic: ["ar", "arabic"],
  English: ["en", "english"],
  French: ["fr", "french"],
  German: ["de", "german"],
  Spanish: ["es", "spanish"],
};

function lengthScore(pages: number | null, pref?: string) {
  if (!pref || pref === "Any" || !pages) return 0;
  if (pref.startsWith("Short")) return pages < 200 ? 3 : -1;
  if (pref.startsWith("Medium")) return pages >= 200 && pages <= 400 ? 3 : -1;
  if (pref.startsWith("Long")) return pages > 400 ? 3 : -1;
  return 0;
}

async function questionnaireRecommendations(answers: Answers) {
  const books = (await rest(
    "books?select=id,title,author_name,description,cover_url,isbn,published_year,pages,language,rating,ratings_count,trending_rank,publisher,tags&limit=200",
  )) as (Book & { title: string; pages: number | null; language: string; tags?: string[] | null })[];

  // Official Readora categories -> raw dataset genre terms (mapping layer).
  const selectedCategories = normalizeGenres(answers.genres ?? []);
  const genres = [...new Set(selectedCategories.flatMap((c) => categorySearchTerms(c)))];
  const categorySlugs = selectedCategories
    .map((c) => READORA_CATEGORY_DEFS.find((d) => d.name === c)?.slug)
    .filter(Boolean) as string[];
  const moodTags = MOOD_TAGS[answers.readingMood ?? ""] ?? [];
  const langCodes = LANG_CODES[answers.preferredLanguage ?? ""] ?? [];
  const favorite = (answers.favoriteBook ?? "").trim().toLowerCase();

  // Genre affinity via categories.
  const genreBookIds = new Set<string>();
  if (genres.length) {
    const cats = (await rest("categories?select=id,name,slug")) as { id: string; name: string; slug: string }[];
    const matched = cats.filter((c) => categorySlugs.includes(c.slug.toLowerCase()));
    if (matched.length) {
      const rows = (await rest(
        `book_categories?select=book_id&category_id=in.(${matched.map((m) => m.id).join(",")})`,
      )) as { book_id: string }[];
      for (const r of rows) genreBookIds.add(r.book_id);
    }
  }

  const favoriteBook = favorite ? books.find((b) => b.title.toLowerCase().includes(favorite)) : undefined;

  const scored = books
    .filter((b) => !favoriteBook || b.id !== favoriteBook.id)
    .map((b) => {
      const tags = ((b.tags ?? []) as string[]).map((t) => t.toLowerCase());
      let score = Number(b.rating) || 0;
      if (genreBookIds.has(b.id)) score += 5;
      score += tags.filter((t) => genres.some((g) => t.includes(g) || g.includes(t))).length * 2;
      score += tags.filter((t) => moodTags.some((m) => t.includes(m) || m.includes(t))).length * 1.5;
      if (langCodes.length && langCodes.includes((b.language ?? "").toLowerCase())) score += 2;
      score += lengthScore(b.pages, answers.preferredBookLength);
      if (favoriteBook) {
        if ((b as { author_name?: string }).author_name === (favoriteBook as { author_name?: string }).author_name)
          score += 3;

        const favTags = ((favoriteBook.tags ?? []) as string[]).map((t) => t.toLowerCase());
        score += tags.filter((t) => favTags.includes(t)).length * 1.5;
      }
      return { book: b, score };
    })
    .sort((a, b) => b.score - a.score)
    .slice(0, 12)
    .map((s) => s.book);

  return scored;
}

export const Route = createFileRoute("/api/recommendations")({
  server: {
    handlers: {
      POST: async ({ request }) => {
        const answers = (await request.json()) as Answers;
        const external = process.env["RECOMMENDER_API_URL"];
        if (external) {
          try {
            const res = await fetch(external, {
              method: "POST",
              headers: { "content-type": "application/json" },
              body: JSON.stringify(answers),
            });
            if (res.ok) {
              const json = (await res.json()) as { books?: unknown[] };
              if (json.books?.length) return Response.json({ books: json.books, source: "ml" });
            }
          } catch {
            // fall through to the built-in algorithm
          }
        }
        return Response.json({ books: await questionnaireRecommendations(answers), source: "questionnaire" });
      },
      GET: async ({ request }) => {

        const userId = new URL(request.url).searchParams.get("userId");

        // 1. External ML recommender, when configured.
        const external = process.env["RECOMMENDER_API_URL"];
        if (external) {
          try {
            const res = await fetch(`${external}?userId=${userId ?? ""}`);
            if (res.ok) {
              const json = (await res.json()) as { books?: unknown[] };
              if (json.books?.length) return Response.json({ books: json.books, source: "ml" });
            }
          } catch {
            // fall through to the built-in algorithm
          }
        }

        // 2. Fallback: genre affinity from the user's library, weighted by rating.
        const books = (await rest(
          "books?select=id,title,author_name,description,cover_url,isbn,published_year,pages,language,rating,ratings_count,trending_rank&order=rating.desc&limit=100",
        )) as Book[];

        let preferredIds = new Set<string>();
        let ownedIds = new Set<string>();
        if (userId) {
          const owned = (await rest(`user_books?select=book_id&user_id=eq.${userId}`)) as { book_id: string }[];
          ownedIds = new Set(owned.map((o) => o.book_id));
          if (ownedIds.size) {
            const cats = (await rest(
              `book_categories?select=category_id&book_id=in.(${[...ownedIds].join(",")})`,
            )) as { category_id: string }[];
            const catIds = [...new Set(cats.map((c) => c.category_id))];
            if (catIds.length) {
              const related = (await rest(
                `book_categories?select=book_id&category_id=in.(${catIds.join(",")})`,
              )) as { book_id: string }[];
              preferredIds = new Set(related.map((r) => r.book_id));
            }
          }
        }

        const scored = books
          .filter((b) => !ownedIds.has(b.id))
          .map((b) => ({ book: b, score: Number(b.rating) + (preferredIds.has(b.id) ? 2 : 0) }))
          .sort((a, b) => b.score - a.score)
          .slice(0, 12)
          .map((s) => s.book);

        return Response.json({ books: scored, source: "fallback" });
      },
    },
  },
});
