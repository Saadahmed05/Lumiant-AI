"use client";

import { ArrowRight, BarChart3, Boxes, ClipboardCheck, Coins, FileText, Scale, ShieldAlert, Snail } from "lucide-react";
import Link from "next/link";

import { PageHeader } from "@/components/ui/page-header";
import { useMe } from "@/lib/hooks";
import { enterDelay } from "@/lib/motion";

type Card = {
  title: string;
  blurb: string;
  href: string;
  icon: typeof Boxes;
  needs?: "costs" | "assistant" | "risks" | "reports" | "inventory";
};

const q = (text: string) => `/assistant?q=${encodeURIComponent(text)}`;

const CARDS: Card[] = [
  { title: "Analyze stock", blurb: "Search and filter every stock line by item, warehouse, group and ABC class.", href: "/inventory", icon: Boxes, needs: "inventory" },
  { title: "Compare warehouses", blurb: "See how stock is spread across your warehouses.", href: q("Show inventory value by warehouse"), icon: Scale, needs: "assistant" },
  { title: "Investigate inventory costs", blurb: "Compare costing methods for one item and reconcile with the source.", href: "/costs", icon: Coins, needs: "costs" },
  { title: "Find slow-moving items", blurb: "Stock that has not been issued for months.", href: q("Which items have not moved in six months?"), icon: Snail, needs: "assistant" },
  { title: "Review stock risks", blurb: "Excess stock, dormant stock, expiring lots and data gaps.", href: "/risks", icon: ShieldAlert, needs: "risks" },
  { title: "Check master-data quality", blurb: "Missing policies, prices and invalid item codes.", href: q("Which items have incomplete master data?"), icon: ClipboardCheck, needs: "assistant" },
  { title: "Generate a report", blurb: "Download or print a report with its filters and sources attached.", href: "/reports", icon: FileText, needs: "reports" },
  { title: "Ask in your own words", blurb: "Type a question; the assistant picks the right checked analysis.", href: "/assistant", icon: BarChart3, needs: "assistant" },
];

export function ExplorePage() {
  const me = useMe();
  const sections = new Set<string>(me.data?.sections ?? []);
  const cards = CARDS.filter((c) => !c.needs || sections.has(c.needs));
  return (
    <div className="mx-auto max-w-5xl space-y-5">
      <PageHeader title="What would you like to do?" description="Each choice runs the same secured analyses as the assistant. Only options your role allows are shown." />
      <ul className="grid gap-3 sm:grid-cols-2" data-testid="explore-cards">
        {cards.map((c, i) => (
          <li key={c.title} className="rise" style={enterDelay(i)}>
            <Link
              href={c.href}
              className="panel group flex h-full items-start gap-3.5 p-4 transition-colors hover:border-line-strong hover:bg-surface-2 sm:p-5"
            >
              <span className="flex size-9 shrink-0 items-center justify-center rounded-control border border-line bg-surface-2 text-accent">
                <c.icon size={18} aria-hidden />
              </span>
              <span className="min-w-0 flex-1">
                <span className="block text-title font-semibold text-ink">{c.title}</span>
                <span className="mt-1 block text-dense text-ink-3">{c.blurb}</span>
              </span>
              <ArrowRight size={16} className="mt-1 shrink-0 text-ink-3 transition-[color,transform] group-hover:translate-x-0.5 group-hover:text-ink" aria-hidden />
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
