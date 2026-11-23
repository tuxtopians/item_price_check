# Copyright (c) 2026, Biztek and Contributors
# License: MIT

PAGE_NAME = "item-price-check"
PAGE_LABEL = "Item Price Check"
PAGE_MODULE = "Item Price Check"

WORKSPACE_NAMES = ("Selling", "Sales")
SIDEBAR_NAMES = ("Selling", "Sales")
AFTER_LINKS = (
	"Item Price",
	"Price List",
	"Item",
	"Sales Order",
	"Sales Invoice",
)

DEFAULT_SALES_HISTORY_LIMIT = 5
MAX_SALES_HISTORY_LIMIT = 20

# Warehouse Type names excluded from sellable / FTS totals (case-insensitive match).
DEFAULT_EXCLUDED_WAREHOUSE_TYPES = ("Damaged", "Transit")

WAREHOUSE_EXCLUDE_FIELD = "custom_ipc_exclude_from_fts"
WAREHOUSE_EXCLUDE_FIELD_LABEL = "Exclude from Free To Sell"

CUSTOM_FIELDS = {
	"Warehouse": [
		{
			"fieldname": WAREHOUSE_EXCLUDE_FIELD,
			"label": WAREHOUSE_EXCLUDE_FIELD_LABEL,
			"fieldtype": "Check",
			"insert_after": "disabled",
			"description": "Exclude this warehouse from Item Price Check free-to-sell totals",
		}
	]
}
