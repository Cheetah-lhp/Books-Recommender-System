import { useQuery } from "@tanstack/react-query";

import { authFetch } from "@/lib/auth-api";
import type { Book } from "@/lib/data";

/**
 * Recommendation access layer — FastAPI scorer behind /api/recommendations.
 * Requires a signed-in user (backend returns 401 for anonymous callers).
 */
export function useRecommendations(userId: string | null) {
  return useQuery({
    queryKey: ["recommendations", userId],
    enabled: Boolean(userId),
    queryFn: async (): Promise<Book[]> => {
      const res = await authFetch("/api/recommendations");
      if (!res.ok) return [];
      const json = (await res.json()) as { books: Book[] };
      return json.books ?? [];
    },
  });
}
