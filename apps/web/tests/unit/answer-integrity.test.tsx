import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AnswerBody } from "@/components/analyst/answer-view";
import { InsightsFeed } from "@/components/overview/insights-feed";
import type { ChatAnswer } from "@/lib/agent";
import { api } from "@/lib/api";

const answer = (grounding: ChatAnswer["grounding"]): ChatAnswer => ({
  mode: "anthropic",
  notice: null,
  kind: "unsupported",
  answer: "An answer.",
  blocks: [],
  tool_calls: [],
  provenance: [],
  warnings: [],
  follow_ups: [],
  choices: [],
  grounding,
});

function renderAnswer(grounding: ChatAnswer["grounding"]) {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <AnswerBody answer={answer(grounding)} onAsk={() => {}} turnId={1} testId="answer" />
    </QueryClientProvider>,
  );
}

function renderFeed(feed: object) {
  vi.spyOn(api, "get").mockResolvedValue({ insights: [], gaps: [], failed: [], complete: true, generated_at: "2026-10-31T00:00:00Z", ...feed });
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <InsightsFeed />
    </QueryClientProvider>,
  );
}

describe("AnswerBody number checks", () => {
  it("says so when an AI answer was withheld, and never claims the numbers were checked", () => {
    renderAnswer({ passed: false, source: "blocked", ungrounded: ["48,250,000"] });
    expect(screen.getByTestId("grounding-failed").textContent).toMatch(/withheld/);
    expect(screen.queryByText("numbers checked")).toBeNull();
  });

  it("flags figures that could not be traced, even on a model-worded answer", () => {
    renderAnswer({ passed: false, source: "model" });
    expect(screen.getByTestId("grounding-failed").textContent).toMatch(/could not be traced/);
    expect(screen.queryByText("numbers checked")).toBeNull();
  });

  it("shows no warning on a verified answer", () => {
    renderAnswer({ passed: true, source: "model" });
    expect(screen.queryByTestId("grounding-failed")).toBeNull();
    expect(screen.getByText("numbers checked")).toBeTruthy();
  });
});

describe("InsightsFeed", () => {
  it("never reports an all-clear when the checks failed", async () => {
    renderFeed({ complete: false, failed: [{ id: "dormant", label: "dormant stock", code: "source_unavailable", message: "x" }] });
    expect((await screen.findByTestId("insights-incomplete")).textContent).toMatch(/could not be checked.*dormant stock/);
    expect(screen.queryByText(/Nothing stands out/)).toBeNull();
  });

  it("reports an all-clear only when every check ran", async () => {
    renderFeed({});
    expect(await screen.findByText(/Nothing stands out/)).toBeTruthy();
    expect(screen.queryByTestId("insights-incomplete")).toBeNull();
  });
});
