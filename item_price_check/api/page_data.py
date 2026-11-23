# Copyright (c) 2026, Biztek and Contributors
# License: MIT

"""Whitelisted entry points for the Item Price Check desk page."""

from __future__ import annotations

import frappe
from frappe.utils import cint

from item_price_check.api.item import fetch_item_details, resolve_item_code
from item_price_check.api.sales import build_price_summary, fetch_last_sales_history
from item_price_check.api.stock import build_warehouse_stock_payload
from item_price_check.constants import DEFAULT_SALES_HISTORY_LIMIT


def _require_read_permissions():
	frappe.has_permission("Item", "read", throw=True)
	frappe.has_permission("Warehouse", "read", throw=True)
	frappe.has_permission("Sales Invoice", "read", throw=True)


@frappe.whitelist()
def get_item_details(item_code: str):
	"""Return item master fields for the selected item / barcode."""
	_require_read_permissions()
	resolved = resolve_item_code(item_code)
	return fetch_item_details(resolved)


@frappe.whitelist()
def get_warehouse_stock(item_code: str, include_zero_stock: int | str | bool = 0):
	"""Warehouse-wise actual / reserved / free-to-sell stock."""
	_require_read_permissions()
	resolved = resolve_item_code(item_code)
	return build_warehouse_stock_payload(resolved, include_zero_stock=bool(cint(include_zero_stock)))


@frappe.whitelist()
def get_free_to_sell_stock(item_code: str):
	"""Sellable Free To Sell summary for an item."""
	_require_read_permissions()
	resolved = resolve_item_code(item_code)
	payload = build_warehouse_stock_payload(resolved, include_zero_stock=False)
	return {
		"item_code": resolved,
		**payload["sellable_totals"],
	}


@frappe.whitelist()
def get_last_sales_history(item_code: str, limit: int | str = DEFAULT_SALES_HISTORY_LIMIT):
	"""Latest submitted Sales Invoice lines and price summary."""
	_require_read_permissions()
	resolved = resolve_item_code(item_code)
	history = fetch_last_sales_history(resolved, limit=cint(limit) or DEFAULT_SALES_HISTORY_LIMIT)
	return {
		"item_code": resolved,
		"sales_history": history,
		"price_summary": build_price_summary(history),
	}


@frappe.whitelist()
def get_item_price_check_data(
	item_code: str,
	include_zero_stock: int | str | bool = 0,
	limit: int | str = DEFAULT_SALES_HISTORY_LIMIT,
):
	"""Combined payload for the Item Price Check page."""
	_require_read_permissions()
	resolved = resolve_item_code(item_code)
	item = fetch_item_details(resolved)
	stock = build_warehouse_stock_payload(resolved, include_zero_stock=bool(cint(include_zero_stock)))
	history = fetch_last_sales_history(resolved, limit=cint(limit) or DEFAULT_SALES_HISTORY_LIMIT)

	return {
		"item": item,
		"warehouses": stock["warehouses"],
		"totals": stock["totals"],
		"sellable_totals": stock["sellable_totals"],
		"sales_history": history,
		"price_summary": build_price_summary(history),
	}
