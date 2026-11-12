import { queryOptions } from "@tanstack/react-query";
import { apiFetch } from "@/shared/api/client";
import { categorySearchTerms, READORA_CATEGORY_DEFS } from "@/lib/categories";
import type { Book, BookPage, Category } from "@/features/books/types";
import { normalizeBook } from "@/features/books/api";

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
        `/books/search?q=${encodeURIComponent(term.trim())}&limit=30`,
      );
      return data.map(normalizeBook);
    },
  });
}

const fallbackCategories = (): Category[] =>
  READORA_CATEGORY_DEFS.map((c, i) => ({
    id: c.slug,
    name: c.name,
    slug: c.slug,
    icon: c.icon,
    sort_order: i,
  }));

export const categoriesQuery = queryOptions({
  queryKey: ["categories"],
  queryFn: async (): Promise<Category[]> => {
    try {
      const rows = await apiFetch<{ name: string; count: number }[]>("/categories");
      if (!rows?.length) return fallbackCategories();
      return rows.map((r, i) => ({
        id: r.name,
        name: r.name,
        slug: r.name.toLowerCase().replace(/\s+/g, "-"),
        icon: "book",
        sort_order: i,
      }));
    } catch {
      return fallbackCategories();
    }
  },
  initialData: fallbackCategories,
  staleTime: 10 * 60 * 1000,
});
