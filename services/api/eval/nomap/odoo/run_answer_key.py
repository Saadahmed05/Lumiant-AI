# ruff: noqa: E402, S102
"""Compute the Odoo answer key with Odoo's own ORM, read-only (the transaction is rolled back).

Usage, with the Odoo 18 source folder on the path and its Python environment:
    python run_answer_key.py <odoo source folder> <postgres port> <output json>
The database is `odoo_demo`, built with: python -m odoo -d odoo_demo -i stock,purchase,sale_stock --stop-after-init
"""

import sys
from pathlib import Path

source, port, out = sys.argv[1], sys.argv[2], sys.argv[3]
sys.path.insert(0, source)

import odoo
from odoo import api

odoo.tools.config.parse_config(["--db_host", "127.0.0.1", "--db_port", port, "-r", "odoo", "-w", "odoo_local_only"])
registry = odoo.modules.registry.Registry("odoo_demo")
with registry.cursor() as cr:
    env = api.Environment(cr, odoo.SUPERUSER_ID, {})
    exec(Path(__file__).with_name("answer_key_odoo.py").read_text(encoding="utf-8"), {"env": env, "OUT": out})
    cr.rollback()
