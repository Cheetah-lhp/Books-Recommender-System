import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, createFileRoute, useNavigate } from "@tanstack/react-router";
import { ArrowRight, Minus, Plus, ShoppingBag, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { AppShell } from "@/components/readora/AppShell";
import { BookCover, SectionHeader } from "@/components/readora/BookCard";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth";
import {
  fetchUserCart,
  formatPrice,
  removeFromCart,
  updateCartQuantity,
  type CartItem,
} from "@/lib/ecommerce";
import { useI18n } from "@/lib/i18n";

export const Route = createFileRoute("/cart")({
  head: () => ({
    meta: [
      { title: "Shopping Cart — Book Recommender System" },
      { name: "description", content: "View and manage your selected books in your shopping cart." },
    ],
  }),
  component: CartPage,
});

function CartPage() {
  const { t } = useI18n();
  const { user } = useAuth();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [localTick, setLocalTick] = useState(0);

  // Lắng nghe sự kiện cập nhật giỏ hàng từ localStorage khi chưa đăng nhập
  useEffect(() => {
    const handleCartUpdate = () => setLocalTick((prev) => prev + 1);
    window.addEventListener("cart_updated", handleCartUpdate);
    return () => window.removeEventListener("cart_updated", handleCartUpdate);
  }, []);

  const { data: items = [], isLoading } = useQuery({
    queryKey: ["cart", user?.id, localTick],
    queryFn: () => fetchUserCart(user?.id ?? null),
  });

  const updateQtyMutation = useMutation({
    mutationFn: async ({ item, quantity }: { item: CartItem; quantity: number }) => {
      await updateCartQuantity(user?.id ?? null, item.id, item.book_id, quantity);
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["cart"] });
    },
  });

  const removeItemMutation = useMutation({
    mutationFn: async (item: CartItem) => {
      await removeFromCart(user?.id ?? null, item.id, item.book_id);
    },
    onSuccess: () => {
      toast.success(t("cart.removed") || "Removed from cart");
      void qc.invalidateQueries({ queryKey: ["cart"] });
    },
  });

  const subtotal = items.reduce((acc, item) => {
    const price = item.book?.price ?? 14.99;
    return acc + price * item.quantity;
  }, 0);

  const shipping = subtotal > 35 || subtotal === 0 ? 0 : 4.99;
  const total = subtotal + shipping;

  return (
    <AppShell>
      <SectionHeader
        title={t("cart.title") || "Shopping Cart"}
        subtitle={
          items.length > 0
            ? `${items.reduce((s, i) => s + i.quantity, 0)} ${t("cart.items") || "items in your cart"}`
            : (t("cart.empty") || "Your cart is currently empty")
        }
      />

      {isLoading ? (
        <div className="surface-card p-12 text-center text-muted-foreground">
          <p className="animate-pulse">Loading your cart...</p>
        </div>
      ) : items.length === 0 ? (
        <div className="surface-card flex flex-col items-center justify-center p-12 text-center">
          <div className="flex h-20 w-20 items-center justify-center rounded-full bg-secondary/80 text-muted-foreground mb-4">
            <ShoppingBag className="h-10 w-10 text-gold" />
          </div>
          <h3 className="font-display text-xl font-bold text-foreground">Your cart is empty</h3>
          <p className="mt-2 max-w-md text-sm text-muted-foreground">
            Looks like you haven't added any books to your cart yet. Explore our curated selection and find your next favorite!
          </p>
          <Button asChild className="mt-6 rounded-full bg-gold px-6 text-gold-foreground hover:bg-gold/90">
            <Link to="/discover">Explore Books</Link>
          </Button>
        </div>
      ) : (
        <div className="grid gap-8 lg:grid-cols-[1fr_360px]">
          {/* Danh sách sách trong giỏ */}
          <div className="surface-card divide-y divide-border overflow-hidden">
            {items.map((item) => {
              const book = item.book;
              const price = book?.price ?? 14.99;
              return (
                <div key={item.id} className="flex flex-col gap-4 p-4 sm:flex-row sm:items-center sm:justify-between sm:p-5">
                  <div className="flex items-start gap-4">
                    {book ? (
                      <Link to="/book/$bookId" params={{ bookId: book.id }}>
                        <BookCover book={book} className="h-24 w-16 shrink-0 rounded-lg shadow-sm" />
                      </Link>
                    ) : (
                      <div className="h-24 w-16 shrink-0 rounded-lg bg-secondary flex items-center justify-center text-xs text-muted-foreground">
                        Book
                      </div>
                    )}
                    <div className="min-w-0">
                      <Link
                        to="/book/$bookId"
                        params={{ bookId: item.book_id }}
                        className="block font-display text-base font-bold text-foreground hover:text-gold transition-colors line-clamp-1"
                      >
                        {book?.title ?? `Book #${item.book_id}`}
                      </Link>
                      <p className="text-xs text-muted-foreground line-clamp-1">{book?.author_name ?? "Author"}</p>
                      <p className="mt-2 text-sm font-semibold text-gold">{formatPrice(price)}</p>
                    </div>
                  </div>

                  {/* Cụm điều khiển số lượng & Xóa */}
                  <div className="flex items-center justify-between sm:justify-end gap-4">
                    <div className="flex items-center rounded-full border border-border bg-background p-1">
                      <button
                        type="button"
                        onClick={() => updateQtyMutation.mutate({ item, quantity: item.quantity - 1 })}
                        disabled={updateQtyMutation.isPending}
                        className="flex h-7 w-7 items-center justify-center rounded-full hover:bg-accent text-muted-foreground hover:text-foreground transition-colors"
                        aria-label="Decrease quantity"
                      >
                        <Minus className="h-3.5 w-3.5" />
                      </button>
                      <span className="w-8 text-center text-xs font-bold text-foreground">{item.quantity}</span>
                      <button
                        type="button"
                        onClick={() => updateQtyMutation.mutate({ item, quantity: item.quantity + 1 })}
                        disabled={updateQtyMutation.isPending}
                        className="flex h-7 w-7 items-center justify-center rounded-full hover:bg-accent text-muted-foreground hover:text-foreground transition-colors"
                        aria-label="Increase quantity"
                      >
                        <Plus className="h-3.5 w-3.5" />
                      </button>
                    </div>

                    <div className="text-right min-w-[70px]">
                      <span className="block text-sm font-bold text-foreground">{formatPrice(price * item.quantity)}</span>
                    </div>

                    <button
                      type="button"
                      onClick={() => removeItemMutation.mutate(item)}
                      disabled={removeItemMutation.isPending}
                      className="p-2 text-muted-foreground hover:text-destructive transition-colors"
                      aria-label="Remove item"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Tóm tắt đơn hàng (Order Summary) */}
          <div className="h-fit">
            <div className="surface-card p-6">
              <h3 className="font-display text-lg font-bold text-foreground mb-4">
                {t("cart.summary") || "Order Summary"}
              </h3>

              <div className="space-y-3 text-sm">
                <div className="flex justify-between text-muted-foreground">
                  <span>{t("cart.subtotal") || "Subtotal"}</span>
                  <span className="font-medium text-foreground">{formatPrice(subtotal)}</span>
                </div>
                <div className="flex justify-between text-muted-foreground">
                  <span>{t("cart.shipping") || "Shipping"}</span>
                  <span className="font-medium text-foreground">
                    {shipping === 0 ? <span className="text-emerald-500 font-bold">Free</span> : formatPrice(shipping)}
                  </span>
                </div>
                {subtotal < 35 && subtotal > 0 ? (
                  <p className="text-xs text-muted-foreground bg-secondary/50 p-2 rounded-lg">
                    💡 Add <span className="font-bold text-gold">{formatPrice(35 - subtotal)}</span> more for <b>FREE SHIPPING</b>!
                  </p>
                ) : null}
                <div className="border-t border-border pt-3 flex justify-between text-base font-bold text-foreground">
                  <span>{t("cart.total") || "Total"}</span>
                  <span className="text-gold text-lg">{formatPrice(total)}</span>
                </div>
              </div>

              <Button
                onClick={() => void navigate({ to: "/checkout" })}
                className="mt-6 w-full rounded-full bg-gold py-6 text-sm font-bold text-gold-foreground hover:bg-gold/90 shadow-lg shadow-gold/20 flex items-center justify-center gap-2"
              >
                <span>{t("cart.checkout") || "Proceed to Checkout"}</span>
                <ArrowRight className="h-4 w-4" />
              </Button>

              <div className="mt-4 text-center">
                <Link to="/discover" className="text-xs font-semibold text-muted-foreground hover:text-gold transition-colors">
                  ← Continue Shopping
                </Link>
              </div>
            </div>
          </div>
        </div>
      )}
    </AppShell>
  );
}
