import type { DataClassification } from "@/lib/api";

/** Plain, always-visible label: demo data is generated, never customer data (brief §3.2, §21). */
export function SyntheticTape({ compact = false }: { compact?: boolean }) {
  return (
    <span
      className="inline-flex shrink-0 items-center rounded-[3px] border border-line-strong px-1.5 py-0.5"
      title="Generated demonstration data — not from any customer system"
      data-testid="synthetic-badge"
    >
      <span className="whitespace-nowrap text-[0.625rem] font-bold tracking-[0.14em] text-ink-2">
        {compact ? (
          "SYNTHETIC"
        ) : (
          <>
            <span className="sm:hidden">SYNTHETIC</span>
            <span className="hidden sm:inline">SYNTHETIC DEMO DATA</span>
          </>
        )}
      </span>
    </span>
  );
}

/** Real client files loaded on this machine for analysis (ADR-0008): confidential, never shared or deployed. */
export function ClientExtractTape({ compact = false }: { compact?: boolean }) {
  return (
    <span
      className="inline-flex shrink-0 items-center rounded-[3px] border-2 border-signal bg-signal-soft px-1.5 py-0.5"
      title="Real client data loaded locally from exported files — confidential, do not share or deploy"
      data-testid="client-extract-badge"
    >
      <span className="whitespace-nowrap text-[0.625rem] font-extrabold tracking-[0.14em] text-signal">
        {compact ? (
          "CLIENT EXTRACT"
        ) : (
          <>
            <span className="sm:hidden">CLIENT EXTRACT</span>
            <span className="hidden sm:inline">CLIENT EXTRACT · CONFIDENTIAL · LOCAL</span>
          </>
        )}
      </span>
    </span>
  );
}

/** The label for the data a tenant serves: client-extract badge, synthetic tape, or nothing for live customer data. */
export function DataBadge({
  classification,
  synthetic,
  compact = false,
}: {
  classification?: DataClassification;
  synthetic: boolean;
  compact?: boolean;
}) {
  if (classification === "customer_extract") return <ClientExtractTape compact={compact} />;
  if (synthetic) return <SyntheticTape compact={compact} />;
  return null;
}
