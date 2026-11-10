import type { Book } from "./types";

export function normalizeBook(raw: Record<string, unknown>): Book {
  // Chuan hoa du lieu tho tu API ve dang Book
  return {
    id: String(raw["id"]),
    title: String(raw["title"] ?? ""),
    author_name: String(raw["author_name"] ?? ""),
    description: (raw["description"] as string) ?? null,
    cover_url: (raw["cover_url"] as string) ?? null,
    isbn: (raw["isbn"] as string) ?? null,
    published_year: (raw["published_year"] as number) ?? null,
    pages: (raw["pages"] as number) ?? null,
    language: String(raw["language"] ?? "en"),
    rating: Number(raw["rating"] ?? 0),
    ratings_count: Number(raw["ratings_count"] ?? 0),
    trending_rank: (raw["trending_rank"] as number) ?? null,
    publisher: (raw["publisher"] as string) ?? null,
    tags: (raw["tags"] as string[]) ?? [],
    price: Number(raw["price"] ?? 0),
    goodreads_id: (raw["goodreads_id"] as number) ?? null,
  };
}

