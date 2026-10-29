import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, createFileRoute } from "@tanstack/react-router";
import { Heart, ShoppingBag, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { AppShell } from "@/components/readora/AppShell";
import { BookCover, SectionHeader } from "@/components/readora/BookCard";
import { Rating } from "@/components/readora/Rating";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth";
import {
  addToCart,
  fetchUserWishlist,
  formatPrice,
  toggleWishlist,
  type WishlistItem,
} from "@/lib/ecommerce";
import { useI18n } from "@/lib/i18n";

export const Route = createFileRoute("/wishlist")({
  head: () => ({
    meta: [
      { title: "Wishlist — Book Recommender System" },
      { name: "description", content: "Your saved books and reading desires." },
    ],
  }),
  component: WishlistPage,
});

function WishlistPage() {
  const { t } = useI18n();
  const { user } = useAuth();
  const qc = useQueryClient();
  const [localTick, setLocalTick] = useState(0);

  useEffect(() => {
    const handleWishlistUpdate = () => setLocalTick((prev) => prev + 1);
    window.addEventListener("wishlist_updated", handleWishlistUpdate);
    return () => window.removeEventListener("wishlist_updated", handleWishlistUpdate);
  }, []);

  const { data: items = [], isLoading } = useQuery({
    queryKey: ["wishlist", user?.id, localTick],
    queryFn: () => fetchUserWishlist(user?.id ?? null),
  });

  const moveToCartMutation = useMutation({
    mutationFn: async (item: WishlistItem) => {
      await addToCart(user?.id ?? null, item.book_id, 1);
      await toggleWishlist(user?.id ?? null, item.book_id);
    },
    onSuccess: () => {
      toast.success(t("cart.added") || "Added to cart!");
      void qc.invalidateQueries({ queryKey: ["wishlist"] });
      void qc.invalidateQueries({ queryKey: ["cart"] });
    },
  });

  const removeMutation = useMutation({
    mutationFn: async (item: WishlistItem) => {
      await toggleWishlist(user?.id ?? null, item.book_id);
    },
    onSuccess: () => {
      toast.success("Removed from wishlist");
      void qc.invalidateQueries({ queryKey: ["wishlist"] });
    },
  });

  return (
    <AppShell>
      <SectionHeader
        title={t("wishlist.title") || "My Wishlist"}
        subtitle={
          items.length > 0
            ? `${items.length} ${t("wishlist.count") || "books you've saved"}`
            : (t("wishlist.empty") || "Your wishlist is empty")
        }
      />

      {isLoading ? (
        <div className="surface-card p-12 text-center text-muted-foreground">
          <p className="animate-pulse">Loading your wishlist...</p>
        </div>
      ) : items.length === 0 ? (
        <div className="surface-card flex flex-col items-center justify-center p-12 text-center">
          <div className="flex h-20 w-20 items-center justify-center rounded-full bg-secondary/80 text-muted-foreground mb-4">
            <Heart className="h-10 w-10 text-rose-500" />
          </div>
          <h3 className="font-display text-xl font-bold text-foreground">Your wishlist is empty</h3>
          <p className="mt-2 max-w-md text-sm text-muted-foreground">
            Save books you'd love to read or purchase later by clicking the heart button on any book page.
          </p>
          <Button asChild className="mt-6 rounded-full bg-gold px-6 text-gold-foreground hover:bg-gold/90">
            <Link to="/discover">Discover Books</Link>
          </Button>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4">
          {items.map((item) => {
            const book = item.book;
            if (!book) return null;
            return (
              <div
                key={item.id}
                className="surface-card group flex flex-col justify-between overflow-hidden p-4 transition-all hover:border-gold/50"
              >
                <div>
                  <Link to="/book/$bookId" params={{ bookId: book.id }} className="block">
                    <BookCover book={book} className="mx-auto aspect-[2/3] w-36 rounded-lg shadow-md transition-transform group-hover:scale-105" />
                  </Link>

                  <div className="mt-4">
                    <Link
                      to="/book/$bookId"
                      params={{ bookId: book.id }}
                      className="block font-display text-sm font-bold text-foreground hover:text-gold transition-colors line-clamp-1"
                    >
                      {book.title}
                    </Link>
                    <p className="text-xs text-muted-foreground line-clamp-1">{book.author_name}</p>
                    <div className="mt-2 flex items-center justify-between">
                      <Rating value={book.rating} />
                      <span className="text-sm font-bold text-gold">{formatPrice(book.price ?? 14.99)}</span>
                    </div>
                  </div>
                </div>

                <div className="mt-5 flex gap-2 pt-3 border-t border-border">
                  <Button
                    size="sm"
                    onClick={() => moveToCartMutation.mutate(item)}
                    disabled={moveToCartMutation.isPending}
                    className="flex-1 rounded-full bg-gold text-xs font-bold text-gold-foreground hover:bg-gold/90 flex items-center justify-center gap-1.5"
                  >
                    <ShoppingBag className="h-3.5 w-3.5" />
                    <span>Add to Cart</span>
                  </Button>
                  <Button
                    variant="outline"
                    size="icon"
                    onClick={() => removeMutation.mutate(item)}
                    disabled={removeMutation.isPending}
                    className="h-8 w-8 rounded-full border-border hover:text-destructive hover:border-destructive"
                    aria-label="Remove"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </AppShell>
  );
}
