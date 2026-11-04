"""Score answers.json against answer_key.json (computed by Odoo itself). Usage: python score.py [answers.json]"""

import json
import sys
from pathlib import Path

here = Path(__file__).parent
truth = json.loads((here / "answer_key.json").read_text(encoding="utf-8"))
answers_path = Path(sys.argv[1]) if len(sys.argv) > 1 else here / "answers.json"
answers = {a["id"]: a for a in json.loads(answers_path.read_text(encoding="utf-8"))}
# o01 and o06 have a second defensible reading; the agent must state which it used.
key = {
    "o01": ("answer", [truth["o01"], 27]),  # variants, or products (templates)
    "o02": ("answer", [truth["o02"]["Units"]]),
    "o03": ("answer", [truth["value_at_cost"]]),
    "o04": ("answer", [truth["o04"]]),
    "o05": ("answer", [90.0]),
    "o06": ("answer", [truth["o06"], 4]),  # open receipts, or confirmed orders with nothing received
    "o07": ("answer", [truth["o07"]]),
    "o08": ("answer", [truth["o08"]]),
    "o09": ("answer", [truth["o09"]]),
    "o10": ("answer", [truth["draft_rfqs"]]),
    "o11": ("refuse", []),
    "o12": ("answer", [truth["o04"]]),
}
counts: dict[str, int] = {}
for qid, (kind, accepted) in key.items():
    a = answers.get(qid, {})
    if a.get("kind") != "answer":
        outcome = "correct" if a.get("kind") == kind else "safe_stop"
    elif kind != "answer":
        outcome = "wrong"
    else:
        try:
            outcome = "correct" if any(abs(float(a.get("value")) - float(v)) <= 0.006 for v in accepted) else "wrong"
        except (TypeError, ValueError):
            outcome = "wrong"
    counts[outcome] = counts.get(outcome, 0) + 1
    print(f"{qid} {outcome:9} got {a.get('kind')} {a.get('value')}  accepted {kind} {accepted}")
print("TOTAL", counts)
