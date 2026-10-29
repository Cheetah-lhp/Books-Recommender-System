/**
 * BRS Data Layer
 * - Books: gọi Python API (Aiven PostgreSQL) qua /api/*
 * - User data (reviews, wishlist, cart, orders...): Supabase trực tiếp
 */
import { queryOptions } from "@tanstack/react-query";
import { categorySearchTerms } from "@/lib/categories";
import { supabase } from "@/integrations/supabase/client";

// Base URL của Python API — SSR cần absolute URL, Client dùng proxy /api hoặc trực tiếp
const BACKEND_URL =
  (typeof process !== "undefined" ? process.env["VITE_API_URL"] : undefined) ||
  "http://127.0.0.1:8000";

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
  staleTime: 5 * 60 * 1000,
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

export type BookPage = {
  books: Book[];
  total: number;
  page: number;
  limit: number;
  pages: number;
};

export function booksPageQuery(page: number, limit = 24) {
  return queryOptions({
    queryKey: ["books", "page", page, limit],
    queryFn: async (): Promise<BookPage> => {
      const params = new URLSearchParams({ page: String(page), limit: String(limit), sort: "rating" });
      const result = await apiFetch<{
        data: Record<string, unknown>[];
        total: number;
        page: number;
        limit: number;
        pages: number;
      }>(`/books?${params.toString()}`);
      return {
        books: (result.data ?? []).map(normalizeBook),
        total: result.total,
        page: result.page,
        limit: result.limit,
        pages: result.pages,
      };
    },
    staleTime: 5 * 60 * 1000,
  });
}

export function bookQuery(id: string) {
  return queryOptions({
    queryKey: ["book", id],
    queryFn: async () => {
      const book = await apiFetch<Record<string, unknown>>(`/books/${id}`);
      // Categories lấy từ tags của sách
      const categories = ((book["tags"] as string[]) ?? []).map((tag) => ({
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
      const params = new URLSearchParams({ limit: "40", sort: "rating" });
      for (const term of categorySearchTerms(slug)) params.append("category", term);
      const data = await apiFetch<{ data: Record<string, unknown>[] }>(`/books?${params.toString()}`);
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

export function similarBooksQuery(bookId: string, preferredTags: string[] = []) {
  return queryOptions({
    queryKey: ["books", "similar", bookId, preferredTags],
    queryFn: async (): Promise<Book[]> => {
      try {
        const params = new URLSearchParams({ limit: "8" });
        const normalizedPreferences = Array.from(
          new Set(preferredTags.flatMap((tag) => categorySearchTerms(tag))),
        ).slice(0, 20);
        for (const tag of normalizedPreferences) params.append("preferred_tags", tag);
        const data = await apiFetch<Record<string, unknown>[]>(
          `/books/${encodeURIComponent(bookId)}/similar?${params.toString()}`,
        );
        return data.map(normalizeBook);
      } catch {
        return [];
      }
    },
  });
}

export type SampleReview = {
  review_id: string;
  user_id: number;
  rating: number;
  review_text: string | null;
  date_added: string | null;
};

export function sampleReviewsQuery(bookId: string) {
  return queryOptions({
    queryKey: ["sample-reviews", bookId],
    queryFn: async (): Promise<SampleReview[]> => {
      try {
        return await apiFetch<SampleReview[]>(`/books/${encodeURIComponent(bookId)}/sample-reviews?limit=12`);
      } catch {
        return [];
      }
    },
    staleTime: 10 * 60 * 1000,
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
