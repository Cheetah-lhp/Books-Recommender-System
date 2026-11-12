/**
 * Read-only catalog access for server-side helpers.
 * Uses FastAPI only — no Supabase.
 */

export type CatalogBook = {
  id: string;
  title: string;
  author_name: string;
  description: string | null;
  cover_url: string | null;
  isbn: string | null;
  published_year: number | null;
  pages: number | null;
  language: string;
  rating: number;
  ratings_count: number;
  trending_rank: number | null;
  publisher: string | null;
  tags: string[] | null;
  categories: string[];
  price?: number;
};

const API_BASE =
  process.env["VITE_API_BASE"] ||
  process.env["API_BASE"] ||
  process.env["VITE_API_URL"] ||
  "http://localhost:8000";

/** @deprecated Kept for call-site compatibility; always returns []. */
export async function rest<T = unknown>(_path: string, _accessToken?: string): Promise<T[]> {
  return [];
}

let cache: { at: number; books: CatalogBook[] } | null = null;

export async function fetchCatalog(): Promise<CatalogBook[]> {
  if (cache && Date.now() - cache.at < 60_000) return cache.books;

  try {
    const pages = await Promise.all(
      [1, 2, 3, 4, 5].map(async (page) => {
        const res = await fetch(`${API_BASE}/api/books?page=${page}&limit=100&sort=rating`, {
          signal: AbortSignal.timeout(10_000),
        });
        if (!res.ok) return [] as CatalogBook[];
        const json = (await res.json()) as { data?: CatalogBook[] };
        return json.data ?? [];
      }),
    );

    const seen = new Set<string>();
    const books: CatalogBook[] = [];
    for (const row of pages.flat()) {
      const id = String(row.id);
      if (seen.has(id)) continue;
      seen.add(id);
      books.push({
        ...row,
        id,
        tags: row.tags ?? [],
        categories: (row.tags ?? []).slice(0, 5),
      });
    }
    cache = { at: Date.now(), books };
    return books;
  } catch {
    return cache?.books ?? [];
  }
}
