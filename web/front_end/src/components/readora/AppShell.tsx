import { Link } from "@tanstack/react-router";
import { lazy, Suspense, useState, type ReactNode } from "react";
import { MessageCircle } from "lucide-react";

import { Header } from "@/components/readora/Header";
import { DesktopSidebar, NAV_ITEMS, useActivePath } from "@/components/readora/Sidebar";
import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";

const Chatbot = lazy(() =>
  import("@/components/readora/Chatbot").then((module) => ({ default: module.Chatbot })),
);

function LazyChatbot() {
  const { t } = useI18n();
  const [loaded, setLoaded] = useState(false);
  const launcher = (
    <button
      onClick={() => setLoaded(true)}
      aria-label={t("chat.title")}
      className="group flex h-14 w-14 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-float ring-2 ring-gold transition-transform hover:scale-105 focus:outline-none focus-visible:ring-4 focus-visible:ring-gold/50"
    >
      <MessageCircle className="h-6 w-6" />
    </button>
  );

  return (
    <div className="fixed bottom-20 end-4 z-40 md:bottom-6">
      {loaded ? (
        <Suspense fallback={launcher}>
          <Chatbot initiallyOpen />
        </Suspense>
      ) : (
        launcher
      )}
    </div>
  );
}

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
      <LazyChatbot />
    </div>
  );
}
