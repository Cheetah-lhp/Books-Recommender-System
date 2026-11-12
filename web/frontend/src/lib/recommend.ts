import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useServerFn } from "@tanstack/react-start";
import { toast } from "sonner";

import { authFetch } from "@/lib/auth-api";
import type { Book } from "@/lib/data";
import { EMPTY_PROFILE, type RecommendationProfile } from "@/lib/preferences";
import { getForYou, getWhyThisBook } from "@/lib/recommend.functions";

export type RecommendedBook = Book & { why: string };
export type RecommendationSection = { key: string; title: string; books: RecommendedBook[] };

export function useRecommendationProfile(userId: string | null) {
  return useQuery({
    queryKey: ["recommendation-profile", userId],
    enabled: Boolean(userId),
    queryFn: async (): Promise<RecommendationProfile | null> => {
      const res = await authFetch("/api/users/me/recommendation-profile");
      if (!res.ok) return null;
      const data = await res.json();
      return { ...EMPTY_PROFILE, ...data, user_id: userId! } as RecommendationProfile;
    },
  });
}

export function useSaveRecommendationProfile(userId: string | null) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (patch: Partial<Omit<RecommendationProfile, "user_id">>) => {
      if (!userId) throw new Error("You need an account to save preferences.");
      const res = await authFetch("/api/users/me/recommendation-profile", {
        method: "PUT",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          genres: patch.genres ?? [],
          themes: patch.themes ?? [],
          reading_mood: patch.reading_mood ?? null,
          reading_frequency: patch.reading_frequency ?? null,
          preferred_book_length: patch.preferred_book_length ?? null,
          favorite_books: patch.favorite_books ?? [],
        }),
      });
      if (!res.ok) throw new Error("Could not save preferences");
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["recommendation-profile", userId] });
      void qc.invalidateQueries({ queryKey: ["for-you"] });
    },
  });
}

export function useForYou(userId: string | null) {
  const fetchForYou = useServerFn(getForYou);
  return useQuery({
    queryKey: ["for-you", userId],
    enabled: Boolean(userId),
    queryFn: async (): Promise<{ sections: RecommendationSection[]; hasProfile: boolean }> => {
      return (await fetchForYou({ data: undefined })) as {
        sections: RecommendationSection[];
        hasProfile: boolean;
      };
    },
  });
}

export function useWhyThisBook(userId: string | null, bookId: string) {
  const ask = useServerFn(getWhyThisBook);
  return useQuery({
    queryKey: ["why-book", userId, bookId],
    enabled: Boolean(userId && bookId),
    queryFn: async (): Promise<string | null> => {
      const res = (await ask({ data: { bookId } })) as { why: string | null };
      return res.why;
    },
  });
}

export function useRecommendationFeedback(userId: string | null) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (input: { bookId: string; feedback: "good" | "not_for_me"; reason?: string }) => {
      if (!userId) throw new Error("Sign in to send feedback.");
      const res = await authFetch("/api/users/me/recommendation-feedback", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ book_id: input.bookId, feedback: input.feedback }),
      });
      if (!res.ok) throw new Error("Could not save feedback");
    },
    onSuccess: () => {
      toast.success("Thanks — your recommendations will improve.");
      void qc.invalidateQueries({ queryKey: ["for-you"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });
}

export function useNotInterested(userId: string | null) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (bookId: string) => {
      if (!userId) throw new Error("Sign in to hide books.");
      const res = await authFetch("/api/users/me/recommendation-feedback", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ book_id: bookId, feedback: "not_for_me" }),
      });
      if (!res.ok) throw new Error("Could not hide book");
    },
    onSuccess: () => {
      toast.success("Hidden from your recommendations.");
      void qc.invalidateQueries({ queryKey: ["for-you"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });
}
