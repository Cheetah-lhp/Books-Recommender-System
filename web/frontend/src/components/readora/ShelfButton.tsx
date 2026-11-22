import { Check, ChevronDown } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { SHELF_LABELS, SHELF_STATUSES, type ShelfStatus } from "@/lib/library";
import { cn } from "@/lib/utils";

export function ShelfButton({
  status,
  disabled,
  onChange,
  className,
  compact,
}: {
  status: ShelfStatus | null;
  disabled?: boolean;
  onChange: (status: ShelfStatus) => void;
  className?: string;
  compact?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const label = status ? SHELF_LABELS[status] : "Want to Read";

  return (
    <div className={cn("relative inline-flex", className)}>
      <Button
        type="button"
        disabled={disabled}
        onClick={() => {
          // #region agent log
          fetch("http://127.0.0.1:7460/ingest/b819d754-3046-494d-a58c-7e31ffe6c52a", {
            method: "POST",
            headers: { "Content-Type": "application/json", "X-Debug-Session-Id": "829bc3" },
            body: JSON.stringify({
              sessionId: "829bc3",
              runId: "pre-fix",
              hypothesisId: "B",
              location: "ShelfButton.tsx:onClick",
              message: "ShelfButton main click",
              data: { status, willOpenMenu: Boolean(status), disabled: Boolean(disabled) },
              timestamp: Date.now(),
            }),
          }).catch(() => {});
          // #endregion
          if (status) {
            setOpen((v) => !v);
            return;
          }
          onChange("want");
        }}
        className={cn(
          "rounded-full font-semibold",
          status
            ? "bg-emerald-600 text-white hover:bg-emerald-600/90"
            : "bg-primary text-primary-foreground hover:bg-primary/90",
          compact ? "h-8 px-3 text-xs" : "h-9 px-4 text-sm",
        )}
      >
        {status ? <Check className="me-1.5 h-3.5 w-3.5" /> : null}
        {label}
        <ChevronDown className="ms-1.5 h-3.5 w-3.5 opacity-80" />
      </Button>
      {open ? (
        <div className="absolute start-0 top-full z-20 mt-1 min-w-[11rem] overflow-hidden rounded-xl border border-border bg-card shadow-lg">
          {SHELF_STATUSES.map((s) => (
            <button
              key={s}
              type="button"
              className={cn(
                "flex w-full items-center px-3 py-2 text-start text-sm hover:bg-accent",
                status === s && "bg-accent font-semibold",
              )}
              onClick={() => {
                onChange(s);
                setOpen(false);
              }}
            >
              {SHELF_LABELS[s]}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}
