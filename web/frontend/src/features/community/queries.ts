import { queryOptions } from "@tanstack/react-query";
import type { CommunityPost } from "./types";

const POSTS_KEY = "brs_community_posts";

export function loadLocalPosts(): CommunityPost[] {
  try {
    return JSON.parse(localStorage.getItem(POSTS_KEY) || "[]") as CommunityPost[];
  } catch {
    return [];
  }
}

export function saveLocalPosts(posts: CommunityPost[]) {
  localStorage.setItem(POSTS_KEY, JSON.stringify(posts));
}

export const postsQuery = queryOptions({
  queryKey: ["community", "posts"],
  queryFn: async (): Promise<CommunityPost[]> => loadLocalPosts(),
});
