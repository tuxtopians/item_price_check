# Copyright (c) 2026, Biztek and Contributors
# License: MIT

"""Local demo data for Item Price Check (dev.local only).

Run:
	bench --site dev.local execute item_price_check.demo.setup_demo_data
"""

from __future__ import annotations

from datetime import timedelta
from contextlib import contextmanager
from unittest.mock import patch

import frappe
from frappe.utils import add_days, flt, getdate, today

from item_price_check.constants import WAREHOUSE_EXCLUDE_FIELD
from item_price_check.install import sync_custom_fields

DEMO_ITEM = "IPC-DEMO-ITEM"
DEMO_BARCODE = "890100IPCDEMO01"
DEMO_CUSTOMER = "IPC Demo Customer"


@contextmanager
def _quiet_doc_hooks():
	"""Skip Redis global-search + disabled Server Scripts during local demo seeding."""
	with (
		patch("frappe.model.document.update_global_search"),
		patch("frappe.model.document.run_server_script_for_doc_event"),
	):
		yield


def setup_demo_data():
	"""Create a demo item, warehouse stock, and sales history for local testing."""
	sync_custom_fields()
	company = _company()
	item = _ensure_item()
	customer = _ensure_customer()
	warehouses = _ensure_warehouses(company)
	_seed_bins(item, warehouses)
	invoices = _seed_sales(company, customer, item)

	frappe.db.commit()
	return {
		"item_code": item,
		"barcode": DEMO_BARCODE,
		"customer": customer,
		"warehouses": warehouses,
		"sales_invoices": invoices,
		"hint": "Open Desk → Item Price Check → select IPC-DEMO-ITEM (or scan barcode 890100IPCDEMO01)",
	}


def clear_demo_data():
	"""Remove demo SIs / bins / item / customer created by setup_demo_data."""
	for name in frappe.get_all(
		"Sales Invoice",
		filters={"customer": DEMO_CUSTOMER},
		pluck="name",
	):
		doc = frappe.get_doc("Sales Invoice", name)
		if doc.docstatus == 1:
			with _quiet_doc_hooks():
				doc.cancel()
		frappe.delete_doc("Sales Invoice", name, force=True, ignore_permissions=True)

	frappe.db.delete("Bin", {"item_code": DEMO_ITEM})
	frappe.db.delete("Item Barcode", {"parent": DEMO_ITEM})

	if frappe.db.exists("Item", DEMO_ITEM):
		frappe.delete_doc("Item", DEMO_ITEM, force=True, ignore_permissions=True)

	if frappe.db.exists("Customer", DEMO_CUSTOMER):
		frappe.delete_doc("Customer", DEMO_CUSTOMER, force=True, ignore_permissions=True)

	# Demo-only warehouses (leave site warehouses alone).
	for wh in ("IPC Demo Stores - GT", "IPC Demo Damaged - GT"):
		if frappe.db.exists("Warehouse", wh):
			frappe.db.set_value("Warehouse", wh, "disabled", 1, update_modified=False)

	frappe.db.commit()
	return {"cleared": True}


def _company() -> str:
	company = frappe.defaults.get_user_default("Company") or frappe.db.get_single_value(
		"Global Defaults", "default_company"
	)
	if not company:
		frappe.throw("Set a default Company before loading demo data")
	return company


def _ensure_item() -> str:
	if frappe.db.exists("Item", DEMO_ITEM):
		_ensure_barcode(DEMO_ITEM)
		return DEMO_ITEM

	item_group = (
		frappe.db.get_value("Item Group", {"name": "All Item Groups"}, "name")
		or frappe.db.get_value("Item Group", {"is_group": 1}, "name")
		or frappe.db.get_value("Item Group", {}, "name")
	)
	stock_uom = "Nos" if frappe.db.exists("UOM", "Nos") else frappe.db.get_value("UOM", {}, "name")

	with _quiet_doc_hooks():
		doc = frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": DEMO_ITEM,
				"item_name": "IPC Demo Access Point",
				"item_group": item_group,
				"stock_uom": stock_uom,
				"is_stock_item": 1,
				"is_sales_item": 1,
				"include_item_in_manufacturing": 0,
				"description": "Demo item for Item Price Check screen",
			}
		)
		doc.insert(ignore_permissions=True)
	_ensure_barcode(DEMO_ITEM)
	return DEMO_ITEM


