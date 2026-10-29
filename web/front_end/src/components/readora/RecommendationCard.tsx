import { Link } from "@tanstack/react-router";
import { EyeOff, Sparkles, ThumbsDown, ThumbsUp } from "lucide-react";
import { useState } from "react";

import { BookCover } from "@/components/readora/BookCard";
import { Rating } from "@/components/readora/Rating";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth";
import { FEEDBACK_REASONS } from "@/lib/preferences";
import { useNotInterested, useRecommendationFeedback, type RecommendedBook } from "@/lib/recommend";
import { cn } from "@/lib/utils";

/** Book card with an explanation line and feedback actions. */
export function RecommendationCard({ book, className }: { book: RecommendedBook; className?: string }) {
  const { user } = useAuth();
  const feedback = useRecommendationFeedback(user?.id ?? null);
  const hide = useNotInterested(user?.id ?? null);
  const [askReason, setAskReason] = useState(false);
  const [done, setDone] = useState<"good" | "not_for_me" | null>(null);

  if (done === "not_for_me") {
    return (
      <div className={cn("flex h-full flex-col items-center justify-center rounded-2xl border border-border bg-card/60 p-4 text-center", className)}>
        <p className="text-xs text-muted-foreground">Removed from your recommendations.</p>
      </div>
    );
  }

  return (
    <div className={cn("flex h-full flex-col", className)}>
      <Link to="/book/$bookId" params={{ bookId: book.id }} className="group block">
        <BookCover book={book} className="aspect-[2/3] w-full transition-transform group-hover:-translate-y-1" />
        <p className="mt-3 truncate text-sm font-bold text-foreground">{book.title}</p>
        <p className="truncate text-xs text-muted-foreground">{book.author_name}</p>
        <Rating value={book.rating} className="mt-1 text-xs" />
      </Link>

      <p className="mt-2 flex items-start gap-1.5 rounded-xl border border-gold/40 bg-gold/10 px-2.5 py-2 text-[11px] leading-snug text-foreground/85">
        <Sparkles className="mt-0.5 h-3 w-3 shrink-0 text-gold" />
        <span>{book.why}</span>
      </p>

      {askReason ? (
        <div className="mt-2 space-y-1">
          {FEEDBACK_REASONS.map((reason) => (
            <button
              key={reason}
              onClick={() => {
                feedback.mutate({ bookId: book.id, feedback: "not_for_me", reason });
                hide.mutate(book.id);
                setDone("not_for_me");
              }}
              className="w-full rounded-lg border border-border px-2 py-1 text-[11px] text-foreground hover:border-gold"
            >
              {reason}
            </button>
          ))}
        </div>
      ) : (
        <div className="mt-2 flex items-center gap-1.5">
          <Button
            size="sm"
            variant={done === "good" ? "default" : "outline"}
            className="h-8 flex-1 rounded-full px-2 text-[11px]"
            onClick={() => {
              feedback.mutate({ bookId: book.id, feedback: "good" });
              setDone("good");
            }}
          >
            <ThumbsUp className="mr-1 h-3 w-3" /> Good
          </Button>
          <Button
            size="sm"
            variant="outline"
            className="h-8 flex-1 rounded-full px-2 text-[11px]"
            onClick={() => setAskReason(true)}
          >
            <ThumbsDown className="mr-1 h-3 w-3" /> Not for me
          </Button>
          <Button
            size="icon"
            variant="ghost"
            aria-label="Not interested"
            className="h-8 w-8 shrink-0"
            onClick={() => {
              hide.mutate(book.id);
              setDone("not_for_me");
            }}
          >
            <EyeOff className="h-3.5 w-3.5" />
          </Button>
        </div>
      )}
    </div>
  );
}
