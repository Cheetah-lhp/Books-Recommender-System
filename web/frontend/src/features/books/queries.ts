import { queryOptions } from "@tanstack/react-query";
import { apiFetch } from "@/shared/api/client";
import { categorySearchTerms } from "@/lib/categories";
import type { Book } from "./types";
import { normalizeBook } from "./api";

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

export function bookQuery(id: string) {
  return queryOptions({
    queryKey: ["book", id],
    queryFn: async () => {
      const book = await apiFetch<Record<string, unknown>>(`/books/${id}`);
      const categories = ((book["tags"] as string[]) ?? []).map((tag) => ({
        name: tag,
        slug: tag.toLowerCase().replace(/\s+/g, "-"),
      }));
      return { book: normalizeBook(book), categories };
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

