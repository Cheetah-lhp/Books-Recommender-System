export type UserBook = {
  id: string;
  status: string;
  progress: number;
  book_id: string;
};

export type AdminStats = {
  users: number;
  books: number;
  reviews: number;
  recent: {
    id: string;
    full_name: string;
    avatar_url: string | null;
    created_at: string;
  }[];
};

