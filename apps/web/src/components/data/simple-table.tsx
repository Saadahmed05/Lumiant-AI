"use client";

import { CodeName, DataTable, HeadRow, Td, Th, Tr } from "@/components/ui/table";
import type { Row } from "@/lib/api";

export type SimpleColumn = {
  key: string;
  label: string;
  align?: "right";
  render: (row: Row) => React.ReactNode;
};

export function SimpleTable({
  columns,
  rows,
  empty,
  busy,
  rowKey,
  minWidth = "44rem",
}: {
  columns: SimpleColumn[];
  rows: Row[];
  empty: string;
  busy?: boolean;
  rowKey: (row: Row, index: number) => string;
  minWidth?: string;
}) {
  if (rows.length === 0) return <p className="text-sm text-ink-3">{empty}</p>;
  return (
    <DataTable minWidth={minWidth} busy={busy}>
      <thead>
        <HeadRow>
          {columns.map((c) => (
            <Th key={c.key} align={c.align}>
              {c.label}
            </Th>
          ))}
        </HeadRow>
      </thead>
      <tbody>
        {rows.map((r, i) => (
          <Tr key={rowKey(r, i)}>
            {columns.map((c) => (
              <Td key={c.key} align={c.align}>
                {c.render(r)}
              </Td>
            ))}
          </Tr>
        ))}
      </tbody>
    </DataTable>
  );
}

export function ItemCell({ row }: { row: Row }) {
  const code = (row["item.item_code"] ?? row.item_code ?? row.item_id) as string;
  const description = (row["item.description"] ?? row.description) as string | null;
  return <CodeName code={code} name={description} />;
}
