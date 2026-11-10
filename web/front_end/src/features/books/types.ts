/**
 * Dinh nghia kieu du lieu cho Book va Category
 */

export type Book = {
  id: string;
  title: string;
  author_name: string;
  description: string | null;
  cover_url: string | null;
  isbn: string | null;
  published_year: number | null;
  pages: number | null;
  language: string;
  rating: number;
  ratings_count: number;
  trending_rank: number | null;
  publisher?: string | null;
  tags?: string[] | null;
  price?: number | null;
  goodreads_id?: number | null;
};

export type BookPage = {
  books: Book[];
  total: number;
  page: number;
  limit: number;
  pages: number;
};

export type Category = {
  id: string;
  name: string;
  slug: string;
  icon: string;
  sort_order: number;
};

