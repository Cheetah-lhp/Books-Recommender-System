import logo from "@/assets/readora-logo-official.png.asset.json";
import { cn } from "@/lib/utils";

/**
 * Logo contexts are INDEPENDENT theme tokens.
 * Each context (header / sidebar / drawer / auth / compact) renders the official
 * READORA logo unmodified on its own dedicated brand plate, whose colors are
 * defined per context in src/styles.css (--logo-plate-* / --logo-ring-*).
 * Changing a header or sidebar background never affects logo visibility, and no
 * CSS filter or recoloring is ever applied to the artwork itself.
 */
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
        src={logo.url}
        alt="Readora"
        width={1280}
        height={853}
        className={cn("w-auto object-contain", imgClassName)}
      />
    </span>
  );
}

/** Icon/mark-sized lockup — used in collapsed sidebar rails and small surfaces. */
export function LogoMark({ className, context = "sidebar" }: { className?: string; context?: LogoContext }) {
  return <LogoPlate context={context} imgClassName={cn("h-9", className)} />;
}

/** Full lockup — header, mobile drawer, auth screens. */
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
