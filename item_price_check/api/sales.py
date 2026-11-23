# Copyright (c) 2026, Biztek and Contributors
# License: MIT

"""Sales history and price summary for Item Price Check."""

from __future__ import annotations

import frappe
from frappe.utils import flt

from item_price_check.constants import DEFAULT_SALES_HISTORY_LIMIT, MAX_SALES_HISTORY_LIMIT


def fetch_last_sales_history(item_code: str, limit: int = DEFAULT_SALES_HISTORY_LIMIT) -> list[dict]:
	"""Latest submitted Sales Invoice lines for an item."""
	limit = min(max(int(limit or DEFAULT_SALES_HISTORY_LIMIT), 1), MAX_SALES_HISTORY_LIMIT)

	si = frappe.qb.DocType("Sales Invoice")
	sii = frappe.qb.DocType("Sales Invoice Item")

	rows = (
		frappe.qb.from_(sii)
		.inner_join(si)
		.on(sii.parent == si.name)
		.select(
			si.name.as_("sales_invoice"),
			si.posting_date,
			si.currency,
			si.is_return,
			si.customer,
			si.customer_name,
			si.creation,
			sii.qty,
			sii.rate,
			sii.stock_uom,
			sii.uom,
		)
		.where((sii.item_code == item_code) & (si.docstatus == 1))
		.orderby(si.posting_date, order=frappe.qb.desc)
		.orderby(si.creation, order=frappe.qb.desc)
		.limit(limit)
		.run(as_dict=True)
	)

	history = []
	for row in rows or []:
		history.append(
			{
				"sales_invoice": row.sales_invoice,
				"posting_date": row.posting_date,
				"qty": flt(row.qty),
				"rate": flt(row.rate),
				"currency": row.currency,
				"is_return": int(row.is_return or 0),
				"customer": row.customer,
				"customer_name": row.customer_name,
				"stock_uom": row.stock_uom or row.uom,
			}
		)
	return history


def build_price_summary(history: list[dict]) -> dict:
	"""Last / average / high / low selling price for one currency.

	Uses the currency of the newest non-return sale when present; otherwise the
	newest row's currency. Rows in other currencies are ignored for averages.
	"""
	empty = {
		"currency": "",
		"last_selling_price": None,
		"average_selling_price": None,
		"highest_selling_price": None,
		"lowest_selling_price": None,
		"transaction_count": 0,
	}
	if not history:
		return empty

	currency = _preferred_currency(history)
	priced = [flt(r["rate"]) for r in history if r.get("currency") == currency and not r.get("is_return")]
	if not priced:
		# Fall back to all rows in preferred currency, including returns.
		priced = [flt(r["rate"]) for r in history if r.get("currency") == currency]
	if not priced:
		return empty

	last_price = None
	for row in history:
		if row.get("currency") == currency and not row.get("is_return"):
			last_price = flt(row["rate"])
			break
	if last_price is None:
		last_price = priced[0]

	return {
		"currency": currency,
		"last_selling_price": last_price,
		"average_selling_price": flt(sum(priced) / len(priced)),
		"highest_selling_price": max(priced),
		"lowest_selling_price": min(priced),
		"transaction_count": len(priced),
	}


def _preferred_currency(history: list[dict]) -> str:
	for row in history:
		if not row.get("is_return") and row.get("currency"):
			return row["currency"]
	for row in history:
		if row.get("currency"):
			return row["currency"]
	return ""
