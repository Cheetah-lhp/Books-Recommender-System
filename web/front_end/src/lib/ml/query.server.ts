import { READORA_CATEGORY_DEFS, normalizeGenres } from "@/lib/categories";
import { THEME_TAGS, GENRE_OPTIONS, THEME_OPTIONS } from "@/lib/preferences";

import { callModel } from "./models.server";

export type ParsedQuery = {
  text: string;
  genres: string[];
  themes: string[];
  length: "short" | "medium" | "long" | null;
  similarTo: string | null;
  keywords: string[];
};

const LENGTH_HINTS: [RegExp, ParsedQuery["length"]][] = [
  [/\bshort(er)?\b|\bquick\b|\blight read\b/i, "short"],
  [/\bmedium\b|\bmid-?length\b/i, "medium"],
  [/\blong(er)?\b|\bepic\b|\bchunky\b/i, "long"],
];

// Raw dataset genre words map onto the official Readora categories.
const GENRE_ALIASES: Record<string, string> = Object.fromEntries(
  READORA_CATEGORY_DEFS.flatMap((c) => c.tags.map((t) => [t, c.name] as const)),
);

const THEME_ALIASES: Record<string, string> = {
  emotional: "Emotional",
  sad: "Emotional",
  moving: "Emotional",
  funny: "Funny",
  humor: "Funny",
  humour: "Funny",
  dark: "Dark",
  relaxing: "Relaxing",
  cozy: "Relaxing",
  calm: "Relaxing",
  inspiring: "Inspirational",
  inspirational: "Inspirational",
  motivational: "Motivational",
  motivating: "Motivational",
  educational: "Educational",
  learn: "Educational",
  "thought-provoking": "Thought-provoking",
  thoughtful: "Thought-provoking",
  philosophical: "Thought-provoking",
  "fast-paced": "Fast-paced",
  exciting: "Fast-paced",
  gripping: "Fast-paced",
  mysterious: "Mysterious",
};

function heuristicParse(text: string): ParsedQuery {
  const lower = text.toLowerCase();
  const genres = new Set<string>();
  const themes = new Set<string>();

  for (const [alias, genre] of Object.entries(GENRE_ALIASES)) if (lower.includes(alias)) genres.add(genre);
  for (const g of GENRE_OPTIONS) if (lower.includes(g.toLowerCase())) genres.add(g);
  for (const [alias, theme] of Object.entries(THEME_ALIASES)) if (lower.includes(alias)) themes.add(theme);
  for (const th of THEME_OPTIONS) if (lower.includes(th.toLowerCase())) themes.add(th);

  let length: ParsedQuery["length"] = null;
  for (const [re, value] of LENGTH_HINTS) if (re.test(lower)) length = value;

  const similar =
    /(?:similar to|like|loved|enjoyed|read)\s+([^.,?!]{2,60})/i.exec(text)?.[1]?.trim().replace(/^"|"$/g, "") ??
    null;

  const keywords = lower
    .replace(/[^a-z0-9\s]/g, " ")
    .split(/\s+/)
    .filter((w) => w.length > 3);

  return {
    text,
    genres: [...genres],
    themes: [...themes],
    length,
    similarTo: similar,
    keywords,
  };
}

/** ML model 3 — natural-language query understanding. Falls back to heuristics. */
export async function parseQuery(text: string): Promise<ParsedQuery> {
  const fallback = heuristicParse(text);
  const remote = await callModel<Partial<ParsedQuery>>("query", { text });
  if (!remote) return fallback;
  return {
    text,
    genres: remote.genres?.length ? normalizeGenres(remote.genres) : fallback.genres,
    themes: remote.themes?.length ? remote.themes : fallback.themes,
    length: remote.length ?? fallback.length,
    similarTo: remote.similarTo ?? fallback.similarTo,
    keywords: remote.keywords?.length ? remote.keywords : fallback.keywords,
  };
}

export function tagsForQuery(q: ParsedQuery): string[] {
  const tags = new Set<string>();
  for (const th of q.themes) for (const tag of THEME_TAGS[th] ?? []) tags.add(tag);
  return [...tags];
}
