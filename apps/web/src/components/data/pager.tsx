"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";

import { Button } from "@/components/ui/button";
import { formatCount } from "@/lib/format";

export function Pager({
  page,
  onChange,
}: {
  page: { offset: number; limit: number; total: number };
  onChange: (offset: number) => void;
}) {
  const { offset, limit, total } = page;
  const from = total === 0 ? 0 : offset + 1;
  const to = Math.min(offset + limit, total);
  return (
    <nav aria-label="Pagination" className="mt-4 flex items-center justify-between gap-3 text-xs text-ink-3">
      <span className="figure" data-testid="pager-range">
        {formatCount(from)}–{formatCount(to)} of {formatCount(total)}
      </span>
      <span className="flex gap-1.5">
        <Button size="sm" className="pl-1.5" disabled={offset === 0} onClick={() => onChange(Math.max(0, offset - limit))}>
          <ChevronLeft size={14} aria-hidden /> Prev
        </Button>
        <Button size="sm" className="pr-1.5" disabled={to >= total} onClick={() => onChange(offset + limit)}>
          Next <ChevronRight size={14} aria-hidden />
        </Button>
      </span>
    </nav>
  );
}
