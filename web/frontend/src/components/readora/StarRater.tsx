import { Star } from "lucide-react";
import { useState } from "react";

import { cn } from "@/lib/utils";

export function StarRater({
  value,
  onChange,
  disabled,
  size = 20,
  showLabel = true,
}: {
  value: number | null;
  onChange: (rating: number) => void;
  disabled?: boolean;
  size?: number;
  showLabel?: boolean;
}) {
  const [hover, setHover] = useState(0);
  const active = hover || value || 0;

  return (
    <div className="flex flex-col items-start gap-0.5">
      <div
        className="inline-flex items-center gap-0.5"
        onMouseLeave={() => setHover(0)}
        role="radiogroup"
        aria-label="Rate this book"
      >
        {[1, 2, 3, 4, 5].map((n) => (
          <button
            key={n}
            type="button"
            disabled={disabled}
            aria-label={`${n} stars`}
            aria-checked={value === n}
            role="radio"
            onMouseEnter={() => setHover(n)}
            onClick={() => onChange(n)}
            className="p-0.5 disabled:opacity-50"
          >
            <Star
              style={{ width: size, height: size }}
              className={cn(n <= active ? "fill-gold text-gold" : "text-border")}
            />
          </button>
        ))}
      </div>
      {showLabel ? (
        <span className="text-[11px] text-muted-foreground">
          {value ? `Your rating: ${value}` : "Rate this book"}
        </span>
      ) : null}
    </div>
  );
}
