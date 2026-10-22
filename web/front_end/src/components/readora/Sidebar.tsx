import { Link, useRouterState } from "@tanstack/react-router";
import { Compass, Heart, Home, LogOut, Package, Settings, ShoppingBag, Star, User, Users } from "lucide-react";

import { LogoMark } from "@/components/readora/Logo";
import { useAuth } from "@/lib/auth";
import { useI18n, type TKey } from "@/lib/i18n";
import { cn } from "@/lib/utils";

export const NAV_ITEMS = [
  { to: "/", label: "nav.home" as TKey, icon: Home },
  { to: "/discover", label: "nav.discover" as TKey, icon: Compass },
  { to: "/cart", label: "nav.cart" as TKey, icon: ShoppingBag },
  { to: "/wishlist", label: "nav.wishlist" as TKey, icon: Heart },
  { to: "/orders", label: "nav.orders" as TKey, icon: Package },
  { to: "/community", label: "nav.community" as TKey, icon: Users },
  { to: "/top-rated", label: "nav.topRated" as TKey, icon: Star },
  { to: "/profile", label: "nav.profile" as TKey, icon: User },
  { to: "/settings", label: "nav.settings" as TKey, icon: Settings },
];

export function useActivePath() {
  return useRouterState({ select: (s) => s.location.pathname });
}

export function SidebarNav({ onNavigate }: { onNavigate?: () => void }) {
  const path = useActivePath();
  const { t } = useI18n();
  const { user, signOut } = useAuth();

  const isActive = (to: string) => (to === "/" ? path === "/" : path.startsWith(to));

  return (
    <nav className="flex w-full flex-col gap-1 px-2">
      {NAV_ITEMS.map((item) => (
        <Link
          key={item.to}
          to={item.to}
          onClick={onNavigate}
          className={cn(
            "flex flex-col items-center gap-1 rounded-xl px-2 py-3 text-[11px] font-medium text-sidebar-foreground/75 transition-colors hover:bg-sidebar-accent hover:text-sidebar-accent-foreground lg:flex-row lg:gap-3 lg:px-3 lg:text-sm",
            isActive(item.to) && "bg-sidebar-accent text-sidebar-accent-foreground",
          )}
        >
          <item.icon className={cn("h-5 w-5 shrink-0", isActive(item.to) && "text-gold dark:text-sidebar-accent-foreground")} />
          <span className="truncate">{t(item.label)}</span>
        </Link>
      ))}
      {user ? (
        <button
          onClick={() => {
            onNavigate?.();
            void signOut();
          }}
          className="mt-1 flex flex-col items-center gap-1 rounded-xl px-2 py-3 text-[11px] font-medium text-sidebar-foreground/75 transition-colors hover:bg-sidebar-accent hover:text-sidebar-accent-foreground lg:flex-row lg:gap-3 lg:px-3 lg:text-sm"
        >
          <LogOut className="h-5 w-5 shrink-0" />
          <span className="truncate">{t("nav.logout")}</span>
        </button>
      ) : null}
    </nav>
  );
}

export function DesktopSidebar() {
  return (
    <aside className="sticky top-0 hidden h-screen w-[92px] shrink-0 flex-col items-center gap-6 rounded-e-[28px] bg-sidebar py-5 text-sidebar-foreground md:flex lg:w-[208px] lg:items-stretch lg:px-2">
      <Link to="/" className="flex items-center justify-center px-2 lg:justify-start">
        <LogoMark context="sidebar" className="h-12 lg:h-14" />
      </Link>
      <SidebarNav />
    </aside>
  );
}
