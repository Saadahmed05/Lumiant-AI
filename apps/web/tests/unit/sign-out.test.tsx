import { act } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  analyze,
  ask,
  bindAnalystUser,
  resetAnalyst,
  setLens,
  togglePin,
  type Turn,
  useAnalyst,
} from "@/components/analyst/store";
import type { ChatAnswer } from "@/lib/agent";
import { renderHook } from "@testing-library/react";

const stream = vi.hoisted(() => ({ fn: vi.fn() }));
vi.mock("@/lib/agent", async (original) => ({ ...(await original<object>()), streamChat: stream.fn }));

const ADMIN = "demo-alpha:alpha.admin";
const VIEWER = "demo-alpha:alpha.analyst";
const SECRET = "Stock is worth USD 133,381.";
const answer = { answer: SECRET, blocks: [], steps: [] } as unknown as ChatAnswer;
const KEY = (user: string) => `lumiant-analyst-board:${user}`;

function state() {
  return renderHook(() => useAnalyst()).result;
}

async function answered(question = "What is it worth?") {
  stream.fn.mockResolvedValueOnce(answer);
  await act(() => ask(question));
}

describe("Analyst data never outlives the session", () => {
  beforeEach(() => {
    window.localStorage.clear();
    act(() => resetAnalyst());
    stream.fn.mockReset();
  });

  afterEach(() => act(() => resetAnalyst()));

  it("clears the conversation, selections, dock and lens at sign-out", async () => {
    act(() => {
      bindAnalystUser(ADMIN);
      analyze({ kind: "warehouse", id: "1100", label: "North" });
      setLens(true);
    });
    await answered();
    const result = state();
    expect(result.current.turns).toHaveLength(1);

    act(() => resetAnalyst());
    expect(result.current).toMatchObject({ turns: [], selections: [], open: false, lens: false, busy: false, board: [] });
  });

  it("removes pinned answers from the browser at sign-out", async () => {
    act(() => bindAnalystUser(ADMIN));
    await answered();
    const result = state();
    act(() => togglePin(result.current.turns[0] as Turn));
    expect(window.localStorage.getItem(KEY(ADMIN))).toContain(SECRET);

    act(() => resetAnalyst());
    expect(JSON.stringify({ ...window.localStorage })).not.toContain(SECRET);
    expect(result.current.board).toEqual([]);
  });

  it("does not show one user's pins or conversation to another when the first never signed out", async () => {
    act(() => bindAnalystUser(ADMIN));
    await answered();
    const result = state();
    act(() => togglePin(result.current.turns[0] as Turn));

    act(() => bindAnalystUser(VIEWER));
    expect(result.current.turns).toEqual([]);
    expect(result.current.board).toEqual([]);
  });

  it("keeps a user's pins when the same user is bound again", async () => {
    act(() => bindAnalystUser(ADMIN));
    await answered();
    const result = state();
    act(() => togglePin(result.current.turns[0] as Turn));

    act(() => bindAnalystUser(ADMIN));
    expect(result.current.turns).toHaveLength(1);
    expect(result.current.board).toHaveLength(1);
  });

  it("drops pins saved before pins had an owner", () => {
    window.localStorage.setItem("lumiant-analyst-board", JSON.stringify([{ id: "x", question: "q", answer: SECRET }]));
    act(() => bindAnalystUser(VIEWER));
    expect(state().current.board).toEqual([]);
    expect(window.localStorage.getItem("lumiant-analyst-board")).toBeNull();
  });

  it("keeps an answer still streaming at sign-out away from the next user", async () => {
    act(() => bindAnalystUser(ADMIN));
    let finish: (value: ChatAnswer) => void = () => {};
    stream.fn.mockImplementationOnce(() => new Promise((resolve) => (finish = resolve)));
    const pending = ask("What is it worth?");

    act(() => resetAnalyst());
    act(() => bindAnalystUser(VIEWER));
    stream.fn.mockImplementationOnce(() => new Promise(() => {}));
    void ask("Another question");
    const result = state();
    expect(result.current.busy).toBe(true);

    await act(async () => {
      finish(answer);
      await pending;
    });
    expect(JSON.stringify(result.current.turns)).not.toContain(SECRET);
    expect(result.current.busy).toBe(true);
  });
});
