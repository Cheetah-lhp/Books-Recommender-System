import { useQuery } from "@tanstack/react-query";

import type { Book } from "@/lib/data";

/**
 * Recommendation access layer. The UI never depends on a static list:
 * it calls the /api/recommendations endpoint, which either proxies an external
 * ML recommendation API (when RECOMMENDER_API_URL is configured) or falls back
 * to a genre/rating/history based algorithm.
 */
export function useRecommendations(userId: string | null) {
  return useQuery({
    queryKey: ["recommendations", userId],
    queryFn: async (): Promise<Book[]> => {
      const url = userId ? `/api/recommendations?userId=${userId}` : "/api/recommendations";
      const res = await fetch(url);
      if (!res.ok) return [];
      const json = (await res.json()) as { books: Book[] };
      return json.books ?? [];
    },
  });
}
