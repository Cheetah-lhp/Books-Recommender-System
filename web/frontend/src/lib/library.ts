import { authFetch } from "@/lib/auth-api";

export type ShelfStatus = "want" | "reading" | "read";

export const SHELF_STATUSES: ShelfStatus[] = ["want", "reading", "read"];

export const SHELF_LABELS: Record<ShelfStatus, string> = {
  want: "Want to Read",
  reading: "Currently Reading",
  read: "Read",
};

/** Minimum ratings before personalized Discover sections unlock. */
export const RATING_THRESHOLD = 5;

export function normalizeShelfStatus(status: string | null | undefined): ShelfStatus | null {
  if (!status) return null;
  if (status === "want_to_read" || status === "want") return "want";
  if (status === "reading" || status === "currently_reading") return "reading";
  if (status === "read") return "read";
  return null;
}

export async function setShelf(bookId: string, status: ShelfStatus): Promise<void> {
  const res = await authFetch("/api/library/me", {
    method: "PUT",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ book_id: bookId, status }),
  });
  if (!res.ok) throw new Error("Could not update shelf");
}

export async function rateBook(bookId: string, rating: number, body?: string | null): Promise<void> {
  const res = await authFetch("/api/reviews", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ book_id: bookId, rating, body: body ?? null }),
  });
  if (!res.ok) throw new Error("Could not save rating");
}
