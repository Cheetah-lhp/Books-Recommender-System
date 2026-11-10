export type CommunityPost = {
  id: string;
  body: string;
  tags: string[];
  kind: string;
  created_at: string;
  user_id: string;
  book_id: string | null;
  profiles: { full_name: string; avatar_url: string | null } | null;
  books: { id: string; title: string; cover_url: string | null } | null;
  post_likes: { user_id: string }[];
  post_comments: {
    id: string;
    body: string;
    created_at: string;
    user_id: string;
    profiles: { full_name: string; avatar_url: string | null } | null;
  }[];
};

