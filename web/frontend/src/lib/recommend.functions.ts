import { createServerFn } from "@tanstack/react-start";
import { getRequestHeader } from "@tanstack/react-start/server";
import { z } from "zod";

import { requireLocalAuth } from "@/lib/local-auth-middleware";

const API_BASE =
  process.env["API_BASE"] || process.env["VITE_API_URL"] || "http://127.0.0.1:8000";

function authHeaders(): HeadersInit {
  const auth = getRequestHeader("authorization");
  return auth ? { Authorization: auth, "content-type": "application/json" } : { "content-type": "application/json" };
}

export const getForYou = createServerFn({ method: "POST" })
  .middleware([requireLocalAuth])
  .handler(async () => {
    const res = await fetch(`${API_BASE}/api/recommendations/sections`, {
      headers: authHeaders(),
      signal: AbortSignal.timeout(15_000),
    });
    if (!res.ok) return { sections: [], hasProfile: false };
    const json = (await res.json()) as {
      sections?: { key: string; title: string; books: Array<Record<string, unknown> & { why?: string }> }[];
    };
    const sections = (json.sections ?? []).map((s) => ({
      key: s.key,
      title: s.title,
      books: (s.books ?? []).map((b) => {
        const book = (b as { book?: Record<string, unknown> }).book ?? b;
        return { ...book, why: (b as { why?: string }).why ?? "" };
      }),
    }));
    const hasProfile = sections.some((s) => s.key === "genre" || s.books.length > 0);
    return { sections, hasProfile };
  });

export const getWhyThisBook = createServerFn({ method: "POST" })
  .middleware([requireLocalAuth])
  .inputValidator((data: unknown) => z.object({ bookId: z.string().min(1) }).parse(data))
  .handler(async ({ data }) => {
    const res = await fetch(`${API_BASE}/api/recommendations/sections`, {
      headers: authHeaders(),
      signal: AbortSignal.timeout(15_000),
    });
    if (!res.ok) return { why: null as string | null };
    const json = (await res.json()) as {
      sections?: { books: Array<{ book?: { id?: string }; id?: string; why?: string }> }[];
    };
    for (const section of json.sections ?? []) {
      for (const item of section.books ?? []) {
        const id = String(item.book?.id ?? item.id ?? "");
        if (id === data.bookId) return { why: item.why ?? null };
      }
    }
    return { why: null as string | null };
  });

const SearchInput = z.object({ query: z.string().min(2).max(300) });

export const naturalSearch = createServerFn({ method: "POST" })
  .inputValidator((data: unknown) => SearchInput.parse(data))
  .handler(async ({ data }) => {
    const res = await fetch(
      `${API_BASE}/api/books/search?q=${encodeURIComponent(data.query)}&limit=12`,
      { signal: AbortSignal.timeout(10_000) },
    );
    if (!res.ok) return { interpreted: null, books: [] as never[] };
    const books = (await res.json()) as Record<string, unknown>[];
    return {
      interpreted: { genres: [] as string[], themes: [] as string[], length: null, similarTo: null },
      books: books.map((b) => ({ ...b, why: "Matched your search." })),
    };
  });

export const getMlStatus = createServerFn({ method: "GET" }).handler(async () => {
  return { models: { recommender: "fastapi", sentiment: "off", query: "off" } };
});
