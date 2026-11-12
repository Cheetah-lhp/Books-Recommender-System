import { queryOptions } from "@tanstack/react-query";
import { authFetch } from "@/lib/auth-api";
import { apiFetch } from "@/shared/api/client";
import type { UserBook, AdminStats } from "./types";

const PREFS_KEY = "brs_user_preferences";

export function userBooksQuery(userId: string | null) {
  return queryOptions({
    queryKey: ["user-books", userId],
    enabled: Boolean(userId),
    queryFn: async (): Promise<UserBook[]> => {
      const res = await authFetch("/api/library/me");
      if (!res.ok) return [];
      const rows = (await res.json()) as { id: number; book_id: string; status: string }[];
      return rows.map((r) => ({
        id: String(r.id),
        status: r.status,
        progress: 0,
        book_id: String(r.book_id),
      })) as UserBook[];
    },
  });
}

export function preferencesQuery(userId: string | null) {
  return queryOptions({
    queryKey: ["preferences", userId],
    enabled: Boolean(userId),
    queryFn: async () => {
      try {
        const raw = localStorage.getItem(`${PREFS_KEY}:${userId}`);
        return raw
          ? JSON.parse(raw)
          : { user_id: userId, push_notifications: true, email_updates: false };
      } catch {
        return { user_id: userId, push_notifications: true, email_updates: false };
      }
    },
  });
}

export function saveLocalPreferences(
  userId: string,
  patch: { push_notifications?: boolean; email_updates?: boolean },
) {
  const key = `${PREFS_KEY}:${userId}`;
  const current = (() => {
    try {
      return JSON.parse(localStorage.getItem(key) || "{}");
    } catch {
      return {};
    }
  })();
  const next = { ...current, user_id: userId, ...patch };
  localStorage.setItem(key, JSON.stringify(next));
  return next;
}

export const adminStatsQuery = queryOptions({
  queryKey: ["admin", "stats"],
  queryFn: async (): Promise<AdminStats> => {
    const booksStats = await apiFetch<{ total_books: number }>("/stats").catch(() => ({
      total_books: 0,
    }));
    return {
      users: 0,
      books: booksStats.total_books,
      reviews: 0,
      recent: [],
    };
  },
});
