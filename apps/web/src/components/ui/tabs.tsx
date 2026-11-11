"use client";

import { clsx } from "clsx";
import { motion } from "motion/react";
import { useId } from "react";

import { LAYOUT_SPRING } from "@/lib/motion";

type TabItem<T extends string> = { id: T; label: string };

/** Underline tab bar; the indicator slides between tabs. */
export function Tabs<T extends string>({
  label,
  tabs,
  value,
  onChange,
  className,
  style,
}: {
  label: string;
  tabs: readonly TabItem<T>[];
  value: T;
  onChange: (id: T) => void;
  className?: string;
  style?: React.CSSProperties;
}) {
  const group = useId();
  return (
    <div role="tablist" aria-label={label} className={clsx("flex flex-wrap gap-1 border-b border-line", className)} style={style}>
      {tabs.map((t) => {
        const selected = t.id === value;
        return (
          <button
            key={t.id}
            type="button"
            role="tab"
            aria-selected={selected}
            onClick={() => onChange(t.id)}
            className={clsx(
              "relative -mb-px rounded-t-control px-3 py-2 text-sm font-medium transition-colors",
              selected ? "text-ink" : "text-ink-3 hover:bg-surface-2/60 hover:text-ink",
            )}
          >
            {t.label}
            {selected && (
              <motion.span layoutId={`tab-${group}`} transition={LAYOUT_SPRING} aria-hidden className="absolute inset-x-2 -bottom-px h-0.5 rounded-full bg-accent" />
            )}
          </button>
        );
      })}
    </div>
  );
}

/** Compact switch between a few values of the same thing (for example the currency of a chart). */
export function Segmented<T extends string>({ label, options, value, onChange }: { label: string; options: readonly T[]; value: T; onChange: (v: T) => void }) {
  return (
    <div role="tablist" aria-label={label} className="flex rounded-control border border-line bg-surface-2/60 p-0.5">
      {options.map((o) => (
        <button
          key={o}
          type="button"
          role="tab"
          aria-selected={o === value}
          onClick={() => onChange(o)}
          className={clsx(
            "figure rounded-[0.375rem] px-2 py-0.5 text-caption font-medium transition-colors",
            o === value ? "bg-surface-3 text-ink shadow-e1" : "text-ink-3 hover:text-ink",
          )}
        >
          {o}
        </button>
      ))}
    </div>
  );
}
