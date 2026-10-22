import { createServerFn } from "@tanstack/react-start";
import { getRequestHeader } from "@tanstack/react-start/server";
import { z } from "zod";

import { requireSupabaseAuth } from "@/integrations/supabase/auth-middleware";

/**
 * Backend API for the recommendation experience. The frontend never talks to
 * an ML model directly — it calls these server functions, which orchestrate
 * the recommendation engine and the three ML services.
 */

function bearer(): string {
  return (getRequestHeader("authorization") ?? "").replace("Bearer ", "");
}

export const getForYou = createServerFn({ method: "POST" })
  .middleware([requireSupabaseAuth])
  .handler(async ({ context }) => {
    const { collectSignals, buildSections } = await import("@/lib/ml/engine.server");
    const signals = await collectSignals(context.userId, bearer());
    const sections = await buildSections(context.userId, signals);
    return {
      sections: sections.map((s) => ({
        key: s.key,
        title: s.title,
        books: s.books.map((b) => ({ ...b.book, why: b.why })),
      })),
      hasProfile: signals.genres.length > 0 || signals.themes.length > 0,
    };
  });

export const getWhyThisBook = createServerFn({ method: "POST" })
  .middleware([requireSupabaseAuth])
  .inputValidator((data: unknown) => z.object({ bookId: z.string().uuid() }).parse(data))
  .handler(async ({ data, context }) => {
    const { collectSignals, scoreBook } = await import("@/lib/ml/engine.server");
    const { fetchCatalog } = await import("@/lib/ml/catalog.server");
    const [signals, catalog] = await Promise.all([collectSignals(context.userId, bearer()), fetchCatalog()]);
    const book = catalog.find((b) => b.id === data.bookId);
    if (!book) return { why: null as string | null };
    const hasSignals = signals.genres.length + signals.themes.length + signals.positiveBookIds.length > 0;
    if (!hasSignals) return { why: null as string | null };
    return { why: scoreBook(book, signals, catalog).why };
  });

const SearchInput = z.object({ query: z.string().min(2).max(300) });

/** Natural-language search: model 3 parses the request, the engine ranks books. */
export const naturalSearch = createServerFn({ method: "POST" })
  .inputValidator((data: unknown) => SearchInput.parse(data))
  .handler(async ({ data }) => {
    const { parseQuery } = await import("@/lib/ml/query.server");
    const { searchByIntent, EMPTY_SIGNALS } = await import("@/lib/ml/engine.server");
    const parsed = await parseQuery(data.query);
    const isNatural =
      parsed.genres.length > 0 || parsed.themes.length > 0 || parsed.length !== null || Boolean(parsed.similarTo);
    const empty: { interpreted: null; books: never[] } = { interpreted: null, books: [] };
    if (!isNatural) return empty;
    const results = await searchByIntent(parsed, EMPTY_SIGNALS, 12);
    return {
      interpreted: {
        genres: parsed.genres,
        themes: parsed.themes,
        length: parsed.length,
        similarTo: parsed.similarTo,
      },
      books: results.map((r) => ({ ...r.book, why: r.why })),
    };
  });

export const getMlStatus = createServerFn({ method: "GET" }).handler(async () => {
  const { modelStatus } = await import("@/lib/ml/models.server");
  return { models: modelStatus() };
});
