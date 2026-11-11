import { clsx } from "clsx";
import type { LucideIcon } from "lucide-react";

/** What to show when there is nothing to show: a plain sentence, optionally an icon and a hint on what to do next. */
export function EmptyState({ icon: Icon, title, hint, className }: { icon?: LucideIcon; title: string; hint?: React.ReactNode; className?: string }) {
  return (
    <div className={clsx("flex items-start gap-3 rounded-control border border-dashed border-line-strong px-4 py-3.5", className)}>
      {Icon && <Icon size={16} aria-hidden className="mt-0.5 shrink-0 text-ink-3" />}
      <div className="min-w-0">
        <p className="text-sm text-ink-2">{title}</p>
        {hint && <p className="mt-0.5 text-xs text-ink-3">{hint}</p>}
      </div>
    </div>
  );
}
