# ruff: noqa: F821
# Executed by run_answer_key.py inside Odoo with `env` and `OUT` set: answers computed by Odoo's own ORM.
import json
from collections import defaultdict

from odoo import fields

Product = env["product.product"]
storable = Product.search([("is_storable", "=", True)])
quants = env["stock.quant"].search([("location_id.usage", "=", "internal")])
by_uom = defaultdict(float)
by_product = defaultdict(float)
for q in quants:
    by_uom[q.product_uom_id.name] += q.quantity
    by_product[q.product_id.id] += q.quantity
top_id = max(by_product, key=by_product.get)
top = Product.browse(top_id)
cabinet = Product.search([("name", "=", "Large Cabinet")], limit=1)
layers = env["stock.valuation.layer"].search([])
orderpoints = env["stock.warehouse.orderpoint"].search([])
late = env["stock.picking"].search_count(
    [
        ("picking_type_code", "=", "outgoing"),
        ("state", "not in", ("done", "cancel")),
        ("scheduled_date", "<", fields.Datetime.now()),
    ]
)
truth = {
    "companies": env["res.company"].search_count([]),
    "o01": len(storable),
    "o02": dict(by_uom),
    "o03": sum(layers.mapped("value")),
    "o03_alt_quant_value": sum(quants.mapped("value")),
    "o04": env["stock.warehouse"].search_count([]),
    "o05": cabinet.qty_available,
    "o05_name": cabinet.display_name,
    "o06": env["purchase.order"].search_count(
        [("state", "=", "purchase"), ("receipt_status", "in", ("pending", "partial"))]
    ),
    "o07": by_product[top_id],
    "o07_name": top.display_name,
    "o08": late,
    "o09": len(orderpoints.filtered(lambda o: o.qty_on_hand < o.product_min_qty)),
    "o09_total_rules": len(orderpoints),
    "negative_internal_quants": len(quants.filtered(lambda q: q.quantity < 0)),
    "non_internal_quant_qty": sum(
        env["stock.quant"].search([("location_id.usage", "!=", "internal")]).mapped("quantity")
    ),
    "currency": env.company.currency_id.name,
    "value_at_cost": sum(q.quantity * q.product_id.with_company(q.company_id).standard_price for q in quants),
    "products_by_qty": sorted(
        ((Product.browse(pid).display_name, qty) for pid, qty in by_product.items()), key=lambda x: -x[1]
    )[:6],
    "storable_with_stock": len([pid for pid, qty in by_product.items() if qty > 0]),
    "stock_account_installed": bool(
        env["ir.module.module"].search([("name", "=", "stock_account"), ("state", "=", "installed")])
    ),
    "quants_per_company": {
        c.name: sum(quants.filtered(lambda q, c=c: q.company_id == c).mapped("quantity"))
        for c in env["res.company"].search([])
    },
    "warehouses": env["stock.warehouse"].search([]).mapped(lambda w: f"{w.name} ({w.company_id.name})"),
    "draft_rfqs": env["purchase.order"].search_count([("state", "in", ("draft", "sent"))]),
}
path = OUT  # set by run_answer_key.py
with open(path, "w", encoding="utf-8") as f:
    json.dump(truth, f, indent=1, default=str)
print("TRUTH WRITTEN", json.dumps(truth, default=str))
