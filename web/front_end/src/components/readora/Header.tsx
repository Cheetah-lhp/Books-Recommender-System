import { Link, useNavigate } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { Heart, Menu, Moon, Package, Search, ShoppingBag, Sun } from "lucide-react";
import { useEffect, useState } from "react";

import { LogoLockup } from "@/components/readora/Logo";
import { SidebarNav } from "@/components/readora/Sidebar";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { useAuth } from "@/lib/auth";
import { fetchUserCart } from "@/lib/ecommerce";
import { useI18n } from "@/lib/i18n";
import { useTheme } from "@/lib/theme";

export function Header() {
  const { t, lang, setLang } = useI18n();
  const { theme, toggle } = useTheme();
  const { user, profile, isAdmin } = useAuth();
  const navigate = useNavigate();
  const [term, setTerm] = useState("");
  const [open, setOpen] = useState(false);
  const [localTick, setLocalTick] = useState(0);

  useEffect(() => {
    const handleCartUpdate = () => setLocalTick((p) => p + 1);
    window.addEventListener("cart_updated", handleCartUpdate);
    return () => window.removeEventListener("cart_updated", handleCartUpdate);
  }, []);

  const { data: cartItems = [] } = useQuery({
    queryKey: ["cart", user?.id, localTick],
    queryFn: () => fetchUserCart(user?.id ?? null),
  });

  const cartCount = cartItems.reduce((sum, item) => sum + item.quantity, 0);

  return (
    <header className="sticky top-0 z-30 flex items-center gap-3 border-b border-border bg-card/95 px-3 py-3 backdrop-blur sm:px-5">
      <Sheet open={open} onOpenChange={setOpen}>
        <SheetTrigger asChild className="md:hidden">
          <Button variant="ghost" size="icon" aria-label="Menu">
            <Menu className="h-5 w-5" />
          </Button>
        </SheetTrigger>
        <SheetContent side="left" className="w-64 bg-sidebar p-0 pt-12 text-sidebar-foreground">
          <SheetTitle className="sr-only">READORA</SheetTitle>
          <div className="px-4 pb-4">
            <LogoLockup context="drawer" />
          </div>
          <div className="[&_a]:flex-row [&_a]:gap-3 [&_a]:px-3 [&_a]:text-sm [&_button]:flex-row [&_button]:gap-3 [&_button]:px-3 [&_button]:text-sm">
            <SidebarNav onNavigate={() => setOpen(false)} />
          </div>
        </SheetContent>
      </Sheet>

      <Link to="/" className="shrink-0">
        <LogoLockup context="header" />
      </Link>

      <form
        className="relative min-w-0 flex-1"
        onSubmit={(e) => {
          e.preventDefault();
          if (term.trim()) void navigate({ to: "/search", search: { q: term.trim() } });
        }}
      >
        <Search className="pointer-events-none absolute start-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <input
          value={term}
          onChange={(e) => setTerm(e.target.value)}
          placeholder={t("action.search")}
          className="h-10 w-full rounded-full border border-border bg-background ps-9 pe-4 text-sm text-foreground outline-none placeholder:text-muted-foreground focus:border-gold"
        />
      </form>

      <select
        value={lang}
        onChange={(e) => setLang(e.target.value as "en" | "ar")}
        aria-label="Language"
        className="hidden h-9 rounded-full border border-border bg-background px-2 text-xs font-semibold text-foreground outline-none sm:block"
      >
        <option value="en">EN</option>
        <option value="ar">AR</option>
      </select>

      <Button variant="ghost" size="icon" aria-label="Toggle theme" onClick={toggle}>
        {theme === "dark" ? <Sun className="h-5 w-5 text-gold" /> : <Moon className="h-5 w-5 text-gold" />}
      </Button>

      {/* Wishlist Button */}
      <Button asChild variant="ghost" size="icon" aria-label="Wishlist" className="relative">
        <Link to="/wishlist">
          <Heart className="h-5 w-5 text-foreground hover:text-rose-500 transition-colors" />
        </Link>
      </Button>

      {/* Cart Button with Count Badge */}
      <Button asChild variant="ghost" size="icon" aria-label="Cart" className="relative">
        <Link to="/cart">
          <ShoppingBag className="h-5 w-5 text-foreground hover:text-gold transition-colors" />
          {cartCount > 0 ? (
            <span className="absolute -top-1 -right-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-gold px-1 text-[10px] font-bold text-gold-foreground">
              {cartCount > 99 ? "99+" : cartCount}
            </span>
          ) : null}
        </Link>
      </Button>

      {user ? (
        <div className="flex shrink-0 items-center gap-2">
          {isAdmin ? (
            <Button asChild variant="outline" size="sm" className="hidden lg:inline-flex">
              <Link to="/admin">{t("nav.admin")}</Link>
            </Button>
          ) : null}
          <Link to="/profile">
            <Avatar className="h-9 w-9 border border-gold">
              <AvatarImage src={profile?.avatar_url ?? undefined} alt={profile?.full_name ?? "Profile"} />
              <AvatarFallback className="bg-primary text-xs text-primary-foreground">
                {(profile?.full_name ?? "R").slice(0, 2).toUpperCase()}
              </AvatarFallback>
            </Avatar>
          </Link>
        </div>
      ) : (
        <div className="flex shrink-0 items-center gap-2">
          <Button asChild variant="outline" size="sm" className="hidden sm:inline-flex">
            <Link to="/login">{t("action.login")}</Link>
          </Button>
          <Button asChild size="sm" className="bg-gold text-gold-foreground hover:bg-gold/90">
            <Link to="/signup">{t("action.signup")}</Link>
          </Button>
        </div>
      )}
    </header>
  );
}
