# Copyright (c) 2026, Biztek and Contributors
# License: MIT

"""Item lookup helpers for Item Price Check."""

from __future__ import annotations

import frappe
from frappe import _


def resolve_item_code(item_or_barcode: str) -> str:
	"""Resolve an Item Code from a code, name, or barcode."""
	value = (item_or_barcode or "").strip()
	if not value:
		frappe.throw(_("Item is required"))

	if frappe.db.exists("Item", value):
		return value

	barcode_item = frappe.db.get_value("Item Barcode", {"barcode": value}, "parent")
	if barcode_item:
		return barcode_item

	by_name = frappe.db.get_value("Item", {"item_name": value}, "name")
	if by_name:
		return by_name

	frappe.throw(_("Item {0} not found").format(value))


def fetch_item_details(item_code: str) -> dict:
	"""Return display fields for the selected item."""
	item = frappe.db.get_value(
		"Item",
		item_code,
		["name", "item_code", "item_name", "item_group", "stock_uom", "disabled"],
		as_dict=True,
	)
	if not item:
		frappe.throw(_("Item {0} not found").format(item_code))

	barcodes = frappe.get_all(
		"Item Barcode",
		filters={"parent": item_code},
		fields=["barcode"],
		order_by="idx asc",
		pluck="barcode",
	)

	return {
		"item_code": item.item_code,
		"item_name": item.item_name,
		"item_group": item.item_group,
		"stock_uom": item.stock_uom,
		"barcode": barcodes[0] if barcodes else "",
		"barcodes": barcodes,
		"disabled": item.disabled,
	}
