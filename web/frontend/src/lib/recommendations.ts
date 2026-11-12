import { useQuery } from "@tanstack/react-query";

import { authFetch } from "@/lib/auth-api";
import type { Book } from "@/lib/data";

/**
 * Recommendation access layer — FastAPI scorer behind /api/recommendations
 * (Nginx in prod, Vite proxy / thin TanStack proxy in dev).
 */
export function useRecommendations(userId: string | null) {
  return useQuery({
    queryKey: ["recommendations", userId],
    queryFn: async (): Promise<Book[]> => {
      const url = userId ? `/api/recommendations?userId=${userId}` : "/api/recommendations";
      const res = await authFetch(url);
      if (!res.ok) return [];
      const json = (await res.json()) as { books: Book[] };
      return json.books ?? [];
    },
  });
}
