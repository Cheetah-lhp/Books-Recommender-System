import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, createFileRoute, useNavigate } from "@tanstack/react-router";
import { CheckCircle2, CreditCard, DollarSign, Lock, ShieldCheck, Truck } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { AppShell } from "@/components/readora/AppShell";
import { BookCover, SectionHeader } from "@/components/readora/BookCard";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/lib/auth";
import { createOrder, fetchUserCart, formatPrice } from "@/lib/ecommerce";
import { useI18n } from "@/lib/i18n";

export const Route = createFileRoute("/checkout")({
  head: () => ({
    meta: [
      { title: "Checkout — Book Recommender System" },
      { name: "description", content: "Complete your book order securely." },
    ],
  }),
  component: CheckoutPage,
});

function CheckoutPage() {
  const { t } = useI18n();
  const { user, profile } = useAuth();
  const navigate = useNavigate();
  const qc = useQueryClient();

  const [fullName, setFullName] = useState(profile?.full_name ?? "");
  const [address, setAddress] = useState("");
  const [city, setCity] = useState("Hanoi");
  const [phone, setPhone] = useState("");
  const [paymentMethod, setPaymentMethod] = useState<"cod" | "card">("cod");

  const { data: items = [], isLoading } = useQuery({
    queryKey: ["cart", user?.id],
    queryFn: () => fetchUserCart(user?.id ?? null),
  });

  const subtotal = items.reduce((acc, item) => {
    const price = item.book?.price ?? 14.99;
    return acc + price * item.quantity;
  }, 0);

  const shipping = subtotal > 35 || subtotal === 0 ? 0 : 4.99;
  const total = subtotal + shipping;

  const orderMutation = useMutation({
    mutationFn: async () => {
      if (!user) throw new Error("Please log in to place an order");
      if (!address.trim()) throw new Error("Please enter your delivery address");
      if (!phone.trim()) throw new Error("Please enter your phone number");

      const shippingAddress = `${fullName} | ${phone} | ${address}, ${city} (Payment: ${paymentMethod.toUpperCase()})`;
      return await createOrder({
        userId: user.id,
        items,
        shippingAddress,
        totalAmount: total,
      });
    },
    onSuccess: (order) => {
      toast.success(t("checkout.success") || "Order placed successfully!");
      void qc.invalidateQueries({ queryKey: ["cart"] });
      void qc.invalidateQueries({ queryKey: ["orders"] });
      void navigate({ to: "/orders" });
    },
    onError: (err: any) => {
      toast.error(err?.message || "Failed to place order");
    },
  });

  if (!user) {
    return (
      <AppShell>
        <div className="surface-card mx-auto max-w-md p-8 text-center my-8">
          <div className="flex h-16 w-16 items-center justify-center rounded-full bg-gold/10 text-gold mx-auto mb-4">
            <Lock className="h-8 w-8" />
          </div>
          <h2 className="font-display text-xl font-bold text-foreground">Sign in to Checkout</h2>
          <p className="mt-2 text-sm text-muted-foreground">
            Please log in or create an account to complete your book purchase and track your deliveries.
          </p>
          <div className="mt-6 flex flex-col gap-3">
            <Button asChild className="rounded-full bg-gold text-gold-foreground hover:bg-gold/90">
              <Link to="/login">Sign In</Link>
            </Button>
            <Button asChild variant="outline" className="rounded-full">
              <Link to="/signup">Create Account</Link>
            </Button>
          </div>
        </div>
      </AppShell>
    );
  }

  if (!isLoading && items.length === 0) {
    return (
      <AppShell>
        <div className="surface-card mx-auto max-w-md p-8 text-center my-8">
          <h2 className="font-display text-xl font-bold text-foreground">No items to checkout</h2>
          <p className="mt-2 text-sm text-muted-foreground">Your cart is currently empty.</p>
          <Button asChild className="mt-6 rounded-full bg-gold text-gold-foreground hover:bg-gold/90">
            <Link to="/discover">Explore Books</Link>
          </Button>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <SectionHeader
        title={t("checkout.title") || "Checkout"}
        subtitle="Review your order and provide delivery information"
      />

      <div className="grid gap-8 lg:grid-cols-[1fr_400px]">
        {/* Form giao hàng & thanh toán */}
        <div className="space-y-6">
          {/* Thông tin người nhận */}
          <div className="surface-card p-6">
            <div className="flex items-center gap-2 mb-4">
              <Truck className="h-5 w-5 text-gold" />
              <h3 className="font-display text-lg font-bold text-foreground">Shipping Information</h3>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div className="sm:col-span-2">
                <Label htmlFor="fullName" className="text-xs font-semibold text-muted-foreground">
                  Recipient Name
                </Label>
                <Input
                  id="fullName"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder="e.g. John Doe"
                  className="mt-1"
                />
              </div>

              <div>
                <Label htmlFor="phone" className="text-xs font-semibold text-muted-foreground">
                  Phone Number
                </Label>
                <Input
                  id="phone"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  placeholder="e.g. 0912 345 678"
                  className="mt-1"
                />
              </div>

              <div>
                <Label htmlFor="city" className="text-xs font-semibold text-muted-foreground">
                  City / Province
                </Label>
                <Input
                  id="city"
                  value={city}
                  onChange={(e) => setCity(e.target.value)}
                  placeholder="e.g. Hanoi"
                  className="mt-1"
                />
              </div>

              <div className="sm:col-span-2">
                <Label htmlFor="address" className="text-xs font-semibold text-muted-foreground">
                  Delivery Address
                </Label>
                <Input
                  id="address"
                  value={address}
                  onChange={(e) => setAddress(e.target.value)}
                  placeholder="e.g. 123 Nguyen Trai, Thanh Xuan"
                  className="mt-1"
                />
              </div>
            </div>
          </div>

          {/* Phương thức thanh toán */}
          <div className="surface-card p-6">
            <div className="flex items-center gap-2 mb-4">
              <CreditCard className="h-5 w-5 text-gold" />
              <h3 className="font-display text-lg font-bold text-foreground">Payment Method</h3>
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <div
                onClick={() => setPaymentMethod("cod")}
                className={`flex cursor-pointer items-center gap-3 rounded-xl border p-4 transition-all ${
                  paymentMethod === "cod"
                    ? "border-gold bg-gold/10 text-foreground"
                    : "border-border bg-card hover:border-gold/50 text-muted-foreground"
                }`}
              >
                <DollarSign className={`h-5 w-5 ${paymentMethod === "cod" ? "text-gold" : ""}`} />
                <div>
                  <p className="text-sm font-bold text-foreground">Cash on Delivery (COD)</p>
                  <p className="text-xs text-muted-foreground">Pay when your books arrive</p>
                </div>
              </div>

              <div
                onClick={() => setPaymentMethod("card")}
                className={`flex cursor-pointer items-center gap-3 rounded-xl border p-4 transition-all ${
                  paymentMethod === "card"
                    ? "border-gold bg-gold/10 text-foreground"
                    : "border-border bg-card hover:border-gold/50 text-muted-foreground"
                }`}
              >
                <CreditCard className={`h-5 w-5 ${paymentMethod === "card" ? "text-gold" : ""}`} />
                <div>
                  <p className="text-sm font-bold text-foreground">Credit / Debit Card</p>
                  <p className="text-xs text-muted-foreground">Visa, MasterCard, JCB (Demo)</p>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Cột tóm tắt đơn hàng */}
        <div>
          <div className="surface-card p-6 sticky top-24">
            <h3 className="font-display text-lg font-bold text-foreground mb-4">Order Summary</h3>

            {/* List preview sách */}
            <div className="max-h-60 overflow-y-auto space-y-3 pr-2 divide-y divide-border">
              {items.map((it) => (
                <div key={it.id} className="pt-3 first:pt-0 flex items-center justify-between gap-3 text-sm">
                  <div className="flex items-center gap-2 min-w-0">
                    {it.book ? <BookCover book={it.book} className="h-12 w-8 shrink-0 rounded" /> : null}
                    <div className="min-w-0">
                      <p className="font-medium text-foreground truncate text-xs">{it.book?.title}</p>
                      <p className="text-[11px] text-muted-foreground">Qty: {it.quantity}</p>
                    </div>
                  </div>
                  <span className="text-xs font-bold text-foreground shrink-0">
                    {formatPrice((it.book?.price ?? 14.99) * it.quantity)}
                  </span>
                </div>
              ))}
            </div>

            <div className="mt-6 border-t border-border pt-4 space-y-2 text-sm">
              <div className="flex justify-between text-muted-foreground">
                <span>Subtotal</span>
                <span className="font-medium text-foreground">{formatPrice(subtotal)}</span>
              </div>
              <div className="flex justify-between text-muted-foreground">
                <span>Shipping</span>
                <span className="font-medium text-foreground">
                  {shipping === 0 ? <span className="text-emerald-500 font-bold">Free</span> : formatPrice(shipping)}
                </span>
              </div>
              <div className="border-t border-border pt-3 flex justify-between text-base font-bold text-foreground">
                <span>Total Due</span>
                <span className="text-gold text-xl">{formatPrice(total)}</span>
              </div>
            </div>

            <Button
              onClick={() => orderMutation.mutate()}
              disabled={orderMutation.isPending}
              className="mt-6 w-full rounded-full bg-gold py-6 text-sm font-bold text-gold-foreground hover:bg-gold/90 shadow-lg shadow-gold/20 flex items-center justify-center gap-2"
            >
              <CheckCircle2 className="h-4 w-4" />
              <span>{orderMutation.isPending ? "Placing Order..." : "Confirm & Place Order"}</span>
            </Button>

            <div className="mt-4 flex items-center justify-center gap-1.5 text-xs text-muted-foreground">
              <ShieldCheck className="h-4 w-4 text-emerald-500" />
              <span>Safe & Secure 256-bit SSL Checkout</span>
            </div>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
