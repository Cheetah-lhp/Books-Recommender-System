import { Link } from "@tanstack/react-router";
import { useServerFn } from "@tanstack/react-start";
import { Send, X } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import readoraOwl from "@/assets/readora-owl.png.asset.json";
import { BookCover } from "@/components/readora/BookCard";
import { LogoMark } from "@/components/readora/Logo";
import { Button } from "@/components/ui/button";
import { askReadoraAi } from "@/lib/ai.functions";
import { useI18n } from "@/lib/i18n";
import type { RecommendedBook } from "@/lib/recommend";
import { cn } from "@/lib/utils";

type Msg = { role: "user" | "assistant"; content: string };
type Turn = Msg & { books?: RecommendedBook[] };

export function Chatbot({ variant = "floating" }: { variant?: "floating" | "inline" }) {
  const { t, lang } = useI18n();
  const [open, setOpen] = useState(variant === "inline");
  const [messages, setMessages] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const ask = useServerFn(askReadoraAi);

  const suggestions = [t("chat.o1"), t("chat.o2"), t("chat.o3"), t("chat.o4"), t("chat.o5")];

  async function send(text: string) {
    const clean = text.trim();
    if (!clean || loading) return;
    const next: Turn[] = [...messages, { role: "user", content: clean }];
    setMessages(next);
    setInput("");
    setLoading(true);
    try {
      const res = await ask({ data: { messages: next.map((m) => ({ role: m.role, content: m.content })), language: lang } });
      if (!res.ok) {
        toast.error(res.error);
      } else {
        setMessages([...next, { role: "assistant", content: res.content, books: res.books as RecommendedBook[] }]);
      }
    } catch {
      toast.error("Could not reach the AI assistant.");
    } finally {
      setLoading(false);
    }
  }

  const panel = (
    <div
      className={cn(
        "flex flex-col overflow-hidden rounded-2xl border border-border bg-card shadow-float",
        variant === "floating" ? "h-[520px] w-[min(92vw,380px)]" : "h-[560px] w-full",
      )}
    >
      <div className="flex items-center gap-2 border-b border-border px-4 py-3">
        <LogoMark context="compact" className="h-6" />
        <p className="flex-1 truncate text-sm font-bold text-foreground">{t("chat.title")}</p>
        {variant === "floating" ? (
          <button onClick={() => setOpen(false)} aria-label="Close" className="text-muted-foreground">
            <X className="h-4 w-4" />
          </button>
        ) : null}
      </div>

      <div className="flex-1 space-y-3 overflow-y-auto px-4 py-4 text-sm">
        <p className="font-semibold text-foreground">{t("chat.hello")}</p>
        <p className="text-muted-foreground">{t("chat.intro")}</p>
        <p className="text-muted-foreground">{t("chat.mood")}</p>
        {messages.length === 0 ? (
          <div className="space-y-2 pt-1">
            {suggestions.map((s) => (
              <button
                key={s}
                onClick={() => void send(s)}
                className="w-full rounded-xl border border-border bg-background px-3 py-2 text-start text-sm text-foreground transition-colors hover:border-gold hover:bg-accent"
              >
                {s}
              </button>
            ))}
          </div>
        ) : null}
        {messages.map((m, i) => (
          <div key={i} className="space-y-2">
            <div className={cn("flex", m.role === "user" ? "justify-end" : "justify-start")}>
              <p
                className={cn(
                  "max-w-[85%] whitespace-pre-wrap rounded-2xl px-3 py-2",
                  m.role === "user"
                    ? "bg-gold-soft text-foreground"
                    : "bg-secondary text-secondary-foreground",
                )}
              >
                {m.content}
              </p>
            </div>
            {m.books?.length ? (
              <div className="grid grid-cols-3 gap-2">
                {m.books.slice(0, 3).map((b) => (
                  <Link
                    key={b.id}
                    to="/book/$bookId"
                    params={{ bookId: b.id }}
                    className="group block rounded-xl border border-border bg-background p-2"
                  >
                    <BookCover book={b} className="aspect-[2/3] w-full" />
                    <p className="mt-1 truncate text-[11px] font-semibold text-foreground">{b.title}</p>
                    <p className="truncate text-[10px] text-muted-foreground">{b.author_name}</p>
                  </Link>
                ))}
              </div>
            ) : null}
          </div>
        ))}
        {loading ? <p className="animate-pulse text-muted-foreground">…</p> : null}
      </div>

      <form
        className="flex items-center gap-2 border-t border-border p-3"
        onSubmit={(e) => {
          e.preventDefault();
          void send(input);
        }}
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={t("chat.ask")}
          className="h-10 min-w-0 flex-1 rounded-full border border-border bg-background px-4 text-sm outline-none focus:border-gold"
        />
        <Button type="submit" size="icon" className="h-9 w-9 shrink-0 rounded-full bg-gold text-gold-foreground hover:bg-gold/90">
          <Send className="h-4 w-4" />
        </Button>
      </form>
    </div>
  );

  if (variant === "inline") return panel;

  return (
    <div className="fixed bottom-20 end-4 z-40 flex flex-col items-end gap-3 md:bottom-6">
      {open ? panel : null}
      <button
        onClick={() => setOpen((v) => !v)}
        aria-label={t("chat.title")}
        className="group h-14 w-14 overflow-hidden rounded-full bg-primary shadow-float ring-2 ring-gold transition-transform hover:scale-105 focus:outline-none focus-visible:ring-4 focus-visible:ring-gold/50"
      >
        <img
          src={readoraOwl.url}
          alt={t("chat.title")}
          width={56}
          height={56}
          className="h-full w-full object-cover"
        />
      </button>
    </div>
  );
}
