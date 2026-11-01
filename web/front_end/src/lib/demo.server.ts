import { READORA_CATEGORY_DEFS } from "./categories";
import { fetchCatalog } from "./ml/catalog.server";
import { buildSections, EMPTY_SIGNALS, type ModelReport, type Signals } from "./ml/engine.server";

function requireDemo() {
  if (process.env["READORA_DEMO_MODE"] !== "1") {
    throw new Error("Local demo is disabled. Start it with scripts/start-demo.ps1.");
  }
}

export async function demoOptions() {
  requireDemo();
  const catalog = await fetchCatalog();
  return {
    genres: READORA_CATEGORY_DEFS.map((category) => category.name),
    books: catalog.map((book) => ({ id: book.id, title: book.title })),
  };
}

export async function demoRecommendations(input: {
  scenario: "genre" | "favorite" | "history";
  genre: string;
  bookId?: string | undefined;
}) {
  requireDemo();
  const catalog = await fetchCatalog();
  if (!catalog.length)
    throw new Error("Catalog is unavailable. Check http://127.0.0.1:8000/health.");
  const book = catalog.find((candidate) => candidate.id === input.bookId) ?? catalog[0]!;
  const other = catalog.filter((candidate) => candidate.id !== book.id);
  const signals: Signals = { ...EMPTY_SIGNALS };
  const inputs: { id?: string; title: string; action: string }[] = [];
  if (input.scenario === "genre") {
    if (!READORA_CATEGORY_DEFS.some((category) => category.name === input.genre)) {
      throw new Error("Choose a genre from the list.");
    }
    signals.genres = [input.genre];
    inputs.push({ title: input.genre, action: "Thể loại đã chọn" });
  } else if (input.scenario === "favorite") {
    signals.favoriteBookIds = [book.id];
    inputs.push({ id: book.id, title: book.title, action: "Sách yêu thích" });
  } else {
    signals.shelves = [{ book_id: book.id, status: "read" }];
    signals.ratings = [{ book_id: book.id, rating: 5, body: null }];
    signals.positiveBookIds = [book.id];
    inputs.push({ id: book.id, title: book.title, action: "Đã đọc · 5 sao" });
    if (other[0]) {
      signals.ratings.push({ book_id: other[0].id, rating: 1, body: null });
      inputs.push({ id: other[0].id, title: other[0].title, action: "Đánh giá 1 sao" });
    }
    if (other[1]) {
      signals.hidden = [other[1].id];
      inputs.push({ id: other[1].id, title: other[1].title, action: "Đã ẩn" });
    }
  }
  const telemetry: { model: ModelReport | null } = { model: null };
  const sections = await buildSections(null, signals, (report) => {
    telemetry.model = report;
  });
  return { sections, inputs, model: telemetry.model };
}
