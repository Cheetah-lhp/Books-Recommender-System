import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useServerFn } from "@tanstack/react-start";
import { toast } from "sonner";

import { supabase } from "@/integrations/supabase/client";
import type { Book } from "@/lib/data";
import { EMPTY_PROFILE, type RecommendationProfile } from "@/lib/preferences";
import { getForYou, getWhyThisBook } from "@/lib/recommend.functions";

export type RecommendedBook = Book & { why: string };
export type RecommendationSection = { key: string; title: string; books: RecommendedBook[] };

/** The user's saved recommendation profile (onboarding answers). */
export function useRecommendationProfile(userId: string | null) {
  return useQuery({
    queryKey: ["recommendation-profile", userId],
    enabled: Boolean(userId),
    queryFn: async (): Promise<RecommendationProfile | null> => {
      const { data, error } = await supabase
        .from("recommendation_profiles")
        .select("*")
        .eq("user_id", userId!)
        .maybeSingle();
      if (error) throw error;
      if (!data) return null;
      const row = data as unknown as Partial<RecommendationProfile>;
      return { ...EMPTY_PROFILE, ...row, user_id: userId! } as RecommendationProfile;
    },
  });
}

export function useSaveRecommendationProfile(userId: string | null) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (patch: Partial<Omit<RecommendationProfile, "user_id">>) => {
      if (!userId) throw new Error("You need an account to save preferences.");
      const { error } = await supabase
        .from("recommendation_profiles")
        .upsert({ user_id: userId, ...patch } as never, { onConflict: "user_id" });
      if (error) throw error;
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["recommendation-profile", userId] });
      void qc.invalidateQueries({ queryKey: ["for-you"] });
    },
  });
}

/** Personalized sections from the backend recommendation engine. */
export function useForYou(userId: string | null) {
  const fetchForYou = useServerFn(getForYou);
  return useQuery({
    queryKey: ["for-you", userId],
    enabled: Boolean(userId),
    queryFn: async (): Promise<{ sections: RecommendationSection[]; hasProfile: boolean }> => {
      const res = (await fetchForYou({ data: undefined })) as unknown as {
        sections: RecommendationSection[];
        hasProfile: boolean;
      };
      return res;
    },
  });
}

export function useWhyThisBook(userId: string | null, bookId: string) {
  const ask = useServerFn(getWhyThisBook);
  return useQuery({
    queryKey: ["why-book", userId, bookId],
    enabled: Boolean(userId && bookId),
    queryFn: async (): Promise<string | null> => {
      const res = (await ask({ data: { bookId } })) as unknown as { why: string | null };
      return res.why;
    },
  });
}

export function useRecommendationFeedback(userId: string | null) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (input: { bookId: string; feedback: "good" | "not_for_me"; reason?: string }) => {
      if (!userId) throw new Error("Sign in to send feedback.");
      const { error } = await supabase.from("recommendation_feedback").upsert(
        {
          user_id: userId,
          book_id: input.bookId,
          feedback: input.feedback,
          reason: input.reason ?? null,
        } as never,
        { onConflict: "user_id,book_id" },
      );
      if (error) throw error;
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
      const { error } = await supabase
        .from("not_interested_books")
        .upsert({ user_id: userId, book_id: bookId } as never, { onConflict: "user_id,book_id" });
      if (error) throw error;
    },
    onSuccess: () => {
      toast.success("Hidden from your recommendations.");
      void qc.invalidateQueries({ queryKey: ["for-you"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });
}
