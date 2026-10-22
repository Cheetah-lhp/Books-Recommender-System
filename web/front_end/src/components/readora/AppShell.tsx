import { Link } from "@tanstack/react-router";
import type { ReactNode } from "react";

import { Chatbot } from "@/components/readora/Chatbot";
import { Header } from "@/components/readora/Header";
import { DesktopSidebar, NAV_ITEMS, useActivePath } from "@/components/readora/Sidebar";
import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";

function MobileTabBar() {
  const path = useActivePath();
  const { t } = useI18n();
  const items = NAV_ITEMS.slice(0, 5);
  return (
    <nav className="fixed inset-x-0 bottom-0 z-30 grid grid-cols-5 border-t border-border bg-card px-1 py-1.5 md:hidden">
      {items.map((item) => {
        const active = item.to === "/" ? path === "/" : path.startsWith(item.to);
        return (
          <Link
            key={item.to}
            to={item.to}
            className={cn(
              "flex flex-col items-center gap-0.5 rounded-lg py-1 text-[10px] font-medium text-muted-foreground",
              active && "text-gold",
            )}
          >
            <item.icon className="h-5 w-5" />
            <span className="truncate">{t(item.label)}</span>
          </Link>
        );
      })}
    </nav>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen w-full bg-background">
      <DesktopSidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <Header />
        <main className="mx-auto w-full max-w-[1240px] flex-1 px-3 pb-24 pt-5 sm:px-6 md:pb-10">{children}</main>
      </div>
      <MobileTabBar />
      <Chatbot />
    </div>
  );
}
