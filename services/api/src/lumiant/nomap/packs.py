"""Knowledge packs: the standard meaning of fields in systems we recognise, so customers map nothing by hand.

A pack applies only when enough of its field names appear, and it labels meanings as known, not proven: customers
reuse standard fields in their own ways, so the agent still checks them against the data. Meanings here are SAP's
standard data dictionary descriptions; they must be confirmed on a real SAP sandbox before any customer relies on them.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

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
    "Translatable names, such as product_template.name and uom_uom.name, are JSON keyed by language: use name->>'en_US'. Check the column type first: other names, such as stock_location.name, are plain text.",
    'product_product.standard_price (cost) is JSON keyed by company id, such as {"1": 70.0}: read the company\'s key.',
    "There may be several companies: say which company_id you count, or report each.",
    "product_template is the product as users see it; product_product holds its variants, so counts differ.",
    "purchase_order.receipt_status is empty when no receipt was created, even if goods are still to arrive: check order lines too.",
)


@dataclass(frozen=True)
class TablePack:
    """A system recognised by its standard table names, with what those tables mean and the rules that apply."""

    name: str
    signature: frozenset[str]  # every one of these canonical table names must exist
    tables: dict[str, str]
    notes: tuple[str, ...]


def _canonical(table: str) -> str:
    """Business Central stores tables as 'Company$Item Ledger Entry$<app id>'; the part between '$' is the table."""
    parts = table.split("$")
    return (parts[1] if len(parts) >= 2 else table).lower()


# These packs follow each vendor's documented standard tables. None has been checked on a real customer system yet,
# so the agent is told they are unconfirmed; its own checks and the data decide.
ORACLE_EBS = TablePack(
    "Oracle E-Business Suite (unconfirmed)",
    frozenset({"mtl_system_items_b", "mtl_onhand_quantities_detail", "mtl_parameters", "mtl_secondary_inventories"}),
    {
        "mtl_system_items_b": "items per inventory organization (SEGMENT1 is usually the item code)",
        "mtl_onhand_quantities_detail": "stock on hand by item, organization, subinventory, locator and lot",
        "mtl_parameters": "inventory organizations, with their costing method",
        "mtl_secondary_inventories": "subinventories; ASSET_INVENTORY 1 is valued stock, 2 is expense",
        "mtl_material_transactions": "inventory transactions; quantities are negative for issues",
        "mtl_lot_numbers": "lots, with expiration dates",
        "cst_item_costs": "item costs per organization and cost type",
        "po_headers_all": "purchase order headers for every operating unit",
        "po_lines_all": "purchase order lines",
        "po_line_locations_all": "purchase order shipments, with quantities ordered and received",
    },
    (
        "On-hand quantity is SUM(PRIMARY_TRANSACTION_QUANTITY) in mtl_onhand_quantities_detail, in the item's primary unit.",
        "Items exist once per organization: join on both INVENTORY_ITEM_ID and ORGANIZATION_ID.",
        "Subinventories with ASSET_INVENTORY = 2 are expense stock and carry no inventory value.",
        "Tables ending in _ALL hold every operating unit: filter ORG_ID or report each.",
        "cst_item_costs has a row per cost type: COST_TYPE_ID 1 is the frozen standard cost; pick the organization's costing method from mtl_parameters.",
    ),
)
DYNAMICS_FO = TablePack(
    "Microsoft Dynamics 365 Finance and Operations (unconfirmed)",
    frozenset({"inventsum", "inventdim", "inventtable", "inventtrans"}),
    {
        "inventsum": "on-hand summary per item and inventory dimension",
        "inventdim": "inventory dimensions: site, warehouse, location, batch and more, behind each INVENTDIMID",
        "inventtable": "released items",
        "inventtrans": "inventory transactions with receipt and issue status",
        "purchtable": "purchase order headers",
        "purchline": "purchase order lines",
    },
    (
        "Every table has DATAAREAID, the legal entity: filter it or report each.",
        "inventsum is per INVENTDIMID: join inventdim to get warehouse (INVENTLOCATIONID), site and batch.",
        "inventsum keeps closed rows (CLOSED = 1); physical on-hand is PHYSICALINVENT, and value is split into posted and physical columns: say which you use.",
        "Exported copies (Synapse Link, Fabric) may show table and column names in lower case.",
    ),
)
BUSINESS_CENTRAL = TablePack(
    "Microsoft Dynamics 365 Business Central (unconfirmed)",
    frozenset({"item", "item ledger entry", "value entry", "location"}),
    {
        "item": "items",
        "item ledger entry": "stock movements per item and location; open entries hold the remaining quantity",
        "value entry": "costs of each movement, actual and expected",
        "location": "locations (warehouses)",
    },
    (
        "Table names include the company, like 'CRONUS$Item Ledger Entry$<id>': each company has its own tables.",
        "On-hand quantity per item and location is SUM(Quantity) of Item Ledger Entry.",
        "Inventory value is the sum of Cost Amount (Actual) and Cost Amount (Expected) in Value Entry: say whether expected cost is included.",
    ),
)
TABLE_PACKS = (ORACLE_EBS, DYNAMICS_FO, BUSINESS_CENTRAL)


def _apply_table_pack(catalog: Catalog, pack: TablePack) -> Catalog:
    names = {_canonical(t.name) for t in catalog.tables}
    if not names >= pack.signature:
        return catalog
    tables = tuple(replace(t, meaning=pack.tables.get(_canonical(t.name), t.meaning)) for t in catalog.tables)
    return replace(catalog, tables=tables, packs=(*catalog.packs, pack.name), notes=(*catalog.notes, *pack.notes))


def _apply_sap(catalog: Catalog) -> Catalog:
    present = {c.name.upper() for t in catalog.tables for c in t.columns} & SAP_FIELDS.keys()
    if len(present) < MIN_FIELDS:
        return catalog
    tables = []
    for t in catalog.tables:
        columns = tuple(replace(c, meaning=SAP_FIELDS.get(c.name.upper(), c.meaning)) for c in t.columns)
        tables.append(replace(t, columns=columns, meaning=SAP_TABLES.get(t.name.upper(), t.meaning)))
    notes = tuple(note for name, note in SAP_NOTES.items() if name in present)
    return replace(
        catalog,
        tables=tuple(tables),
        packs=(*catalog.packs, "SAP (unconfirmed on a real SAP system)"),
        notes=(*catalog.notes, *notes),
    )


def _apply_odoo(catalog: Catalog) -> Catalog:
    names = {t.name.lower() for t in catalog.tables}
    if not names >= ODOO_SIGNATURE:
        return catalog
    tables = tuple(replace(t, meaning=ODOO_TABLES.get(t.name.lower(), t.meaning)) for t in catalog.tables)
    return replace(catalog, tables=tables, packs=(*catalog.packs, "Odoo"), notes=(*catalog.notes, *ODOO_NOTES))


def apply_packs(catalog: Catalog) -> Catalog:
    catalog = _apply_odoo(_apply_sap(catalog))
    for pack in TABLE_PACKS:
        catalog = _apply_table_pack(catalog, pack)
    return catalog
