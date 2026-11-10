import { queryOptions } from "@tanstack/react-query";
import { supabase } from "@/integrations/supabase/client";
import type { CommunityPost } from "./types";

export const postsQuery = queryOptions({
  queryKey: ["community", "posts"],
  queryFn: async (): Promise<CommunityPost[]> => {
    const { data, error } = await supabase
      .from("community_posts")
      .select(
        `id, body, tags, kind, created_at, user_id, book_id,
         profiles(full_name, avatar_url),
         post_likes(user_id),
         post_comments(id, body, created_at, user_id, profiles(full_name, avatar_url))`,
      )
      .order("created_at", { ascending: false });
    if (error) throw error;
    return (data ?? []) as unknown as CommunityPost[];
  },
});