def _ensure_barcode(item_code: str):
	if frappe.db.exists("Item Barcode", {"parent": item_code, "barcode": DEMO_BARCODE}):
		return
	with _quiet_doc_hooks():
		frappe.get_doc(
			{
				"doctype": "Item Barcode",
				"parent": item_code,
				"parenttype": "Item",
				"parentfield": "barcodes",
				"barcode": DEMO_BARCODE,
			}
		).insert(ignore_permissions=True)


def _ensure_customer() -> str:
	if frappe.db.exists("Customer", DEMO_CUSTOMER):
		return DEMO_CUSTOMER
	with _quiet_doc_hooks():
		frappe.get_doc(
			{
				"doctype": "Customer",
				"customer_name": DEMO_CUSTOMER,
				"customer_type": "Company",
				"customer_group": frappe.db.get_single_value("Selling Settings", "customer_group")
				or frappe.db.get_value("Customer Group", {"is_group": 0}, "name"),
				"territory": frappe.db.get_single_value("Selling Settings", "territory")
				or frappe.db.get_value("Territory", {"is_group": 0}, "name"),
			}
		).insert(ignore_permissions=True)
	return DEMO_CUSTOMER


def _ensure_warehouses(company: str) -> dict:
	"""Return named warehouses used by the demo seed."""
	abbr = frappe.get_cached_value("Company", company, "abbr") or "GT"
	stores_name = f"IPC Demo Stores - {abbr}"
	damaged_name = f"IPC Demo Damaged - {abbr}"

	# Prefer existing site warehouses when present.
	existing_stores = frappe.db.get_value(
		"Warehouse",
		{"company": company, "is_group": 0, "disabled": 0, "name": ["like", "Stores%"]},
		"name",
	) or frappe.db.get_value(
		"Warehouse",
		{"company": company, "is_group": 0, "disabled": 0, "warehouse_type": ["is", "not set"]},
		"name",
	)

	stores = existing_stores or _ensure_warehouse(stores_name, company, warehouse_type=None)
	secondary = frappe.db.get_value(
		"Warehouse",
		{
			"company": company,
			"is_group": 0,
			"disabled": 0,
			"name": ["!=", stores],
			"warehouse_type": ["not in", ["Transit", "Damaged"]],
		},
		"name",
	)
	if not secondary:
		secondary = _ensure_warehouse(f"IPC Demo Showroom - {abbr}", company)

	damaged_type = _ensure_warehouse_type("Damaged")
	damaged = _ensure_warehouse(damaged_name, company, warehouse_type=damaged_type)
	if frappe.db.has_column("Warehouse", WAREHOUSE_EXCLUDE_FIELD):
		frappe.db.set_value("Warehouse", damaged, WAREHOUSE_EXCLUDE_FIELD, 1, update_modified=False)

	transit = frappe.db.get_value(
		"Warehouse",
		{"company": company, "warehouse_type": "Transit", "is_group": 0},
		"name",
	)

	return {
		"stores": stores,
		"secondary": secondary,
		"damaged": damaged,
		"transit": transit,
	}


def _ensure_warehouse_type(name: str) -> str | None:
	if not frappe.db.exists("DocType", "Warehouse Type"):
		return None
	if frappe.db.exists("Warehouse Type", name):
		return name
	with _quiet_doc_hooks():
		frappe.get_doc({"doctype": "Warehouse Type", "name": name}).insert(ignore_permissions=True)
	return name


