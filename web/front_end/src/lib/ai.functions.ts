import { createServerFn } from "@tanstack/react-start";
import { getRequestHeader } from "@tanstack/react-start/server";
import { z } from "zod";

import { READORA_CATEGORIES } from "@/lib/categories";

const Input = z.object({
  messages: z.array(z.object({ role: z.enum(["user", "assistant"]), content: z.string().min(1) })).min(1),
  language: z.enum(["en", "ar"]).default("en"),
});

/**
 * READORA AI assistant.
 *
 * AI chat -> query-understanding model -> recommendation engine -> real books
 * from the READORA database -> chat response (text + book cards).
 */
export const askReadoraAi = createServerFn({ method: "POST" })
  .inputValidator((data: unknown) => Input.parse(data))
  .handler(async ({ data }) => {
    const key = process.env["LOVABLE_API_KEY"];
    if (!key) return { ok: false as const, error: "AI is not configured." };

    const { parseQuery } = await import("@/lib/ml/query.server");
    const { searchByIntent, collectSignals, EMPTY_SIGNALS } = await import("@/lib/ml/engine.server");

    const lastUser = [...data.messages].reverse().find((m) => m.role === "user")?.content ?? "";

    // Personalize with the caller's own signals when they are signed in.
    let signals = EMPTY_SIGNALS;
    const token = (getRequestHeader("authorization") ?? "").replace("Bearer ", "");
    if (token.split(".").length === 3) {
      try {
        const payload = JSON.parse(atob(token.split(".")[1]!.replace(/-/g, "+").replace(/_/g, "/"))) as {
          sub?: string;
        };
        if (payload.sub) signals = await collectSignals(payload.sub, token);
      } catch {
        // anonymous chat
      }
    }

    const parsed = await parseQuery(lastUser);
    const results = await searchByIntent(parsed, signals, 6);
    const books = results.map((r) => ({ ...r.book, why: r.why }));

    const catalogBlock = books.length
      ? books
          .map(
            (b) =>
              `- ${b.title} by ${b.author_name} (${Number(b.rating).toFixed(1)}★, ${b.pages ?? "?"} pages, ${(b.tags ?? []).slice(0, 4).join(", ")})`,
          )
          .join("\n")
      : "";

    const system = `You are the READORA AI reading assistant. You recommend books that exist in the READORA library.
${
  catalogBlock
    ? `The READORA recommendation engine selected these real books for this request — talk about THESE and nothing else, and never invent titles:\n${catalogBlock}`
    : "No engine match was found; answer helpfully and invite the reader to describe genre, mood or length."
}
When you name a category, always use one of the official READORA categories: ${READORA_CATEGORIES.join(", ")}. Never use retired labels such as Sci-Fi, Self-Help, Business, Philosophy, Science, plain Fantasy, Mystery, History or Biography.
Be warm and brief (max 110 words). Mention 2-4 of the books by title with one line each on why it fits.
Answer in ${data.language === "ar" ? "Arabic" : "English"}.`;

    const response = await fetch("https://ai.gateway.lovable.dev/v1/chat/completions", {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${key}` },
      body: JSON.stringify({
        model: "google/gemini-3.7-flash",
        messages: [{ role: "system", content: system }, ...data.messages],
      }),
    });

    if (response.status === 429) return { ok: false as const, error: "Too many requests, please try again shortly." };
    if (response.status === 402) return { ok: false as const, error: "AI credits are exhausted for this workspace." };
    if (!response.ok) return { ok: false as const, error: `AI request failed (${response.status}).` };

    const json = (await response.json()) as { choices?: { message?: { content?: string } }[] };
    return { ok: true as const, content: json.choices?.[0]?.message?.content ?? "", books };
  });
