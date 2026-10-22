import { Star } from "lucide-react";

import { cn } from "@/lib/utils";

export function Rating({ value, className }: { value: number; className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-1 text-sm font-semibold text-foreground", className)}>
      <Star className="h-4 w-4 fill-gold text-gold" />
      {Number(value).toFixed(1)}
    </span>
  );
}

export function Stars({ value, size = 14 }: { value: number; size?: number }) {
  return (
    <span className="inline-flex items-center gap-0.5">
      {[1, 2, 3, 4, 5].map((i) => (
        <Star
          key={i}
          style={{ width: size, height: size }}
          className={i <= Math.round(value) ? "fill-gold text-gold" : "text-border"}
        />
      ))}
    </span>
  );
}
