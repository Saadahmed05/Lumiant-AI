import { fireEvent, render, screen } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { matchSystemTheme, toggleTheme } from "@/components/shell/theme-toggle";
import { Button, IconButton } from "@/components/ui/button";
import { Field, Input, Select } from "@/components/ui/field";
import { DataTable, HeadRow, Td, Th, Tr } from "@/components/ui/table";
import { Segmented, Tabs } from "@/components/ui/tabs";

describe("Button", () => {
  it("is a plain button by default, so it never submits a form by accident", () => {
    render(<Button>Save</Button>);
    expect(screen.getByRole("button", { name: "Save" })).toHaveAttribute("type", "button");
  });

  it("keeps an explicit submit type and the disabled state", () => {
    render(
      <Button type="submit" disabled>
        Compare
      </Button>,
    );
    const button = screen.getByRole("button", { name: "Compare" });
    expect(button).toHaveAttribute("type", "submit");
    expect(button).toBeDisabled();
  });

  it("icon buttons take their name from aria-label", () => {
    const onClick = vi.fn();
    render(
      <IconButton aria-label="Close" onClick={onClick}>
        <svg aria-hidden />
      </IconButton>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Close" }));
    expect(onClick).toHaveBeenCalledOnce();
  });
});

describe("Field", () => {
  it("names the control it wraps", () => {
    render(
      <Field label="Warehouse" hint="Your scope only">
        <Select defaultValue="">
          <option value="">All</option>
          <option value="1100">1100 · North Plant</option>
        </Select>
      </Field>,
    );
    const select = screen.getByLabelText(/Warehouse/);
    expect(select.tagName).toBe("SELECT");
    expect(select.querySelectorAll("option")).toHaveLength(2);
    expect(screen.getByText("Your scope only")).toBeInTheDocument();
  });

  it("an explicit aria-label still wins, as the pages rely on", () => {
    render(
      <Field label="A covers up to">
        <Input aria-label="A cutoff" defaultValue="0.80" />
      </Field>,
    );
    expect(screen.getByRole("textbox", { name: "A cutoff" })).toHaveValue("0.80");
  });
});

describe("Tabs", () => {
  const tabs = [
    { id: "excess", label: "Excess stock" },
    { id: "dormant", label: "Dormant stock" },
  ] as const;

  it("exposes a tablist with exactly one selected tab and reports clicks", () => {
    const onChange = vi.fn();
    render(<Tabs label="Risk views" tabs={tabs} value="excess" onChange={onChange} />);
    expect(screen.getByRole("tablist", { name: "Risk views" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Excess stock" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tab", { name: "Dormant stock" })).toHaveAttribute("aria-selected", "false");
    fireEvent.click(screen.getByRole("tab", { name: "Dormant stock" }));
    expect(onChange).toHaveBeenCalledWith("dormant");
  });

  it("segmented control marks the current value", () => {
    const onChange = vi.fn();
    render(<Segmented label="Currency" options={["EUR", "GBP"]} value="EUR" onChange={onChange} />);
    expect(screen.getByRole("tab", { name: "EUR" })).toHaveAttribute("aria-selected", "true");
    fireEvent.click(screen.getByRole("tab", { name: "GBP" }));
    expect(onChange).toHaveBeenCalledWith("GBP");
  });
});

describe("DataTable", () => {
  it("announces the sorted column and sorts on click", () => {
    const onSort = vi.fn();
    render(
      <DataTable busy testId="t">
        <thead>
          <HeadRow>
            <Th sort={{ active: true, dir: "desc", onSort }}>Value</Th>
            <Th>Group</Th>
          </HeadRow>
        </thead>
        <tbody>
          <Tr>
            <Td align="right">10</Td>
            <Td>Spares</Td>
          </Tr>
        </tbody>
      </DataTable>,
    );
    expect(screen.getByTestId("t")).toHaveAttribute("aria-busy", "true");
    expect(screen.getByRole("columnheader", { name: "Value" })).toHaveAttribute("aria-sort", "descending");
    expect(screen.getByRole("columnheader", { name: "Group" })).not.toHaveAttribute("aria-sort");
    fireEvent.click(screen.getByRole("button", { name: "Value" }));
    expect(onSort).toHaveBeenCalledOnce();
    expect(screen.getAllByRole("row")).toHaveLength(2);
  });
});

describe("theme follows the system until the user chooses", () => {
  const root = document.documentElement;
  const source = readFileSync(resolve(process.cwd(), "public", "theme-init.js"), "utf8");
  const boot = () => new Function(source)();
  const original = window.matchMedia;
  let listeners: (() => void)[] = [];
  let prefersLight = false;

  beforeEach(() => {
    localStorage.clear();
    delete root.dataset.theme;
    listeners = [];
    prefersLight = false;
    window.matchMedia = ((query: string) => ({
      get matches() {
        return query.includes("light") && prefersLight;
      },
      media: query,
      addEventListener: (_type: string, listener: () => void) => listeners.push(listener),
      removeEventListener() {},
    })) as unknown as typeof window.matchMedia;
  });

  afterEach(() => {
    window.matchMedia = original;
    localStorage.clear();
    delete root.dataset.theme;
  });

  it("a light system gets the light theme when nothing is saved", () => {
    prefersLight = true;
    boot();
    expect(root.dataset.theme).toBe("light");
  });

  it("a dark system leaves the attribute off (dark is the base theme)", () => {
    boot();
    expect(root.dataset.theme).toBeUndefined();
  });

  it("a saved choice wins over the system setting", () => {
    prefersLight = true;
    localStorage.setItem("lumiant-theme", "dark");
    boot();
    expect(root.dataset.theme).toBe("dark");
  });

  it("follows a system change live, but not after the user has chosen", () => {
    boot();
    prefersLight = true;
    listeners.forEach((l) => l());
    expect(root.dataset.theme).toBe("light");

    toggleTheme();
    expect(root.dataset.theme).toBe("dark");
    prefersLight = false;
    listeners.forEach((l) => l());
    prefersLight = true;
    listeners.forEach((l) => l());
    expect(root.dataset.theme).toBe("dark");
  });

  it("the toggle flips from the effective theme, and 'match system' forgets the choice", () => {
    prefersLight = true;
    boot();
    toggleTheme();
    expect(root.dataset.theme).toBe("dark");
    expect(localStorage.getItem("lumiant-theme")).toBe("dark");

    matchSystemTheme();
    expect(localStorage.getItem("lumiant-theme")).toBeNull();
    expect(root.dataset.theme).toBe("light");
  });
});
