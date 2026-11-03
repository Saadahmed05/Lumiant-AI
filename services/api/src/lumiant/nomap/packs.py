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


def apply_packs(catalog: Catalog) -> Catalog:
    present = {c.name.upper() for t in catalog.tables for c in t.columns} & SAP_FIELDS.keys()
    if len(present) < MIN_FIELDS:
        return catalog
    tables = []
    for t in catalog.tables:
        columns = tuple(replace(c, meaning=SAP_FIELDS.get(c.name.upper(), c.meaning)) for c in t.columns)
        tables.append(replace(t, columns=columns, meaning=SAP_TABLES.get(t.name.upper(), t.meaning)))
    notes = tuple(note for name, note in SAP_NOTES.items() if name in present)
    return replace(catalog, tables=tuple(tables), packs=(*catalog.packs, "SAP"), notes=(*catalog.notes, *notes))
