"""Hide the SAP-style demo among 300 noise tables and two decoys, and write questions plus a private answer key.

Usage: python eval/nomap/crowded.py <output folder>
The answer key goes next to the folder, not inside it, so the agent under test is never pointed at it.
Decoys: a stale backup (ZV_STOCK_BAK_2024, quantities x1.3) and a 200-row test copy (ZV_STOCK_TEST).
"""

# ruff: noqa: E501, S311, S608

import json
import random
import shutil
import sys
from pathlib import Path

import duckdb

out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
db = out / "crowded.duckdb"
db.unlink(missing_ok=True)
shutil.copy(Path(__file__).parents[2] / "data" / "synthetic" / "demo-alpha.duckdb", db)
con = duckdb.connect(str(db))
con.execute("drop table _dataset_info")
random.seed(11)
words = ["ZCO", "ZSD", "ZPP", "ZQM", "ZHR", "ZFI", "ZWM", "ZMM"]
for i in range(300):
    name = f"{random.choice(words)}_{i:04d}"
    con.execute(
        f'create table "{name}" (MANDT varchar, MATNR varchar, WERKS varchar, BUKRS varchar, ZVAL decimal(18,2), ZQTY decimal(18,3), ERDAT date)'
    )
    con.execute(
        f"insert into \"{name}\" select '100', 'M' || (random()*50)::int, 'P' || (random()*4)::int, '1000', random()*1000, random()*100, date '2025-01-01' + (random()*300)::int from range(20)"
    )
# Decoys a careless agent might use: a stale backup and a partial test copy of the stock table.
con.execute(
    "create table ZV_STOCK_BAK_2024 as select MATNR, WERKS, LGORT, CHARG, LABST * 1.3 as LABST, MEINS, VERPR, WAERS from ZV_STOCK"
)
con.execute("create table ZV_STOCK_TEST as select * from ZV_STOCK using sample 200 rows")
truth = {
    "c01": con.execute("select sum(LABST*VERPR) from ZV_STOCK").fetchone()[0],
    "c02": con.execute("select count(distinct MATNR) from ZV_STOCK where LABST>0").fetchone()[0],
    "c03": con.execute(
        "select sum(s.LABST*s.VERPR) from ZV_STOCK s join ZV_MATERIAL m using (MATNR) where m.MTART='FINISHED'"
    ).fetchone()[0],
    "c04": con.execute(
        "select count(*) from ZV_REORDER r left join (select MATNR,WERKS,sum(LABST) q from ZV_STOCK group by 1,2) s using (MATNR,WERKS) where coalesce(s.q,0) < r.MINBE"
    ).fetchone()[0],
    "c05": con.execute(
        "select count(distinct s.CHARG) from ZV_STOCK s join ZV_BATCH b using (CHARG) where s.LABST>0 and b.VFDAT < date '2026-10-31'"
    ).fetchone()[0],
    "c06": con.execute("select count(*) from ZV_PURCHASE where ZZSTATUS='OPEN'").fetchone()[0],
    "c07": con.execute("select sum(LABST) from ZV_STOCK where MATNR='2119000124'").fetchone()[0],
    "c08": con.execute("select count(*) from ZV_PLANT").fetchone()[0],
}
con.close()
questions = [
    {"id": "c01", "question": "What is the total inventory value?"},
    {"id": "c02", "question": "How many different items do we have in stock?"},
    {"id": "c03", "question": "What is the value of finished goods?"},
    {"id": "c04", "question": "How many item and warehouse combinations are below their reorder level?"},
    {"id": "c05", "question": "How many distinct lots with stock on hand have already expired?"},
    {"id": "c06", "question": "How many open purchase order lines do we have?"},
    {"id": "c07", "question": "How much unrestricted stock of material 2119000124 do we hold in total?"},
    {"id": "c08", "question": "How many plants do we have?"},
]
(out / "crowded_questions.json").write_text(json.dumps(questions, indent=1), encoding="utf-8")
(out.parent / "crowded_truth.json").write_text(json.dumps({k: float(v) for k, v in truth.items()}), encoding="utf-8")
print(
    "tables:",
    len(duckdb.connect(str(db), read_only=True).execute("select * from information_schema.tables").fetchall()),
)
