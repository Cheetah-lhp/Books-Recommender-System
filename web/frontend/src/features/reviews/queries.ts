import { queryOptions } from "@tanstack/react-query";
import { apiFetch } from "@/shared/api/client";
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
      try {
        const rows = await apiFetch<
          { id: number; book_id: string; rating: number; body: string | null }[]
        >(`/reviews/book/${encodeURIComponent(bookId)}`);
        return rows.map((r) => ({
          id: String(r.id),
          rating: r.rating,
          body: r.body,
          created_at: new Date().toISOString(),
          user_id: "",
          profiles: { full_name: "Reader", avatar_url: null },
        })) as unknown as UserReview[];
      } catch {
        return [];
      }
    },
  });
}
