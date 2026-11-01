"""Make neutral copies of the demo databases and write question-only files for the agent under test.

Usage: python eval/nomap/prepare.py <output folder>
The copies lose `_dataset_info`, which lists the planted problems, and their tenant names.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).parent))
from cases import DATABASES

DATA = Path(__file__).parents[2] / "data" / "synthetic"


def main(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    for name, (tenant, cases) in DATABASES.items():
        copy = out / f"{name}.duckdb"
        copy.unlink(missing_ok=True)
        shutil.copy(DATA / f"{tenant}.duckdb", copy)
        con = duckdb.connect(str(copy))
        for schema in con.execute(
            "select schema_name from information_schema.schemata where schema_name in ('main', 'inv')"
        ).fetchall():
            con.execute(f'drop table if exists "{schema[0]}"."_dataset_info"')
        con.close()
        questions = [{"id": c.id, "question": c.question} for c in cases]
        (out / f"{name}_questions.json").write_text(
            json.dumps(questions, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        print(name, len(questions), "questions")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
