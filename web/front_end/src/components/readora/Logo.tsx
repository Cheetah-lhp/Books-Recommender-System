import { cn } from "@/lib/utils";

export type LogoContext = "header" | "sidebar" | "drawer" | "auth" | "compact";

const PLATE: Record<LogoContext, string> = {
  header: "bg-[var(--logo-plate-header)] ring-[var(--logo-ring-header)]",
  sidebar: "bg-[var(--logo-plate-sidebar)] ring-[var(--logo-ring-sidebar)]",
  drawer: "bg-[var(--logo-plate-drawer)] ring-[var(--logo-ring-drawer)]",
  auth: "bg-[var(--logo-plate-auth)] ring-[var(--logo-ring-auth)]",
  compact: "bg-[var(--logo-plate-sidebar)] ring-[var(--logo-ring-sidebar)]",
};

function LogoPlate({
  context,
  className,
  imgClassName,
}: {
  context: LogoContext;
  className?: string | undefined;
  imgClassName?: string | undefined;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center justify-center rounded-xl px-2 py-1 ring-1",
        PLATE[context],
        className,
      )}
    >
      <img
        src="/readora_logo.png"
        alt="Readora"
        className={cn("w-auto object-contain", imgClassName)}
      />
    </span>
  );
}

export function LogoMark({ className, context = "sidebar" }: { className?: string; context?: LogoContext }) {
  return <LogoPlate context={context} imgClassName={cn("h-9", className)} />;
}

export function LogoLockup({
  className,
  context = "header",
  wordClassName: _wordClassName,
}: {
  className?: string;
  context?: LogoContext;
  wordClassName?: string;
}) {
  return <LogoPlate context={context} className={className} imgClassName="h-10" />;
}
