import { Link } from "@tanstack/react-router";
import { BookOpen } from "lucide-react";

import { Rating } from "@/components/readora/Rating";
import type { Book } from "@/lib/data";
import { cn } from "@/lib/utils";

export function BookCover({ book, className }: { book: Pick<Book, "title" | "cover_url">; className?: string }) {
  return (
    <div
      className={cn(
        "relative overflow-hidden rounded-xl border border-border bg-secondary shadow-card",
        className,
      )}
    >
      {book.cover_url ? (
        <img
          src={book.cover_url}
          alt={book.title}
          loading="lazy"
          className="h-full w-full object-cover"
        />
      ) : (
        <span className="flex h-full w-full items-center justify-center text-muted-foreground">
          <BookOpen className="h-6 w-6" />
        </span>
      )}
    </div>
  );
}

export function BookCard({ book, className }: { book: Book; className?: string }) {
  const price = book.price && book.price > 0 ? book.price : Number((((Number(book.id) * 37) % 30) + 9.99).toFixed(2));
  return (
    <Link
      to="/book/$bookId"
      params={{ bookId: book.id }}
      className={cn("group block", className)}
    >
      <div className="relative">
        <BookCover book={book} className="aspect-[2/3] w-full transition-transform group-hover:-translate-y-1" />
        <span className="absolute bottom-2 end-2 rounded-md bg-card/90 px-1.5 py-0.5 text-[11px] font-bold text-gold backdrop-blur border border-gold/20 shadow-sm">
          ${price.toFixed(2)}
        </span>
      </div>
      <p className="mt-3 truncate text-sm font-bold text-foreground">{book.title}</p>
      <p className="truncate text-xs text-muted-foreground">{book.author_name}</p>
      <Rating value={book.rating} className="mt-1 text-xs" />
    </Link>
  );
}

export function SectionHeader({
  title,
  subtitle,
  action,
}: {
  title: string;
  subtitle?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="mb-4 grid grid-cols-[minmax(0,1fr)_auto] items-center gap-3">
      <div className="min-w-0">
        <h2 className="truncate font-display text-xl font-bold text-foreground sm:text-2xl">{title}</h2>
        {subtitle ? <p className="truncate text-sm text-muted-foreground">{subtitle}</p> : null}
      </div>
      {action}
    </div>
  );
}
