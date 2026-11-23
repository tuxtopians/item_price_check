# Copyright (c) 2026, Biztek and Contributors
# License: MIT

"""Shared helpers for Item Price Check tests."""

from __future__ import annotations

from unittest.mock import patch

import frappe
from frappe.utils import flt, today


def company() -> str | None:
	return frappe.defaults.get_user_default("Company") or frappe.db.get_single_value(
		"Global Defaults", "default_company"
	)


def first_stock_item():
	return frappe.db.get_value(
		"Item",
		{"disabled": 0, "is_stock_item": 1, "has_variants": 0},
		["name", "item_name", "item_group", "stock_uom"],
		as_dict=True,
	)


def first_customer():
	return frappe.db.get_value("Customer", {"disabled": 0}, "name")


def first_warehouse(company_name: str | None = None):
	filters = {"disabled": 0, "is_group": 0}
	if company_name:
		filters["company"] = company_name
	return frappe.db.get_value("Warehouse", filters, "name")


def ensure_bin(item_code: str, warehouse: str, **qty_fields) -> None:
	"""Upsert Bin qty fields for tests (no SLE)."""
	name = frappe.db.get_value("Bin", {"item_code": item_code, "warehouse": warehouse}, "name")
	values = {
		"actual_qty": 0,
		"reserved_qty": 0,
		"reserved_stock": 0,
		"reserved_qty_for_production": 0,
		"reserved_qty_for_sub_contract": 0,
		"reserved_qty_for_production_plan": 0,
		**qty_fields,
	}
	if name:
		frappe.db.set_value("Bin", name, values, update_modified=False)
		return

	stock_uom = frappe.db.get_value("Item", item_code, "stock_uom")
	company_name = frappe.db.get_value("Warehouse", warehouse, "company")
	doc = frappe.get_doc(
		{
			"doctype": "Bin",
			"item_code": item_code,
			"warehouse": warehouse,
			"stock_uom": stock_uom,
			"company": company_name,
			**values,
		}
	)
	doc.insert(ignore_permissions=True)


def make_submitted_si(
	*,
	company_name: str,
	customer: str,
	item: str,
	qty: float,
	rate: float,
	currency: str | None = None,
	conversion_rate: float = 1,
	is_return: int = 0,
	posting_date: str | None = None,
):
	"""Insert a submitted Sales Invoice with update_stock off."""
	company_currency = frappe.get_cached_value("Company", company_name, "default_currency")
	currency = currency or company_currency
	si = frappe.new_doc("Sales Invoice")
	si.company = company_name
	si.customer = customer
	si.currency = currency
	si.conversion_rate = conversion_rate
	si.posting_date = posting_date or today()
	si.due_date = posting_date or today()
	si.set_posting_time = 1
	si.update_stock = 0
	si.is_return = is_return
	si.append(
		"items",
		{
			"item_code": item,
			"qty": qty if not is_return else -abs(flt(qty)),
			"rate": rate,
		},
	)
	# document.py imports update_global_search by name; patch the bound symbol.
	with patch("frappe.model.document.update_global_search"):
		si.insert(ignore_permissions=True)
		si.submit()
	return si


def set_warehouse_flags(warehouse: str, **flags) -> None:
	frappe.db.set_value("Warehouse", warehouse, flags, update_modified=False)


def flt_eq(a, b, precision: int = 3) -> bool:
	return flt(a, precision) == flt(b, precision)
