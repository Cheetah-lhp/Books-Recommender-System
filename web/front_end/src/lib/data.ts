/**
 * BRS Data Layer
 * - Books: gọi Python API (Aiven PostgreSQL) qua /api/*
 * - User data (reviews, wishlist, cart, orders...): Supabase trực tiếp
 */
import { queryOptions } from "@tanstack/react-query";
import { supabase } from "@/integrations/supabase/client";

// Base URL của Python API — SSR cần absolute URL, Client dùng proxy /api hoặc trực tiếp
const BACKEND_URL =
  (typeof process !== "undefined" ? process.env.VITE_API_URL : undefined) ||
  "https://01a0c9d9-f877-73c4-a505-60067dcbdc6c-8000.eur-1.aiven.app";

function getApiUrl(path: string): string {
  const clean = path.startsWith("/") ? path : `/${path}`;
  const fullPath = clean.startsWith("/api") ? clean : `/api${clean}`;
  if (typeof window === "undefined") {
    // SSR environment (Node.js) requires an absolute URL
    return `${BACKEND_URL}${fullPath}`;
  }
  // Client environment: can use relative path with Vite proxy or direct backend URL
  return fullPath;
}

// ─── Types ───────────────────────────────────────────────────────────────────

export type Book = {
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
  publisher?: string | null;
  tags?: string[] | null;
  price?: number | null;
  goodreads_id?: number | null;
};

export type Category = { id: string; name: string; slug: string; icon: string; sort_order: number };

// ─── Helper gọi Python API ────────────────────────────────────────────────────

async function apiFetch<T>(path: string): Promise<T> {
  const url = getApiUrl(path);
  try {
    const res = await fetch(url);
    if (!res.ok) throw new Error(`API error ${res.status}: ${path}`);
    return (await res.json()) as Promise<T>;
  } catch (err) {
    console.error(`[BRS Data] apiFetch error for ${url}:`, err);
    throw err;
  }
}

function normalizeBook(raw: Record<string, unknown>): Book {
  return {
    id: String(raw["id"]),
    title: String(raw["title"] ?? ""),
    author_name: String(raw["author_name"] ?? ""),
    description: (raw["description"] as string) ?? null,
    cover_url: (raw["cover_url"] as string) ?? null,
    isbn: (raw["isbn"] as string) ?? null,
    published_year: (raw["published_year"] as number) ?? null,
    pages: (raw["pages"] as number) ?? null,
    language: String(raw["language"] ?? "en"),
    rating: Number(raw["rating"] ?? 0),
    ratings_count: Number(raw["ratings_count"] ?? 0),
    trending_rank: (raw["trending_rank"] as number) ?? null,
    publisher: (raw["publisher"] as string) ?? null,
    tags: (raw["tags"] as string[]) ?? [],
    price: Number(raw["price"] ?? 0),
    goodreads_id: (raw["goodreads_id"] as number) ?? null,
  };
}

// ─── Book Queries (Python API / Aiven) ───────────────────────────────────────

export const trendingBooksQuery = queryOptions({
  queryKey: ["books", "trending"],
  queryFn: async (): Promise<Book[]> => {
    try {
      const data = await apiFetch<Record<string, unknown>[]>("/books/trending?limit=10");
      return data.map(normalizeBook);
    } catch (err) {
      console.warn("[trendingBooksQuery] Fallback to empty list:", err);
      return [];
    }
  },
  staleTime: 2 * 60 * 1000,
});

export const topRatedQuery = queryOptions({
  queryKey: ["books", "top-rated"],
  queryFn: async (): Promise<Book[]> => {
    try {
      const data = await apiFetch<Record<string, unknown>[]>("/books/top-rated?limit=20");
      return data.map(normalizeBook);
    } catch (err) {
      console.warn("[topRatedQuery] Fallback to empty list:", err);
      return [];
    }
  },
  staleTime: 5 * 60 * 1000,
});

export const allBooksQuery = queryOptions({
  queryKey: ["books", "all"],
  queryFn: async (): Promise<Book[]> => {
    try {
      const data = await apiFetch<{ data: Record<string, unknown>[] }>("/books?limit=100&sort=rating");
      return (data.data ?? []).map(normalizeBook);
    } catch (err) {
      console.warn("[allBooksQuery] Fallback to empty list:", err);
      return [];
    }
  },
  staleTime: 5 * 60 * 1000,
});

export function bookQuery(id: string) {
  return queryOptions({
    queryKey: ["book", id],
    queryFn: async () => {
      const book = await apiFetch<Record<string, unknown>>(`/books/${id}`);
      // Categories lấy từ tags của sách
      const categories = ((book["tags"] as string[]) ?? []).slice(0, 5).map((tag) => ({
        name: tag,
        slug: tag.toLowerCase().replace(/\s+/g, "-"),
      }));
      return { book: normalizeBook(book), categories };
    },
  });
}

export function booksByCategoryQuery(slug: string) {
  return queryOptions({
    queryKey: ["books", "category", slug],
    queryFn: async (): Promise<Book[]> => {
      const data = await apiFetch<{ data: Record<string, unknown>[] }>(
        `/books?category=${encodeURIComponent(slug)}&limit=40&sort=rating`
      );
      return (data.data ?? []).map(normalizeBook);
    },
    staleTime: 3 * 60 * 1000,
  });
}

