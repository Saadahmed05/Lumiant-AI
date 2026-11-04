"""Knowledge packs: the standard meaning of fields in systems we recognise, so customers map nothing by hand.

A pack applies only when enough of its field names appear, and it labels meanings as known, not proven: customers
reuse standard fields in their own ways, so the agent still checks them against the data. Meanings here are SAP's
standard data dictionary descriptions; they must be confirmed on a real SAP sandbox before any customer relies on them.
"""

from __future__ import annotations

from dataclasses import replace

from lumiant.nomap.catalog import Catalog

MIN_FIELDS = 6  # distinct SAP field names before the pack applies

SAP_FIELDS = {
    "MANDT": "client; filter to one client, never mix clients",
    "MATNR": "material number",
    "MAKTX": "material description (free text)",
    "MTART": "material type",
    "MATKL": "material group",
    "MEINS": "base unit of measure",
    "WERKS": "plant",
    "LGORT": "storage location",
    "LGOBE": "storage location description",
    "CHARG": "batch (lot) number",
    "LABST": "unrestricted-use stock quantity",
    "INSME": "stock in quality inspection",
    "SPEME": "blocked stock",
    "EINME": "stock in restricted-use batches",
    "UMLME": "stock in transfer between storage locations",
    "RETME": "blocked stock from returns",
    "VERPR": "moving average price, per PEINH units",
    "STPRS": "standard price, per PEINH units",
    "PEINH": "price unit: the number of units the price covers",
    "VPRSV": "price control: S standard price, V moving average",
    "LBKUM": "total valuated stock quantity",
    "SALK3": "value of total valuated stock",
    "BWKEY": "valuation area, often the plant",
    "BWTAR": "valuation type (split valuation)",
    "WAERS": "currency key",
    "BWART": "movement type",
    "SHKZG": "debit/credit indicator: S receipt, H issue",
    "MENGE": "quantity",
    "BUDAT": "posting date",
    "BLDAT": "document date",
    "MBLNR": "material document number",
    "MJAHR": "material document year",
    "VFDAT": "shelf-life expiration date",
    "HSDAT": "date of manufacture",
    "LIFNR": "vendor (supplier) number",
    "EBELN": "purchasing document number",
    "EBELP": "purchasing document item",
    "BEDAT": "purchasing document date",
    "NETPR": "net price, per price unit",
    "ELIKZ": "delivery completed indicator",
    "LOEKZ": "deletion indicator",
    "MINBE": "reorder point",
    "EISBE": "safety stock",
    "MABST": "maximum stock level",
    "DISMM": "MRP type",
    "ABCKZ": "ABC indicator",
    "MSTAE": "cross-plant material status",
    "XCHPF": "batch management required",
    "MHDHB": "total shelf life",
    "LAND1": "country key",
    "KUNNR": "customer number",
}

SAP_TABLES = {
    "MARA": "general material data",
    "MAKT": "material descriptions",
    "MARC": "plant data for material",
    "MARD": "stock by storage location",
    "MBEW": "material valuation",
    "MCHB": "batch stock",
    "MCH1": "batches",
    "MKPF": "material document headers (ECC)",
    "MSEG": "material document items (ECC)",
    "MATDOC": "material documents (S/4HANA; replaces MKPF and MSEG)",
    "EKKO": "purchase order headers",
    "EKPO": "purchase order items",
    "LFA1": "vendor master",
    "T001W": "plants",
    "T001L": "storage locations",
}

# Each rule applies only when its field is present.
SAP_NOTES = {
    "PEINH": "Unit price = price / PEINH. Multiplying quantity by the price without dividing overstates value.",
    "LABST": "Unrestricted, quality inspection, blocked and restricted stock are separate quantities; say which ones you count.",
    "SHKZG": "H in SHKZG means an issue: make the quantity negative before adding movements.",
    "MANDT": "If MANDT holds more than one client, filter to one.",
}


# Odoo is recognised by its table names; it already labels every column in the database, so the pack adds rules.
# Checked against a real Odoo 18 demo database (stock, purchase, sale_stock).
ODOO_SIGNATURE = {"stock_quant", "stock_location", "product_template", "product_product", "res_company", "ir_model"}
ODOO_TABLES = {
    "stock_quant": "stock on hand per product, location and lot",
    "stock_location": "locations; only usage 'internal' is stock in a warehouse",
    "product_template": "products as users see them",
    "product_product": "product variants of a product_template",
    "stock_move": "planned and done stock movements",
    "stock_picking": "transfers: receipts, deliveries and internal moves",
    "stock_warehouse_orderpoint": "reordering rules (minimum and maximum quantities)",
    "stock_valuation_layer": "accounting valuation entries; empty or zero when valuation is not automated",
    "purchase_order": "purchase orders and quotations (RFQs)",
    "sale_order": "sales orders and quotations",
    "res_company": "companies; data may belong to several",
}
ODOO_NOTES = (
    "stock_quant also holds mirror quantities in virtual locations (inventory adjustment, customers, suppliers, production, transit), so totals over every location cancel out. Join stock_location and count only usage = 'internal' for stock on hand.",
    "Names are JSON keyed by language: use name->>'en_US'.",
    'product_product.standard_price (cost) is JSON keyed by company id, such as {"1": 70.0}: read the company\'s key.',
    "There may be several companies: say which company_id you count, or report each.",
    "product_template is the product as users see it; product_product holds its variants, so counts differ.",
    "purchase_order.receipt_status is empty when no receipt was created, even if goods are still to arrive: check order lines too.",
)


def _apply_sap(catalog: Catalog) -> Catalog:
    present = {c.name.upper() for t in catalog.tables for c in t.columns} & SAP_FIELDS.keys()
    if len(present) < MIN_FIELDS:
        return catalog
    tables = []
    for t in catalog.tables:
        columns = tuple(replace(c, meaning=SAP_FIELDS.get(c.name.upper(), c.meaning)) for c in t.columns)
        tables.append(replace(t, columns=columns, meaning=SAP_TABLES.get(t.name.upper(), t.meaning)))
    notes = tuple(note for name, note in SAP_NOTES.items() if name in present)
    return replace(catalog, tables=tuple(tables), packs=(*catalog.packs, "SAP"), notes=(*catalog.notes, *notes))


def _apply_odoo(catalog: Catalog) -> Catalog:
    names = {t.name.lower() for t in catalog.tables}
    if not names >= ODOO_SIGNATURE:
        return catalog
    tables = tuple(replace(t, meaning=ODOO_TABLES.get(t.name.lower(), t.meaning)) for t in catalog.tables)
    return replace(catalog, tables=tables, packs=(*catalog.packs, "Odoo"), notes=(*catalog.notes, *ODOO_NOTES))


def apply_packs(catalog: Catalog) -> Catalog:
    return _apply_odoo(_apply_sap(catalog))
