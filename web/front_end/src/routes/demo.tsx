import { useServerFn } from "@tanstack/react-start";
import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { AppShell } from "@/components/readora/AppShell";
import { BookCard } from "@/components/readora/BookCard";
import { Button } from "@/components/ui/button";
import { getDemoOptions, runDemo } from "@/lib/demo.functions";

export const Route = createFileRoute("/demo")({
  component: DemoPage,
  head: () => ({ meta: [{ title: "Demo gợi ý sách — READORA" }] }),
});

function DemoPage() {
  const loadOptions = useServerFn(getDemoOptions);
  const recommend = useServerFn(runDemo);
  const { data: options, error: optionsError } = useQuery({
    queryKey: ["demo-options"],
    queryFn: () => loadOptions(),
    retry: false,
  });
  const [scenario, setScenario] = useState<"genre" | "favorite" | "history">("genre");
  const [genre, setGenre] = useState("Fantasy & Paranormal");
  const [bookId, setBookId] = useState("");
  const [result, setResult] = useState<Awaited<ReturnType<typeof runDemo>> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function submit() {
    setLoading(true);
    setError("");
    setResult(null);
    try {
      setResult(await recommend({ data: { scenario, genre, bookId: bookId || undefined } }));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể lấy gợi ý.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <AppShell>
      <h1 className="font-display text-3xl font-bold">Demo gợi ý sách</h1>
      <p className="mt-2 text-sm text-muted-foreground">
        Thử ba tình huống với sách thật từ tập mẫu. Các lựa chọn chỉ dùng cho lượt demo này.
      </p>
      <form
        className="mt-6 grid gap-4 rounded-2xl border border-border bg-card p-5 sm:grid-cols-2"
        onSubmit={(event) => {
          event.preventDefault();
          void submit();
        }}
      >
        <label className="grid gap-2 text-sm font-medium">
          Tình huống
          <select
            aria-label="Tình huống"
            value={scenario}
            onChange={(event) => {
              setScenario(event.target.value as typeof scenario);
              setResult(null);
            }}
            className="h-11 rounded-lg border border-border bg-background px-3"
          >
            <option value="genre">1. User mới chọn thể loại</option>
            <option value="favorite">2. User có sách yêu thích</option>
            <option value="history">3. User có lịch sử và đánh giá</option>
          </select>
        </label>
        {scenario === "genre" ? (
          <label className="grid gap-2 text-sm font-medium">
            Thể loại
            <select
              aria-label="Thể loại"
              value={genre}
              onChange={(event) => setGenre(event.target.value)}
              className="h-11 rounded-lg border border-border bg-background px-3"
            >
              {options?.genres.map((value) => (
                <option key={value}>{value}</option>
              ))}
            </select>
          </label>
        ) : (
          <label className="grid gap-2 text-sm font-medium">
            {scenario === "favorite" ? "Sách yêu thích" : "Sách đã đọc và đánh giá 5 sao"}
            <select
              aria-label="Chọn sách"
              value={bookId || options?.books[0]?.id || ""}
              onChange={(event) => setBookId(event.target.value)}
              className="h-11 min-w-0 rounded-lg border border-border bg-background px-3"
            >
              {options?.books.map((book) => (
                <option key={book.id} value={book.id}>
                  {book.title}
                </option>
              ))}
            </select>
          </label>
        )}
        <Button
          type="submit"
          disabled={loading || !options?.books.length}
          className="sm:col-span-2 sm:w-fit"
        >
          {loading ? "Đang lấy gợi ý…" : "Lấy gợi ý"}
        </Button>
      </form>
      {(error || optionsError) && (
        <p role="alert" className="mt-4 text-destructive">
          {error || optionsError?.message}
        </p>
      )}
      {result && (
        <div className="mt-6" aria-live="polite">
          <div
            className="rounded-xl border border-border bg-card p-4 text-sm"
            data-testid="demo-status"
          >
            {result.model?.source === "model" ? (
              <p className="font-semibold text-green-600">Đang dùng model · {result.model.runId}</p>
            ) : (
              <p className="font-semibold text-amber-600">
                Đang dùng fallback · model chưa khả dụng
              </p>
            )}
            <p className="mt-1 text-muted-foreground">
              {result.model?.candidates ?? 0} ứng viên · {Math.round(result.model?.durationMs ?? 0)}{" "}
              ms
            </p>
            <ul className="mt-3 space-y-1" data-testid="demo-inputs">
              {result.inputs.map((input) => (
                <li key={`${input.action}-${input.title}`}>
                  {input.action}: {input.title}
                </li>
              ))}
            </ul>
          </div>
          {result.sections.slice(0, 1).map((section) => (
            <section key={section.key} className="mt-6">
              <h2 className="font-display text-xl font-bold">Gợi ý cho bạn</h2>
              <div
                className="mt-4 grid grid-cols-2 gap-5 sm:grid-cols-3 lg:grid-cols-4"
                data-testid="demo-results"
              >
                {section.books.map((recommendation) => (
                  <div key={recommendation.book.id} data-book-id={recommendation.book.id}>
                    <BookCard book={recommendation.book} />
                    <p className="mt-2 text-xs text-muted-foreground">{recommendation.why}</p>
                  </div>
                ))}
              </div>
            </section>
          ))}
          {!result.sections.length && (
            <p className="mt-4">Không có sách phù hợp với lựa chọn này.</p>
          )}
        </div>
      )}
    </AppShell>
  );
}
