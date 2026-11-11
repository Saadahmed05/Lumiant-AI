import { clsx } from "clsx";

type Tone = "neutral" | "accent" | "signal" | "ok";

const TONE: Record<Tone, string> = {
  neutral: "border-line-strong bg-surface-2 text-ink-2",
  accent: "border-accent/30 bg-accent-soft text-accent",
  signal: "border-signal/35 bg-signal-soft text-signal",
  ok: "border-ok/30 bg-surface-2 text-ok",
};

/** Small pill for a state or a category. A state must carry its meaning in words, not only in colour. */
export function Badge({ tone = "neutral", className, children }: { tone?: Tone; className?: string; children: React.ReactNode }) {
  return (
    <span className={clsx("inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-caption font-medium whitespace-nowrap", TONE[tone], className)}>
      {children}
    </span>
  );
}

/** A question or choice the user can click: suggestions, follow-ups, "ask next". */
export function Chip({ size = "md", className, type = "button", ...rest }: React.ComponentProps<"button"> & { size?: "sm" | "md" }) {
  return (
    <button
      type={type}
      className={clsx(
        "rounded-full border border-line bg-surface text-left text-ink-2 transition-[background-color,border-color,color,transform] hover:border-accent/50 hover:bg-accent-soft hover:text-accent active:translate-y-px",
        size === "sm" ? "px-2.5 py-1 text-xs" : "px-3 py-1.5 text-xs",
        className,
      )}
      {...rest}
    />
  );
}
