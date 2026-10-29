import { useQuery } from "@tanstack/react-query";
import { Link, createFileRoute } from "@tanstack/react-router";
import { Calendar, CheckCircle, Clock, Package, Truck, XCircle } from "lucide-react";

import { AppShell } from "@/components/readora/AppShell";
import { BookCover, SectionHeader } from "@/components/readora/BookCard";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth";
import { fetchUserOrders, formatPrice, type Order } from "@/lib/ecommerce";
import { useI18n } from "@/lib/i18n";

export const Route = createFileRoute("/orders")({
  head: () => ({
    meta: [
      { title: "My Orders — Book Recommender System" },
      { name: "description", content: "Track your book orders and view purchase history." },
    ],
  }),
  component: OrdersPage,
});

function StatusBadge({ status }: { status: Order["status"] }) {
  switch (status) {
    case "delivered":
      return (
        <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-500/10 px-3 py-1 text-xs font-semibold text-emerald-500">
          <CheckCircle className="h-3.5 w-3.5" />
          <span>Delivered</span>
        </span>
      );
    case "shipped":
      return (
        <span className="inline-flex items-center gap-1.5 rounded-full bg-blue-500/10 px-3 py-1 text-xs font-semibold text-blue-500">
          <Truck className="h-3.5 w-3.5" />
          <span>Shipped</span>
        </span>
      );
    case "processing":
      return (
        <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-500/10 px-3 py-1 text-xs font-semibold text-amber-500">
          <Package className="h-3.5 w-3.5" />
          <span>Processing</span>
        </span>
      );
    case "cancelled":
      return (
        <span className="inline-flex items-center gap-1.5 rounded-full bg-rose-500/10 px-3 py-1 text-xs font-semibold text-rose-500">
          <XCircle className="h-3.5 w-3.5" />
          <span>Cancelled</span>
        </span>
      );
    case "pending":
    default:
      return (
        <span className="inline-flex items-center gap-1.5 rounded-full bg-gold/10 px-3 py-1 text-xs font-semibold text-gold">
          <Clock className="h-3.5 w-3.5" />
          <span>Pending Confirmation</span>
        </span>
      );
  }
}

function OrdersPage() {
  const { t } = useI18n();
  const { user } = useAuth();

  const { data: orders = [], isLoading } = useQuery({
    queryKey: ["orders", user?.id],
    queryFn: () => (user ? fetchUserOrders(user.id) : Promise.resolve([])),
    enabled: !!user,
  });

  if (!user) {
    return (
      <AppShell>
        <div className="surface-card mx-auto max-w-md p-8 text-center my-8">
          <Package className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
          <h2 className="font-display text-xl font-bold text-foreground">Sign in to view orders</h2>
          <p className="mt-2 text-sm text-muted-foreground">
            Please log in to your account to view your past orders and track current deliveries.
          </p>
          <Button asChild className="mt-6 rounded-full bg-gold text-gold-foreground hover:bg-gold/90">
            <Link to="/login">Sign In</Link>
          </Button>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <SectionHeader
        title={t("orders.title") || "Order History"}
        subtitle="Track your book orders and view receipts"
      />

      {isLoading ? (
        <div className="surface-card p-12 text-center text-muted-foreground">
          <p className="animate-pulse">Loading your orders...</p>
        </div>
      ) : orders.length === 0 ? (
        <div className="surface-card flex flex-col items-center justify-center p-12 text-center">
          <div className="flex h-20 w-20 items-center justify-center rounded-full bg-secondary/80 text-muted-foreground mb-4">
            <Package className="h-10 w-10 text-gold" />
          </div>
          <h3 className="font-display text-xl font-bold text-foreground">No orders yet</h3>
          <p className="mt-2 max-w-md text-sm text-muted-foreground">
            You haven't placed any book orders yet. Browse our store to find captivating reads!
          </p>
          <Button asChild className="mt-6 rounded-full bg-gold px-6 text-gold-foreground hover:bg-gold/90">
            <Link to="/discover">Explore Books</Link>
          </Button>
        </div>
      ) : (
        <div className="space-y-6">
          {orders.map((order) => (
            <div key={order.id} className="surface-card overflow-hidden">
              {/* Header đơn hàng */}
              <div className="flex flex-wrap items-center justify-between gap-4 border-b border-border bg-secondary/30 p-4 sm:px-6">
                <div className="flex flex-wrap items-center gap-4 text-xs text-muted-foreground">
                  <div>
                    <span className="block font-semibold uppercase tracking-wider text-[10px]">Order ID</span>
                    <span className="font-mono text-foreground">{order.id.slice(0, 8)}...</span>
                  </div>
                  <div>
                    <span className="block font-semibold uppercase tracking-wider text-[10px]">Date Placed</span>
                    <span className="flex items-center gap-1 text-foreground">
                      <Calendar className="h-3 w-3 text-gold" />
                      {new Date(order.created_at).toLocaleDateString("en-US", {
                        year: "numeric",
                        month: "short",
                        day: "numeric",
                      })}
                    </span>
                  </div>
                  <div>
                    <span className="block font-semibold uppercase tracking-wider text-[10px]">Total Amount</span>
                    <span className="font-bold text-gold text-sm">{formatPrice(order.total_amount)}</span>
                  </div>
                </div>

                <StatusBadge status={order.status} />
              </div>

              {/* Chi tiết người nhận & sách */}
              <div className="p-4 sm:p-6">
                <div className="text-xs text-muted-foreground mb-4 bg-background/50 p-3 rounded-lg border border-border">
                  <span className="font-semibold text-foreground">Shipping Details:</span> {order.shipping_address}
                </div>

                <div className="divide-y divide-border">
                  {order.items?.map((item) => {
                    const book = item.book;
                    return (
                      <div key={item.id} className="py-3 first:pt-0 last:pb-0 flex items-center justify-between gap-4">
                        <div className="flex items-center gap-3">
                          {book ? (
                            <Link to="/book/$bookId" params={{ bookId: book.id }}>
                              <BookCover book={book} className="h-16 w-11 shrink-0 rounded shadow-sm" />
                            </Link>
                          ) : (
                            <div className="h-16 w-11 shrink-0 rounded bg-secondary flex items-center justify-center text-xs">
                              Book
                            </div>
                          )}
                          <div className="min-w-0">
                            <Link
                              to="/book/$bookId"
                              params={{ bookId: item.book_id }}
                              className="font-display text-sm font-bold text-foreground hover:text-gold transition-colors line-clamp-1"
                            >
                              {book?.title ?? `Book #${item.book_id}`}
                            </Link>
                            <p className="text-xs text-muted-foreground">{book?.author_name ?? "Author"}</p>
                            <p className="text-xs text-muted-foreground mt-1">Quantity: {item.quantity}</p>
                          </div>
                        </div>

                        <div className="text-right">
                          <span className="text-sm font-bold text-foreground">
                            {formatPrice(item.price_at_purchase * item.quantity)}
                          </span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </AppShell>
  );
}
