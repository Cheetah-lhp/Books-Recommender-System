export type SampleReview = {
  review_id: string;
  user_id: number;
  rating: number;
  review_text: string | null;
  date_added: string | null;
};

export type UserReview = {
  id: string;
  rating: number;
  body: string | null;
  created_at: string;
  user_id: string;
  profiles: { full_name: string; avatar_url: string | null } | null;
};

