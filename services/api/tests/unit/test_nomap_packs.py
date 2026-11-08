"""Knowledge packs switch on only for the system they describe, and never for a lookalike."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from lumiant.nomap.discovery import discover
from lumiant.nomap.source import Source

EBS = [
    "MTL_SYSTEM_ITEMS_B",
    "MTL_ONHAND_QUANTITIES_DETAIL",
    "MTL_PARAMETERS",
    "MTL_SECONDARY_INVENTORIES",
    "PO_HEADERS_ALL",
]
FO = ["INVENTSUM", "INVENTDIM", "INVENTTABLE", "INVENTTRANS", "PURCHLINE"]
BC = [
    "CRONUS$Item$437dbf0e-84ff-417a-965d-ed2bb9650972",
    "CRONUS$Item Ledger Entry$437dbf0e-84ff-417a-965d-ed2bb9650972",
    "CRONUS$Value Entry$437dbf0e-84ff-417a-965d-ed2bb9650972",
    "CRONUS$Location$437dbf0e-84ff-417a-965d-ed2bb9650972",
]


def database(tmp_path: Path, tables: list[str]) -> Source:
    path = tmp_path / "erp.sqlite"
    con = sqlite3.connect(path)
    for name in tables:
        con.execute(f'create table "{name}" (id integer, code text)')
    con.close()
    return Source(f"sqlite:///{path.as_posix()}")


@pytest.mark.parametrize(
    ("tables", "pack", "rule"),
    [
        (EBS, "Oracle E-Business Suite", "PRIMARY_TRANSACTION_QUANTITY"),
        (FO, "Dynamics 365 Finance and Operations", "DATAAREAID"),
        (BC, "Business Central", "Cost Amount (Actual)"),
    ],
)
def test_pack_switches_on_from_standard_tables(tmp_path: Path, tables: list[str], pack: str, rule: str) -> None:
    catalog = discover(database(tmp_path, tables))
    assert any(pack in p and "unconfirmed" in p for p in catalog.packs)
    assert any(rule in n for n in catalog.notes)


def test_business_central_company_tables_get_their_meaning(tmp_path: Path) -> None:
    catalog = discover(database(tmp_path, BC))
    ledger = next(t for t in catalog.tables if "Item Ledger Entry" in t.name)
    assert "stock movements" in (ledger.meaning or "")
    assert catalog.search("stock movements")[0].name == ledger.name


@pytest.mark.parametrize("tables", [EBS[:3], FO[:3], BC[:3], ["item", "location", "stock"]])
def test_no_pack_from_a_partial_or_lookalike_schema(tmp_path: Path, tables: list[str]) -> None:
    assert discover(database(tmp_path, tables)).packs == ()
