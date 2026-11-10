import { queryOptions } from "@tanstack/react-query";
import { supabase } from "@/integrations/supabase/client";
import { apiFetch } from "@/shared/api/client";
import type { UserBook, AdminStats } from "./types";

export function userBooksQuery(userId: string | null) {
  return queryOptions({
    queryKey: ["user-books", userId],
    enabled: Boolean(userId),
    queryFn: async (): Promise<UserBook[]> => {
      const { data, error } = await supabase
        .from("user_books")
        .select("id, status, progress, book_id")
        .eq("user_id", userId!);
      if (error) throw error;
      return (data ?? []) as UserBook[];
    },
  });
}

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
  queryFn: async (): Promise<AdminStats> => {
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
      recent: (recent.data ?? []) as {
        id: string;
        full_name: string;
        avatar_url: string | null;
        created_at: string;
      }[],
    };
  },
});

