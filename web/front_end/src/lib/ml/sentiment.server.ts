import { callModel } from "./models.server";

export type Sentiment = { label: "positive" | "neutral" | "negative"; score: number };

const POSITIVE = ["love", "loved", "amazing", "brilliant", "great", "beautiful", "favourite", "favorite", "excellent", "gripping", "moving", "perfect"];
const NEGATIVE = ["boring", "bad", "hate", "hated", "disappointing", "slow", "confusing", "awful", "weak", "predictable"];

/** ML model 2 — review sentiment. Falls back to a lexicon heuristic. */
export async function analyzeSentiment(texts: string[]): Promise<Sentiment[]> {
  if (texts.length === 0) return [];
  const remote = await callModel<{ results?: Sentiment[] }>("sentiment", { texts });
  if (remote?.results?.length === texts.length) return remote.results;

  return texts.map((raw) => {
    const text = (raw ?? "").toLowerCase();
    const pos = POSITIVE.filter((w) => text.includes(w)).length;
    const neg = NEGATIVE.filter((w) => text.includes(w)).length;
    const score = (pos - neg) / Math.max(1, pos + neg);
    if (pos > neg) return { label: "positive" as const, score };
    if (neg > pos) return { label: "negative" as const, score };
    return { label: "neutral" as const, score: 0 };
  });
}
