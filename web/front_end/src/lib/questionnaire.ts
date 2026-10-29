import { READORA_CATEGORIES, normalizeGenres } from "@/lib/categories";
import type { Book } from "@/lib/data";

export type Answers = {
  ageGroup: string;
  genres: string[];
  readingMood: string;
  favoriteBook: string;
  location: string;
  preferredLanguage: string;
  readingFrequency: string;
  preferredBookLength: string;
};

export const EMPTY_ANSWERS: Answers = {
  ageGroup: "",
  genres: [],
  readingMood: "",
  favoriteBook: "",
  location: "",
  preferredLanguage: "",
  readingFrequency: "",
  preferredBookLength: "",
};

export const AGE_GROUPS = ["Under 18", "18-24", "25-34", "35-44", "45-54", "55+"];
export const GENRES = READORA_CATEGORIES;
export const MOODS = [
  "Something inspiring",
  "A page-turner",
  "Deep & intellectual",
  "Light & fun",
  "Emotional journey",
  "Eye-opening facts",
];
export const LANGUAGES = ["Arabic", "English", "French", "German", "Spanish"];
export const FREQUENCIES = ["Daily", "Weekly", "Monthly", "Occasionally"];
export const LENGTHS = ["Short (<200)", "Medium (200-400)", "Long (400+)", "Any"];

export const ANSWERS_STORAGE_KEY = "readora.questionnaire";

export function loadStoredAnswers(): Answers | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(ANSWERS_STORAGE_KEY);
    if (!raw) return null;
    const parsed = { ...EMPTY_ANSWERS, ...(JSON.parse(raw) as Partial<Answers>) };
    // Map previously saved genres onto the official Readora categories.
    return { ...parsed, genres: normalizeGenres(parsed.genres ?? []) };
  } catch {
    return null;
  }
}

export function storeAnswers(answers: Answers) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(ANSWERS_STORAGE_KEY, JSON.stringify(answers));
}

export async function fetchQuestionnaireRecommendations(answers: Answers, userId: string | null): Promise<Book[]> {
  const res = await fetch("/api/recommendations", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ ...answers, userId }),
  });
  if (!res.ok) return [];
  const json = (await res.json()) as { books?: Book[] };
  return json.books ?? [];
}