export function searchQuery(term: string) {
  return queryOptions({
    queryKey: ["search", term],
    enabled: term.trim().length > 1,
    queryFn: async (): Promise<Book[]> => {
      const data = await apiFetch<Record<string, unknown>[]>(
        `/books/search?q=${encodeURIComponent(term.trim())}&limit=30`
      );
      return data.map(normalizeBook);
    },
  });
}

export function similarBooksQuery(bookId: string) {
  return queryOptions({
    queryKey: ["books", "similar", bookId],
    queryFn: async (): Promise<Book[]> => {
      // Lấy thông tin sách hiện tại rồi tìm sách rating cao có cùng tags
      try {
        const base = await apiFetch<Record<string, unknown>>(`/books/${bookId}`);
        const tags = (base["tags"] as string[]) ?? [];
        const firstTag = tags[0];
        const query = firstTag
          ? `/books?category=${encodeURIComponent(firstTag)}&limit=8&sort=rating`
          : `/books/top-rated?limit=8`;
        const data = await apiFetch<Record<string, unknown>[] | { data: Record<string, unknown>[] }>(query);
        const raw = Array.isArray(data) ? data : (data as { data: Record<string, unknown>[] }).data ?? [];
        return raw.filter((b) => String(b["id"]) !== bookId).slice(0, 4).map(normalizeBook);
      } catch {
        return [];
      }
    },
  });
}

// ─── Categories (vẫn từ Supabase) ────────────────────────────────────────────

export const categoriesQuery = queryOptions({
  queryKey: ["categories"],
  queryFn: async (): Promise<Category[]> => {
    try {
      const { data, error } = await supabase.from("categories").select("*").order("sort_order");
      if (error) {
        console.warn("[categoriesQuery] Supabase error:", error.message);
        return [];
      }
      return (data ?? []) as Category[];
    } catch (err) {
      console.warn("[categoriesQuery] Fallback to empty list:", err);
      return [];
    }
  },
  staleTime: 10 * 60 * 1000,
});

// ─── User queries (Supabase) ─────────────────────────────────────────────────

export function reviewsQuery(bookId: string) {
  return queryOptions({
    queryKey: ["reviews", bookId],
    queryFn: async () => {
      const { data, error } = await supabase
        .from("reviews")
        .select("id, rating, body, created_at, user_id, profiles(full_name, avatar_url)")
        .eq("book_id", bookId)
        .order("created_at", { ascending: false });
      if (error) throw error;
      return (data ?? []) as unknown as {
        id: string;
        rating: number;
        body: string | null;
        created_at: string;
        user_id: string;
        profiles: { full_name: string; avatar_url: string | null } | null;
      }[];
    },
  });
}

export function userBooksQuery(userId: string | null) {
  return queryOptions({
    queryKey: ["user-books", userId],
    enabled: Boolean(userId),
    queryFn: async () => {
      const { data, error } = await supabase
        .from("user_books")
        .select("id, status, progress, book_id")
        .eq("user_id", userId!);
      if (error) throw error;
      return (data ?? []) as { id: string; status: string; progress: number; book_id: string }[];
    },
  });
}

export const postsQuery = queryOptions({
  queryKey: ["community", "posts"],
  queryFn: async () => {
    const { data, error } = await supabase
      .from("community_posts")
      .select(
        `id, body, tags, kind, created_at, user_id, book_id,
         profiles(full_name, avatar_url),
         post_likes(user_id),
         post_comments(id, body, created_at, user_id, profiles(full_name, avatar_url))`,
      )
      .order("created_at", { ascending: false });
    if (error) throw error;
    return (data ?? []) as unknown as CommunityPost[];
  },
});

export type CommunityPost = {
  id: string;
  body: string;
  tags: string[];
  kind: string;
  created_at: string;
  user_id: string;
  book_id: string | null;
  profiles: { full_name: string; avatar_url: string | null } | null;
  books: { id: string; title: string; cover_url: string | null } | null;
  post_likes: { user_id: string }[];
  post_comments: {
    id: string;
    body: string;
    created_at: string;
    user_id: string;
    profiles: { full_name: string; avatar_url: string | null } | null;
  }[];
};

export function preferencesQuery(userId: string | null) {
  return queryOptions({
    queryKey: ["preferences", userId],
    enabled: Boolean(userId),
    queryFn: async () => {
      const { data, error } = await supabase
        .from("user_preferences")
        .select("*")
        .eq("user_id", userId!)
        .maybeSingle();
      if (error) throw error;
      return data;
    },
  });
}

export const adminStatsQuery = queryOptions({
  queryKey: ["admin", "stats"],
  queryFn: async () => {
    const [users, reviews, recent, booksStats] = await Promise.all([
      supabase.from("profiles").select("id", { count: "exact", head: true }),
      supabase.from("reviews").select("id", { count: "exact", head: true }),
      supabase
        .from("profiles")
        .select("id, full_name, avatar_url, created_at")
        .order("created_at", { ascending: false })
        .limit(6),
      apiFetch<{ total_books: number }>("/stats").catch(() => ({ total_books: 0 })),
    ]);
    return {
      users: users.count ?? 0,
      books: booksStats.total_books,
      reviews: reviews.count ?? 0,
      recent: (recent.data ?? []) as { id: string; full_name: string; avatar_url: string | null; created_at: string }[],
    };
  },
});
