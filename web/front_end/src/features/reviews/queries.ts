import { queryOptions } from "@tanstack/react-query";
import { apiFetch } from "@/shared/api/client";
import { supabase } from "@/integrations/supabase/client";
import type { SampleReview, UserReview } from "./types";

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

export function reviewsQuery(bookId: string) {
  return queryOptions({
    queryKey: ["reviews", bookId],
    queryFn: async (): Promise<UserReview[]> => {
      const { data, error } = await supabase
        .from("reviews")
        .select("id, rating, body, created_at, user_id, profiles(full_name, avatar_url)")
        .eq("book_id", bookId)
        .order("created_at", { ascending: false });
      if (error) throw error;
      return (data ?? []) as unknown as UserReview[];
    },
  });
}