def _ensure_warehouse(name: str, company: str, warehouse_type: str | None = None) -> str:
	if frappe.db.exists("Warehouse", name):
		frappe.db.set_value("Warehouse", name, "disabled", 0, update_modified=False)
		if warehouse_type is not None:
			frappe.db.set_value("Warehouse", name, "warehouse_type", warehouse_type, update_modified=False)
		return name

	parent = frappe.db.get_value("Warehouse", {"company": company, "is_group": 1}, "name")
	doc = frappe.get_doc(
		{
			"doctype": "Warehouse",
			"warehouse_name": name.rsplit(" - ", 1)[0],
			"company": company,
			"parent_warehouse": parent,
			"is_group": 0,
			"warehouse_type": warehouse_type,
		}
	)
	# warehouse_name + company abbr may rename; keep requested name if possible.
	doc.flags.ignore_permissions = True
	with _quiet_doc_hooks():
		doc.insert()
	return doc.name


def _seed_bins(item_code: str, warehouses: dict):
	"""Set illustrative Bin quantities (no SLE) for the demo item."""
	_upsert_bin(
		item_code,
		warehouses["stores"],
		actual_qty=150,
		reserved_qty=30,
		reserved_stock=20,
	)
	_upsert_bin(
		item_code,
		warehouses["secondary"],
		actual_qty=45,
		reserved_qty=10,
		reserved_stock=0,
	)
	_upsert_bin(
		item_code,
		warehouses["damaged"],
		actual_qty=8,
		reserved_qty=0,
		reserved_stock=0,
	)
	if warehouses.get("transit"):
		_upsert_bin(
			item_code,
			warehouses["transit"],
			actual_qty=12,
			reserved_qty=0,
			reserved_stock=0,
		)


def _upsert_bin(item_code: str, warehouse: str, **qty_fields):
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
	company = frappe.db.get_value("Warehouse", warehouse, "company")
	with _quiet_doc_hooks():
		frappe.get_doc(
			{
				"doctype": "Bin",
				"item_code": item_code,
				"warehouse": warehouse,
				"stock_uom": stock_uom,
				"company": company,
				**values,
			}
		).insert(ignore_permissions=True)


def _seed_sales(company: str, customer: str, item_code: str) -> list[str]:
	"""Create a few submitted SIs + one return if none exist yet for the demo customer."""
	existing = frappe.get_all(
		"Sales Invoice",
		filters={"customer": customer, "docstatus": 1},
		pluck="name",
	)
	if len(existing) >= 5:
		return existing

	currency = frappe.get_cached_value("Company", company, "default_currency")
	base = getdate(today())
	specs = [
		{"days_ago": 20, "qty": 2, "rate": 120, "is_return": 0},
		{"days_ago": 14, "qty": 1, "rate": 135, "is_return": 0},
		{"days_ago": 9, "qty": 3, "rate": 110, "is_return": 0},
		{"days_ago": 4, "qty": 1, "rate": 125, "is_return": 0},
		{"days_ago": 2, "qty": 1, "rate": 125, "is_return": 1},
	]
	names = list(existing)
	for spec in specs:
		if len(names) >= 5:
			break
		posting = add_days(base, -spec["days_ago"])
		si = _make_si(
			company=company,
			customer=customer,
			item_code=item_code,
			qty=spec["qty"],
			rate=spec["rate"],
			currency=currency,
			is_return=spec["is_return"],
			posting_date=posting,
		)
		names.append(si)
	return names


def _make_si(
	*,
	company: str,
	customer: str,
	item_code: str,
	qty: float,
	rate: float,
	currency: str,
	is_return: int,
	posting_date,
) -> str:
	si = frappe.new_doc("Sales Invoice")
	si.company = company
	si.customer = customer
	si.currency = currency
	si.conversion_rate = 1
	si.posting_date = posting_date
	si.due_date = posting_date
	si.set_posting_time = 1
	si.update_stock = 0
	si.is_return = is_return
	si.append(
		"items",
		{
			"item_code": item_code,
			"qty": -abs(flt(qty)) if is_return else flt(qty),
			"rate": rate,
		},
	)
	with _quiet_doc_hooks():
		si.insert(ignore_permissions=True)
		si.submit()
	return si.name
