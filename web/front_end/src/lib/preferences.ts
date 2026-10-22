/**
 * Shared (client + server safe) recommendation preference vocabulary.
 * The onboarding UI, the recommendation engine and the ML services all use
 * these same option lists so answers map cleanly onto book signals.
 */

import { READORA_CATEGORIES } from "@/lib/categories";

/** The official Readora taxonomy is the only user-facing genre vocabulary. */
export const GENRE_OPTIONS = READORA_CATEGORIES;

export const THEME_OPTIONS = [
  "Fast-paced",
  "Emotional",
  "Thought-provoking",
  "Educational",
  "Inspirational",
  "Relaxing",
  "Mysterious",
  "Funny",
  "Dark",
  "Motivational",
];

export const MOOD_OPTIONS = [
  "Something exciting",
  "Something relaxing",
  "Something emotional",
  "Something to learn from",
  "Something inspiring",
  "Surprise me",
];

export const FREQUENCY_OPTIONS = ["Daily", "Several times a week", "Once a week", "Occasionally"];

export const LENGTH_OPTIONS = ["Short books", "Medium-length books", "Long books", "No preference"];

export const FEEDBACK_REASONS = ["Not my genre", "Too long", "Not interested", "Already read it", "Other"];

export const THEME_TAGS: Record<string, string[]> = {
  "Fast-paced": ["thriller", "action", "adventure", "suspense", "fast-paced", "mystery"],
  Emotional: ["romance", "drama", "memoir", "coming-of-age", "family", "emotional", "grief"],
  "Thought-provoking": ["philosophy", "literary", "classic", "dystopia", "society", "science"],
  Educational: ["nonfiction", "science", "history", "psychology", "economics", "education"],
  Inspirational: ["inspiring", "memoir", "biography", "growth", "hope"],
  Relaxing: ["feel-good", "cozy", "contemporary", "poetry", "nature"],
  Mysterious: ["mystery", "detective", "crime", "suspense", "noir"],
  Funny: ["humor", "comedy", "satire", "witty"],
  Dark: ["dark", "horror", "gothic", "dystopia", "tragedy"],
  Motivational: ["self-help", "motivation", "habits", "productivity", "business", "growth"],
};

export const MOOD_TAGS: Record<string, string[]> = {
  "Something exciting": ["thriller", "adventure", "action", "fast-paced", "suspense"],
  "Something relaxing": ["feel-good", "cozy", "contemporary", "poetry", "humor"],
  "Something emotional": ["romance", "drama", "memoir", "family", "coming-of-age"],
  "Something to learn from": ["nonfiction", "science", "history", "psychology", "economics"],
  "Something inspiring": ["inspiring", "self-help", "motivation", "biography", "growth"],
  "Surprise me": [],
};

export type RecommendationProfile = {
  user_id: string;
  genres: string[];
  themes: string[];
  reading_mood: string | null;
  reading_frequency: string | null;
  preferred_book_length: string | null;
  favorite_books: string[];
  onboarding_completed: boolean;
};

export const EMPTY_PROFILE: Omit<RecommendationProfile, "user_id"> = {
  genres: [],
  themes: [],
  reading_mood: null,
  reading_frequency: null,
  preferred_book_length: null,
  favorite_books: [],
  onboarding_completed: false,
};
