/**
 * Read-only catalog access cho server-side recommendation engine.
 * Đọc từ BRS Python API (Aiven PostgreSQL) thay vì Supabase trực tiếp.
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
  "http://localhost:8000";

/** Gọi Supabase REST API với access token (dùng cho user-scoped data). */
export async function rest<T = unknown>(path: string, accessToken?: string): Promise<T[]> {
  const url = process.env["SUPABASE_URL"];
  const key = process.env["SUPABASE_PUBLISHABLE_KEY"] || process.env["SUPABASE_ANON_KEY"];
  if (!url || !key) return [];
  const headers: Record<string, string> = { apikey: key };
  if (accessToken) headers["Authorization"] = `Bearer ${accessToken}`;
  const res = await fetch(`${url}/rest/v1/${path}`, { headers });
  if (!res.ok) return [];
  return (await res.json()) as T[];
}

let cache: { at: number; books: CatalogBook[] } | null = null;

/** Lấy toàn bộ catalog từ Python API (Aiven). Cache 60 giây. */
export async function fetchCatalog(): Promise<CatalogBook[]> {
  if (cache && Date.now() - cache.at < 60_000) return cache.books;

  try {
    // Lấy tối đa 500 sách có rating cao để dùng cho recommendation engine
    const res = await fetch(
      `${API_BASE}/api/books?limit=500&sort=rating`,
      { signal: AbortSignal.timeout(10_000) }
    );
    if (!res.ok) return cache?.books ?? [];

    const json = (await res.json()) as { data: CatalogBook[] };
    const books = (json.data ?? []).map((b) => ({
      ...b,
      id: String(b.id),
      tags: b.tags ?? [],
      categories: (b.tags ?? []).slice(0, 5), // tags làm categories fallback
    }));

    cache = { at: Date.now(), books };
    return books;
  } catch {
    return cache?.books ?? [];
  }
}
