"""Odoo-shaped data: the pack switches on by table names, and mirror quantities are flagged before anyone adds them."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from lumiant.nomap.discovery import discover
from lumiant.nomap.source import Source

ODOO_TABLES = ("stock_location", "product_template", "product_product", "res_company", "ir_model")


@pytest.fixture
def odoo_like(tmp_path: Path) -> Source:
    path = tmp_path / "odoo.sqlite"
    con = sqlite3.connect(path)
    for name in ODOO_TABLES:
        con.execute(f"create table {name} (id integer, name text)")
    con.execute(
        "create table stock_warehouse_orderpoint (id integer, product_min_qty numeric, product_max_qty numeric)"
    )
    con.execute("create table stock_rule (id integer, action text)")
    con.execute("create table stock_quant (id integer, product_id integer, location_id integer, quantity numeric)")
    # Odoo books an inventory adjustment as stock in the warehouse plus the mirror in a virtual location.
    con.executemany(
        "insert into stock_quant values (?, ?, ?, ?)",
        [(1, 7, 8, 500), (2, 7, 14, -500), (3, 9, 8, 90), (4, 9, 14, -90)],
    )
    con.commit()
    con.close()
    return Source(f"sqlite:///{path.as_posix()}")


def test_odoo_pack_switches_on_from_table_names(odoo_like: Source) -> None:
    catalog = discover(odoo_like)
    assert "Odoo" in catalog.packs
    assert any("usage = 'internal'" in n for n in catalog.notes)


def test_mirror_quantities_are_flagged(odoo_like: Source) -> None:
    quant = discover(odoo_like).find("stock_quant")
    assert quant is not None
    assert any("adds up to about zero" in c for c in quant.checks)


def test_search_ranks_by_known_meaning(odoo_like: Source) -> None:
    assert discover(odoo_like).search("reordering rule minimum")[0].name == "stock_warehouse_orderpoint"


def test_odoo_pack_stays_off_without_its_tables(tmp_path: Path) -> None:
    path = tmp_path / "other.sqlite"
    con = sqlite3.connect(path)
    con.execute("create table stock_quant (id integer, quantity numeric)")
    con.close()
    assert "Odoo" not in discover(Source(f"sqlite:///{path.as_posix()}")).packs
