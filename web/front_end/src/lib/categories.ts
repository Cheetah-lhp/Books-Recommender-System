/**
 * SINGLE SOURCE OF TRUTH for the Readora user-facing category taxonomy.
 *
 * The dataset may hold more granular genres/subgenres (kept intact on
 * `books.tags` for the recommendation models). Everything shown to the user
 * is normalized through this mapping layer into one of the 10 categories.
 */

export type ReadoraCategory = {
  name: string;
  slug: string;
  icon: string;
  /** Raw dataset genres/subgenres that normalize into this category. */
  tags: string[];
};

export const READORA_CATEGORY_DEFS: ReadoraCategory[] = [
  {
    name: "Fiction",
    slug: "fiction",
    icon: "book-open",
    tags: [
      "fiction",
      "literary",
      "literary fiction",
      "contemporary",
      "classic",
      "classics",
      "adventure",
      "science fiction",
      "sci-fi",
      "scifi",
      "dystopia",
      "dystopian",
      "drama",
      "short stories",
      "satire",
      "humor",
      "horror",
    ],
  },
  {
    name: "Romance",
    slug: "romance",
    icon: "heart",
    tags: ["romance", "romantic", "love", "chick lit", "contemporary romance", "historical romance"],
  },
  {
    name: "Fantasy & Paranormal",
    slug: "fantasy-paranormal",
    icon: "sparkle",
    tags: [
      "fantasy",
      "paranormal",
      "epic fantasy",
      "high fantasy",
      "urban fantasy",
      "magic",
      "magical realism",
      "supernatural",
      "vampires",
      "witches",
      "mythology",
    ],
  },
  {
    name: "Mystery, Thriller & Crime",
    slug: "mystery-thriller-crime",
    icon: "search",
    tags: [
      "mystery",
      "thriller",
      "crime",
      "detective",
      "suspense",
      "noir",
      "police",
      "true crime",
      "psychological thriller",
      "spy",
    ],
  },
  {
    name: "Young Adult",
    slug: "young-adult",
    icon: "star",
    tags: ["young adult", "ya", "teen", "coming-of-age", "coming of age", "school"],
  },
  {
    name: "Children",
    slug: "children",
    icon: "crown",
    tags: ["children", "childrens", "kids", "picture book", "middle grade", "juvenile", "fairy tale"],
  },
  {
    name: "Comics & Graphic",
    slug: "comics-graphic",
    icon: "rocket",
    tags: ["comics", "comic", "graphic novel", "graphic novels", "manga", "superhero", "bd"],
  },
  {
    name: "Poetry",
    slug: "poetry",
    icon: "feather",
    tags: ["poetry", "poems", "verse", "anthology"],
  },
  {
    name: "Non-Fiction",
    slug: "non-fiction",
    icon: "landmark",
    tags: [
      "nonfiction",
      "non-fiction",
      "self-help",
      "self help",
      "business",
      "economics",
      "psychology",
      "philosophy",
      "science",
      "technology",
      "health",
      "productivity",
      "motivation",
      "habits",
      "education",
      "travel",
      "cooking",
      "religion",
      "spirituality",
      "essays",
    ],
  },
  {
    name: "History & Biography",
    slug: "history-biography",
    icon: "user-round",
    tags: ["history", "historical", "biography", "autobiography", "memoir", "war", "politics", "royalty"],
  },
];

/** The official 10 Readora categories, in display order. */
export const READORA_CATEGORIES = READORA_CATEGORY_DEFS.map((c) => c.name);

export const READORA_CATEGORY_SLUGS = READORA_CATEGORY_DEFS.map((c) => c.slug);

export function categoryBySlug(slug: string): ReadoraCategory | undefined {
  return READORA_CATEGORY_DEFS.find((c) => c.slug === slug.toLowerCase());
}

export function categoryLabel(slug: string): string {
  return categoryBySlug(slug)?.name ?? slug.replace(/-/g, " ");
}

/** Raw dataset genre/subgenre -> one of the 10 official categories (or null). */
export function normalizeGenre(raw: string | null | undefined): string | null {
  if (!raw) return null;
  const value = raw.trim().toLowerCase();
  if (!value) return null;
  const exact = READORA_CATEGORY_DEFS.find((c) => c.name.toLowerCase() === value || c.slug === value);
  if (exact) return exact.name;
  const tagged = READORA_CATEGORY_DEFS.find((c) => c.tags.includes(value));
  if (tagged) return tagged.name;
  const partial = READORA_CATEGORY_DEFS.find((c) => c.tags.some((t) => value.includes(t) || t.includes(value)));
  return partial?.name ?? null;
}

/** Normalize a list of raw genres, de-duplicated, order preserved. */
export function normalizeGenres(raw: (string | null | undefined)[]): string[] {
  const out: string[] = [];
  for (const item of raw) {
    const mapped = normalizeGenre(item);
    if (mapped && !out.includes(mapped)) out.push(mapped);
  }
  return out;
}

/** Raw tags a category should match against when scoring books. */
export function categorySearchTerms(category: string): string[] {
  const def = READORA_CATEGORY_DEFS.find((c) => c.name === category || c.slug === category.toLowerCase());
  if (!def) return [category.toLowerCase()];
  return [def.name.toLowerCase(), def.slug, ...def.tags];
}
