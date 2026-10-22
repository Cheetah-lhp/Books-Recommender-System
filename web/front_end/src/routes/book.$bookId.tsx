import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, createFileRoute, useNavigate } from "@tanstack/react-router";
import { Heart, Minus, Plus, ShoppingBag, Sparkles, Star, Zap } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { AppShell } from "@/components/readora/AppShell";
import { BookCover } from "@/components/readora/BookCard";
import { Rating, Stars } from "@/components/readora/Rating";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { supabase } from "@/integrations/supabase/client";
import { useAuth } from "@/lib/auth";
import { addToCart, fetchUserWishlist, formatPrice, toggleWishlist } from "@/lib/ecommerce";
import { useWhyThisBook } from "@/lib/recommend";
import { bookQuery, reviewsQuery, similarBooksQuery, userBooksQuery } from "@/lib/data";
import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/book/$bookId")({
  head: () => ({
    meta: [
      { title: "Book details — READORA" },
      { name: "description", content: "Read the description, ratings and community reviews for this book." },
      { property: "og:title", content: "Book details — READORA" },
      { property: "og:description", content: "Ratings, reviews and recommendations on READORA." },
    ],
  }),
  component: BookPage,
});

function BookPage() {
  const { bookId } = Route.useParams();
  const { t } = useI18n();
  const { user } = useAuth();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { data, isLoading } = useQuery(bookQuery(bookId));
  const { data: reviews = [] } = useQuery(reviewsQuery(bookId));
  const { data: alsoLike = [] } = useQuery(similarBooksQuery(bookId));
  const { data: shelf = [] } = useQuery(userBooksQuery(user?.id ?? null));
  const { data: why } = useWhyThisBook(user?.id ?? null, bookId);
  const [rating, setRating] = useState(5);
  const [body, setBody] = useState("");
  const [qty, setQty] = useState(1);

  const { data: wishlist = [] } = useQuery({
    queryKey: ["wishlist", user?.id],
    queryFn: () => fetchUserWishlist(user?.id ?? null),
  });
  const isWishlisted = wishlist.some((item) => String(item.book_id) === String(bookId));

  const addToCartMutation = useMutation({
    mutationFn: async () => {
      await addToCart(user?.id ?? null, bookId, qty);
    },
    onSuccess: () => {
      toast.success(t("cart.added") || "Added to cart!");
      void qc.invalidateQueries({ queryKey: ["cart"] });
    },
    onError: () => toast.error("Could not add to cart"),
  });

  const buyNowMutation = useMutation({
    mutationFn: async () => {
      await addToCart(user?.id ?? null, bookId, qty);
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["cart"] });
      void navigate({ to: "/checkout" });
    },
    onError: () => toast.error("Could not proceed to checkout"),
  });

  const wishlistMutation = useMutation({
    mutationFn: async () => {
      return await toggleWishlist(user?.id ?? null, bookId);
    },
    onSuccess: (added) => {
      toast.success(added ? "Added to wishlist" : "Removed from wishlist");
      void qc.invalidateQueries({ queryKey: ["wishlist"] });
    },
    onError: () => toast.error("Could not update wishlist"),
  });

  const shelve = useMutation({
    mutationFn: async (status: string) => {
      if (!user) throw new Error("auth");
      const { error } = await supabase
        .from("user_books")
        .upsert({ user_id: user.id, book_id: bookId, status }, { onConflict: "user_id,book_id" });
      if (error) throw error;
    },
    onSuccess: () => {
      toast.success("Saved to your library");
      void qc.invalidateQueries({ queryKey: ["user-books"] });
    },
    onError: () => toast.error(user ? "Could not save" : t("auth.signedOut")),
  });

  const review = useMutation({
    mutationFn: async () => {
      if (!user) throw new Error("auth");
      const { error } = await supabase
        .from("reviews")
        .upsert({ user_id: user.id, book_id: bookId, rating, body }, { onConflict: "user_id,book_id" });
      if (error) throw error;
    },
    onSuccess: () => {
      setBody("");
      toast.success("Review published");
      void qc.invalidateQueries({ queryKey: ["reviews", bookId] });
      void qc.invalidateQueries({ queryKey: ["book", bookId] });
    },
    onError: () => toast.error(user ? "Could not publish" : t("auth.signedOut")),
  });

  const book = data?.book;

  if (isLoading) {
    return (
      <AppShell>
        <p className="text-sm text-muted-foreground">…</p>
      </AppShell>
    );
  }

  if (!book) {
    return (
      <AppShell>
        <div className="surface-card p-8 text-center">
          <h1 className="font-display text-xl font-bold text-foreground">Book not found</h1>
          <p className="mt-2 text-sm text-muted-foreground">This book is no longer available.</p>
          <Link to="/discover" className="mt-4 inline-block text-sm font-semibold text-gold">
            Browse books
          </Link>
        </div>
      </AppShell>
    );
  }

  const shelfStatus = shelf.find((s) => s.book_id === book.id)?.status ?? null;

  const totalReviews = reviews.length;
  const fallbackPct: Record<number, number> = { 5: 79, 4: 16, 3: 4, 2: 1, 1: 0 };
  const breakdown = [5, 4, 3, 2, 1].map((star) => {
    const count = reviews.filter((r) => r.rating === star).length;
    const pct = totalReviews ? Math.round((count / totalReviews) * 100) : (fallbackPct[star] ?? 0);

    const estCount = totalReviews ? count : Math.round((pct / 100) * book.ratings_count);
    return { star, pct, count: estCount };
  });

  return (
    <AppShell>
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="surface-card p-4 sm:p-5">
          <div className="grid gap-6 sm:grid-cols-[180px_minmax(0,1fr)] lg:grid-cols-[200px_minmax(0,1fr)]">
            <BookCover book={book} className="mx-auto aspect-[2/3] w-40 sm:mx-0 sm:w-full" />
            <div className="min-w-0">
              <h1 className="font-display text-2xl font-extrabold text-foreground sm:text-3xl">{book.title}</h1>
              <p className="text-sm text-muted-foreground">{book.author_name}</p>
              <div className="mt-2 flex flex-wrap items-center gap-2">
                <Rating value={book.rating} />
                <Stars value={book.rating} />
                <span className="text-xs text-muted-foreground">
                  ({book.ratings_count.toLocaleString()} {t("book.ratingsCount")})
                </span>
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                {(data?.categories ?? []).map((c) => (
                  <Link
                    key={c.slug}
                    to="/category/$slug"
                    params={{ slug: c.slug }}
                    className="rounded-full bg-secondary px-3 py-1 text-xs font-medium text-secondary-foreground"
                  >
                    {c.name}
                  </Link>
                ))}
              </div>
              <p className="mt-4 line-clamp-4 text-sm text-muted-foreground">{book.description}</p>
              <dl className="mt-4 grid gap-1 text-xs text-muted-foreground sm:grid-cols-2">
                <div>
                  {t("book.published")}: <span className="text-foreground">{book.published_year ?? "—"}</span>
                </div>
                <div>
                  {t("book.pages")}: <span className="text-foreground">{book.pages ?? "—"}</span>
                </div>
                <div>
                  {t("book.language")}: <span className="text-foreground">{book.language}</span>
                </div>
                <div>
                  Publisher: <span className="text-foreground">{book.publisher ?? "—"}</span>
                </div>
                {book.isbn ? (
                  <div>
                    ISBN: <span className="text-foreground">{book.isbn}</span>
                  </div>
                ) : null}
              </dl>
              {book.tags?.length ? (
                <div className="mt-3 flex flex-wrap gap-2">
                  {book.tags.map((tag) => (
                    <span
                      key={tag}
                      className="rounded-full border border-border px-3 py-1 text-[11px] font-medium text-muted-foreground"
                    >
                      #{tag}
                    </span>
                  ))}
                </div>
              ) : null}
              {/* E-Commerce Price & Purchasing Section */}
              <div className="mt-6 rounded-2xl border border-gold/30 bg-gold/5 p-4 sm:p-5">
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <div>
                    <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Price</span>
                    <div className="flex items-baseline gap-2">
                      <span className="text-3xl font-extrabold text-gold">
                        {formatPrice(book.price && book.price > 0 ? book.price : Number((((Number(book.id) * 37) % 30) + 9.99).toFixed(2)))}
                      </span>
                      <span className="text-xs text-muted-foreground line-through">
                        {formatPrice((book.price && book.price > 0 ? book.price : Number((((Number(book.id) * 37) % 30) + 9.99).toFixed(2))) * 1.25)}
                      </span>
                      <span className="rounded-full bg-emerald-500/10 px-2 py-0.5 text-[10px] font-bold text-emerald-500">In Stock</span>
                    </div>
                  </div>

                  {/* Quantity Stepper */}
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-muted-foreground">Qty:</span>
                    <div className="flex items-center rounded-full border border-border bg-background p-1">
                      <button
                        type="button"
                        onClick={() => setQty(Math.max(1, qty - 1))}
                        className="flex h-7 w-7 items-center justify-center rounded-full hover:bg-accent text-muted-foreground hover:text-foreground transition-colors"
                        aria-label="Decrease quantity"
                      >
                        <Minus className="h-3.5 w-3.5" />
                      </button>
                      <span className="w-8 text-center text-xs font-bold text-foreground">{qty}</span>
                      <button
                        type="button"
                        onClick={() => setQty(qty + 1)}
                        className="flex h-7 w-7 items-center justify-center rounded-full hover:bg-accent text-muted-foreground hover:text-foreground transition-colors"
                        aria-label="Increase quantity"
                      >
                        <Plus className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  </div>
                </div>

                {/* Primary Action Buttons: Add to Cart, Buy Now, Wishlist */}
                <div className="mt-4 flex flex-wrap gap-2.5">
                  <Button
                    onClick={() => addToCartMutation.mutate()}
                    disabled={addToCartMutation.isPending}
                    className="flex-1 rounded-full bg-gold py-5 text-sm font-bold text-gold-foreground hover:bg-gold/90 shadow-md shadow-gold/20 flex items-center justify-center gap-2"
                  >
                    <ShoppingBag className="h-4 w-4" />
                    <span>{t("action.addToCart") || "Add to Cart"}</span>
                  </Button>

                  <Button
                    onClick={() => buyNowMutation.mutate()}
                    disabled={buyNowMutation.isPending}
                    className="flex-1 rounded-full bg-primary py-5 text-sm font-bold text-primary-foreground hover:bg-primary/90 flex items-center justify-center gap-2"
                  >
                    <Zap className="h-4 w-4 text-gold" />
                    <span>{t("action.buyNow") || "Buy Now"}</span>
                  </Button>

                  <Button
                    variant="outline"
                    onClick={() => wishlistMutation.mutate()}
                    disabled={wishlistMutation.isPending}
                    className={`h-11 w-11 rounded-full border-border p-0 transition-colors ${
                      isWishlisted ? "bg-rose-500/10 border-rose-500/30 text-rose-500" : "text-muted-foreground hover:text-rose-500"
                    }`}
                    aria-label="Wishlist"
                  >
                    <Heart className={`h-5 w-5 ${isWishlisted ? "fill-current text-rose-500" : ""}`} />
                  </Button>
                </div>
              </div>

              {/* Reading Status Buttons */}
              <div className="mt-4 flex flex-wrap gap-3">
                <Button
                  variant="outline"
                  className="rounded-full text-xs"
                  disabled={shelve.isPending}
                  onClick={() => shelve.mutate("reading")}
                >
                  {shelfStatus === "reading" ? "In your library" : t("book.addLibrary")}
                </Button>
                <Button
                  variant="outline"
                  className="rounded-full text-xs"
                  disabled={shelve.isPending}
                  onClick={() => shelve.mutate("want_to_read")}
                >
                  {shelfStatus === "want_to_read" ? "On your list" : t("book.wantRead")}
                </Button>
              </div>
            </div>
          </div>
        </div>

        <aside className="surface-card p-5">
          <h2 className="mb-3 font-display text-lg font-bold text-foreground">{t("book.alsoLike")}</h2>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-1">
            {alsoLike.map((b) => (
              <Link
                key={b.id}
                to="/book/$bookId"
                params={{ bookId: b.id }}
                className="flex items-center gap-3 rounded-xl p-1 transition-colors hover:bg-accent"
              >
                <BookCover book={b} className="h-14 w-10 shrink-0" />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-semibold text-foreground">{b.title}</span>
                  <span className="block truncate text-xs text-muted-foreground">{b.author_name}</span>
                  <Rating value={b.rating} className="text-xs" />
                </span>
              </Link>
            ))}
          </div>
        </aside>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <section className="surface-card p-5">
          <h2 className="mb-2 font-display text-lg font-bold text-foreground">{t("book.about")}</h2>
          <p className="text-sm leading-relaxed text-muted-foreground">{book.description}</p>
          {why ? (
            <p className="mt-4 flex items-start gap-2 rounded-xl border border-gold/40 bg-gold/10 px-3 py-2 text-sm text-foreground">
              <Sparkles className="mt-0.5 h-4 w-4 shrink-0 text-gold" />
              <span>{why}</span>
            </p>
          ) : null}
        </section>

        <section className="surface-card p-5">
          <h2 className="mb-3 font-display text-lg font-bold text-foreground">{t("book.ratings")}</h2>
          <div className="flex flex-col items-start gap-6 sm:flex-row">
            <div className="mx-auto text-center sm:mx-0">
              <p className="font-display text-4xl font-extrabold text-foreground">{book.rating.toFixed(1)}</p>
              <Stars value={book.rating} />
              <p className="mt-1 text-xs text-muted-foreground">
                {book.ratings_count.toLocaleString()} {t("book.ratingsCount")}
              </p>
            </div>
            <div className="min-w-0 flex-1 space-y-1 self-stretch">
              {breakdown.map((b) => (
                <div key={b.star} className="flex items-center gap-2 text-xs text-muted-foreground">
                  <span className="w-3">{b.star}</span>
                  <span className="h-2 flex-1 overflow-hidden rounded-full bg-secondary">
                    <span className="block h-full rounded-full bg-gold" style={{ width: `${b.pct}%` }} />
                  </span>
                  <span className="w-8 text-end">{b.pct}%</span>
                  <span className="w-12 text-end">{b.count.toLocaleString()}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="mt-5 border-t border-border pt-4">
            <div className="mb-2 flex items-center gap-1">
              {[1, 2, 3, 4, 5].map((r) => (
                <button
                  key={r}
                  type="button"
                  aria-label={`${r} stars`}
                  onClick={() => setRating(r)}
                  className="p-0.5"
                >
                  <Star className={cn("h-5 w-5", r <= rating ? "fill-gold text-gold" : "text-border")} />
                </button>
              ))}
              <span className="ms-2 text-xs text-muted-foreground">{rating}/5</span>
            </div>
            <Textarea
              value={body}
              onChange={(e) => setBody(e.target.value)}
              placeholder={t("book.writeReview")}
              className="min-h-20"
            />
            <Button
              className="mt-2 rounded-full bg-gold text-gold-foreground hover:bg-gold/90"
              disabled={review.isPending}
              onClick={() => review.mutate()}
            >
              {t("book.writeReview")}
            </Button>
          </div>

          <div className="mt-4 space-y-3">
            {reviews.map((r) => (
              <div key={r.id} className="rounded-xl bg-secondary/60 p-3">
                <div className="flex flex-wrap items-center gap-2">
                  <p className="text-sm font-semibold text-foreground">{r.profiles?.full_name ?? "Reader"}</p>
                  <Stars value={r.rating} size={12} />
                  <span className="text-[11px] text-muted-foreground">
                    {new Date(r.created_at).toLocaleDateString()}
                  </span>
                </div>
                {r.body ? <p className="mt-1 text-sm text-muted-foreground">{r.body}</p> : null}
              </div>
            ))}
          </div>
        </section>
      </div>
    </AppShell>
  );
}
