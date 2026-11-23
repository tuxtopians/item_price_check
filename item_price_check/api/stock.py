# Copyright (c) 2026, Biztek and Contributors
# License: MIT

"""Warehouse stock and Free To Sell helpers.

Reservation model (ERPNext v16 Bin)
-----------------------------------
- ``reserved_qty`` — soft reserve from open Sales Orders (and packed items).
- ``reserved_stock`` — hard reserve from submitted Stock Reservation Entries.
- ``reserved_qty_for_production`` / ``_for_sub_contract`` / ``_for_production_plan`` —
  manufacturing / subcontract holds.

Sales Order soft qty already includes lines that also have an SRE. Adding
``reserved_qty`` and ``reserved_stock`` would double-count, so sales-side
reserve is ``max(reserved_qty, reserved_stock)``. Manufacturing holds are
separate and are always added.
"""

from __future__ import annotations

import frappe
from frappe.utils import cint, flt

from item_price_check.constants import (
	DEFAULT_EXCLUDED_WAREHOUSE_TYPES,
	WAREHOUSE_EXCLUDE_FIELD,
)


def calculate_applicable_reserved(
	reserved_qty: float = 0,
	reserved_stock: float = 0,
	reserved_qty_for_production: float = 0,
	reserved_qty_for_sub_contract: float = 0,
	reserved_qty_for_production_plan: float = 0,
) -> float:
	"""Return reserved qty that blocks free-to-sell without double-counting SO/SRE."""
	sales_reserved = max(flt(reserved_qty), flt(reserved_stock))
	manufacturing = (
		flt(reserved_qty_for_production)
		+ flt(reserved_qty_for_sub_contract)
		+ flt(reserved_qty_for_production_plan)
	)
	return sales_reserved + manufacturing


def calculate_free_to_sell(actual_qty: float, applicable_reserved: float) -> float:
	"""FTS = actual - applicable reserved. Negative stock is returned as-is."""
	return flt(actual_qty) - flt(applicable_reserved)


def stock_status(free_to_sell: float) -> str:
	fts = flt(free_to_sell)
	if fts < 0:
		return "Negative"
	if fts == 0:
		return "Unavailable"
	return "Available"


def is_warehouse_sellable(
	*,
	disabled: int = 0,
	is_group: int = 0,
	is_rejected_warehouse: int = 0,
	warehouse_type: str | None = None,
	exclude_from_fts: int = 0,
	excluded_types: tuple[str, ...] | list[str] | None = None,
) -> bool:
	"""Return True when the warehouse may contribute to Free To Sell totals."""
	if cint(disabled) or cint(is_group) or cint(is_rejected_warehouse) or cint(exclude_from_fts):
		return False

	excluded = {
		(t or "").strip().lower()
		for t in (excluded_types if excluded_types is not None else DEFAULT_EXCLUDED_WAREHOUSE_TYPES)
		if (t or "").strip()
	}
	wt = (warehouse_type or "").strip().lower()
	if wt and wt in excluded:
		return False
	return True


def fetch_warehouse_stock_rows(item_code: str, include_zero_stock: bool = False) -> list[dict]:
	"""Return Bin rows joined to Warehouse for an item, scoped by Warehouse permissions."""
	warehouses = _permitted_warehouses()
	if not warehouses:
		return []

	bin = frappe.qb.DocType("Bin")
	wh = frappe.qb.DocType("Warehouse")

	query = (
		frappe.qb.from_(bin)
		.inner_join(wh)
		.on(bin.warehouse == wh.name)
		.select(
			bin.warehouse,
			bin.actual_qty,
			bin.reserved_qty,
			bin.reserved_stock,
			bin.reserved_qty_for_production,
			bin.reserved_qty_for_sub_contract,
			bin.reserved_qty_for_production_plan,
			bin.stock_uom,
			wh.warehouse_type,
			wh.disabled,
			wh.is_group,
			wh.is_rejected_warehouse,
		)
		.where((bin.item_code == item_code) & (bin.warehouse.isin(warehouses)))
		.orderby(wh.name)
	)

	if frappe.db.has_column("Warehouse", WAREHOUSE_EXCLUDE_FIELD):
		query = query.select(wh[WAREHOUSE_EXCLUDE_FIELD].as_("exclude_from_fts"))

	rows = query.run(as_dict=True) or []

	if not include_zero_stock:
		rows = [
			r
			for r in rows
			if flt(r.actual_qty)
			or flt(r.reserved_qty)
			or flt(r.reserved_stock)
			or flt(r.reserved_qty_for_production)
			or flt(r.reserved_qty_for_sub_contract)
			or flt(r.reserved_qty_for_production_plan)
		]

	return rows


def build_warehouse_stock_payload(item_code: str, include_zero_stock: bool = False) -> dict:
	"""Build warehouse stock table + sellable FTS summary for an item."""
	rows = fetch_warehouse_stock_rows(item_code, include_zero_stock=include_zero_stock)
	warehouses = []
	total_actual = 0.0
	total_reserved = 0.0
	total_fts = 0.0
	warehouses_with_stock = 0
	sellable_actual = 0.0
	sellable_reserved = 0.0
	sellable_fts = 0.0

	for row in rows:
		actual = flt(row.actual_qty)
		reserved = calculate_applicable_reserved(
			reserved_qty=row.reserved_qty,
			reserved_stock=row.reserved_stock,
			reserved_qty_for_production=row.reserved_qty_for_production,
			reserved_qty_for_sub_contract=row.reserved_qty_for_sub_contract,
			reserved_qty_for_production_plan=row.reserved_qty_for_production_plan,
		)
		fts = calculate_free_to_sell(actual, reserved)
		sellable = is_warehouse_sellable(
			disabled=row.get("disabled"),
			is_group=row.get("is_group"),
			is_rejected_warehouse=row.get("is_rejected_warehouse"),
			warehouse_type=row.get("warehouse_type"),
			exclude_from_fts=row.get("exclude_from_fts"),
		)
		status = stock_status(fts) if sellable else "Excluded"

		warehouses.append(
			{
				"warehouse": row.warehouse,
				"actual_qty": actual,
				"reserved_qty": reserved,
				"free_to_sell": fts,
				"stock_status": status,
				"sellable": sellable,
				"stock_uom": row.stock_uom,
				"warehouse_type": row.get("warehouse_type") or "",
				"reserved_qty_so": flt(row.reserved_qty),
				"reserved_stock_sre": flt(row.reserved_stock),
				"reserved_qty_for_production": flt(row.reserved_qty_for_production),
				"reserved_qty_for_sub_contract": flt(row.reserved_qty_for_sub_contract),
				"reserved_qty_for_production_plan": flt(row.reserved_qty_for_production_plan),
			}
		)

		total_actual += actual
		total_reserved += reserved
		total_fts += fts

		if sellable:
			sellable_actual += actual
			sellable_reserved += reserved
			sellable_fts += fts
			if fts > 0:
				warehouses_with_stock += 1

	return {
		"warehouses": warehouses,
		"totals": {
			"actual_qty": total_actual,
			"reserved_qty": total_reserved,
			"free_to_sell": total_fts,
		},
		"sellable_totals": {
			"actual_qty": sellable_actual,
			"reserved_qty": sellable_reserved,
			"free_to_sell": sellable_fts,
			"warehouses_available": warehouses_with_stock,
		},
	}


def _permitted_warehouses() -> list[str]:
	"""Warehouses the current user may read (User Permissions + role perms)."""
	return frappe.get_list(
		"Warehouse",
		filters={"is_group": 0},
		pluck="name",
		limit=10000,
		ignore_permissions=False,
	)
