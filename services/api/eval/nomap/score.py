"""Score an evaluation run. Usage: python eval/nomap/score.py <folder with copies and answers> [--truth-only]

Each answers_<db>.json holds [{"id", "kind", "value", "answer", "how_calculated", "assumptions"}]. `value` is a
number, or a {key: number} object when the answer has one figure per currency or unit.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import duckdb

sys.path.insert(0, str(Path(__file__).parent))
from cases import DATABASES, Case

CENTS = 0.006  # exact to the cent: a looser rule hid an 882.20 difference on the first run


def number(value: Any) -> float | None:
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None


def close(a: float | None, b: float | None) -> bool:
    if a is None or b is None:
        return False
    return abs(a - b) <= CENTS


def scalar(con: duckdb.DuckDBPyConnection, sql: str) -> float | None:
    row = con.execute(sql).fetchone()
    return number(row[0]) if row else None


def truth_of(con: duckdb.DuckDBPyConnection, case: Case) -> Any:
    if case.truth is None:
        return None
    if case.by_key:
        return {str(k): float(v) for k, v in con.execute(case.truth).fetchall()}
    return scalar(con, case.truth)


def matches(con: duckdb.DuckDBPyConnection, case: Case, value: Any) -> bool:
    truth = truth_of(con, case)
    if case.by_key:
        return (
            isinstance(value, dict)
            and set(value) == set(truth)
            and all(close(number(value[k]), truth[k]) for k in truth)
        )
    alternatives = [truth]
    for extra in case.accept_also:
        alternatives.append(scalar(con, extra) if isinstance(extra, str) else float(extra))
    return any(close(number(value), a) for a in alternatives)


def outcome(con: duckdb.DuckDBPyConnection, case: Case, reply: dict[str, Any] | None) -> str:
    """correct: right result. safe_stop: declined something answerable. wrong: a figure that differs from the key."""
    if reply is None:
        return "missing"
    kind = reply.get("kind")
    if kind != "answer":
        return "correct" if kind in case.expect else "safe_stop"
    if "answer" not in case.expect:
        return "wrong"
    if case.truth is None:
        return "review"
    return "correct" if matches(con, case, reply.get("value")) else "wrong"


def main(folder: Path, truth_only: bool) -> None:
    totals: Counter[str] = Counter()
    for name, (_, cases) in DATABASES.items():
        con = duckdb.connect(str(folder / f"{name}.duckdb"), read_only=True)
        if truth_only:
            for case in cases:
                print(name, case.id, case.expect, truth_of(con, case))
            con.close()
            continue
        path = folder / f"answers_{name}.json"
        replies = {r["id"]: r for r in json.loads(path.read_text(encoding="utf-8"))} if path.exists() else {}
        counts: Counter[str] = Counter()
        for case in cases:
            result = outcome(con, case, replies.get(case.id))
            counts[result] += 1
            if result != "correct":
                reply = replies.get(case.id) or {}
                got = f"{reply.get('kind')} {reply.get('value')}"
                print(f"  {case.id} {result}: got {got} want {case.expect} {truth_of(con, case)}")
        print(name, dict(counts))
        totals.update(counts)
        con.close()
    if not truth_only:
        print("TOTAL", dict(totals), "of", sum(totals.values()))


if __name__ == "__main__":
    main(Path(sys.argv[1]), "--truth-only" in sys.argv)
