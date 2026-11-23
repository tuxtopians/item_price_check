# Copyright (c) 2026, Biztek and Contributors
# License: MIT

from __future__ import annotations

import frappe
from frappe.tests import IntegrationTestCase

from item_price_check.api.page_data import (
	get_free_to_sell_stock,
	get_item_details,
	get_item_price_check_data,
	get_last_sales_history,
	get_warehouse_stock,
)
from item_price_check.tests import utils as tu


class TestItemPriceCheckAPI(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.company = tu.company()
		cls.item = tu.first_stock_item()
		cls.customer = tu.first_customer()
		cls.warehouse = tu.first_warehouse(cls.company)

	def setUp(self):
		if not (self.company and self.item and self.customer and self.warehouse):
			self.skipTest("Need company, item, customer, warehouse")

	def test_get_item_details(self):
		details = get_item_details(self.item.name)
		self.assertEqual(details["item_code"], self.item.name)
		self.assertEqual(details["item_group"], self.item.item_group)
		self.assertEqual(details["stock_uom"], self.item.stock_uom)

	def test_resolve_by_barcode(self):
		from unittest.mock import patch

		barcode = f"IPC-TEST-{frappe.generate_hash(length=8)}"
		frappe.db.delete("Item Barcode", {"barcode": barcode})
		with patch("frappe.model.document.update_global_search"):
			frappe.get_doc(
				{
					"doctype": "Item Barcode",
					"parent": self.item.name,
					"parenttype": "Item",
					"parentfield": "barcodes",
					"barcode": barcode,
				}
			).insert(ignore_permissions=True)

		details = get_item_details(barcode)
		self.assertEqual(details["item_code"], self.item.name)
		self.assertIn(barcode, details["barcodes"])

	def test_missing_item_throws(self):
		with self.assertRaises(frappe.ValidationError):
			get_item_details("IPC-DOES-NOT-EXIST-XYZ")

	def test_combined_payload_keys(self):
		tu.ensure_bin(self.item.name, self.warehouse, actual_qty=20, reserved_qty=5)
		data = get_item_price_check_data(self.item.name)
		for key in (
			"item",
			"warehouses",
			"totals",
			"sellable_totals",
			"sales_history",
			"price_summary",
		):
			self.assertIn(key, data)
		self.assertEqual(data["item"]["item_code"], self.item.name)
		self.assertIn("warehouses_available", data["sellable_totals"])

	def test_warehouse_and_fts_endpoints(self):
		tu.ensure_bin(self.item.name, self.warehouse, actual_qty=30, reserved_qty=10)
		stock = get_warehouse_stock(self.item.name, include_zero_stock=1)
		fts = get_free_to_sell_stock(self.item.name)
		self.assertTrue(stock["warehouses"])
		self.assertEqual(fts["item_code"], self.item.name)
		self.assertIn("free_to_sell", fts)

	def test_sales_history_and_returns(self):
		company_currency = frappe.get_cached_value("Company", self.company, "default_currency")
		si = tu.make_submitted_si(
			company_name=self.company,
			customer=self.customer,
			item=self.item.name,
			qty=2,
			rate=55,
			currency=company_currency,
		)
		ret = tu.make_submitted_si(
			company_name=self.company,
			customer=self.customer,
			item=self.item.name,
			qty=1,
			rate=55,
			currency=company_currency,
			is_return=1,
		)

		result = get_last_sales_history(self.item.name, limit=5)
		names = {r["sales_invoice"] for r in result["sales_history"]}
		self.assertIn(si.name, names)
		self.assertIn(ret.name, names)
		return_row = next(r for r in result["sales_history"] if r["sales_invoice"] == ret.name)
		self.assertEqual(return_row["is_return"], 1)
		self.assertEqual(result["price_summary"]["currency"], company_currency)
		self.assertIsNotNone(result["price_summary"]["last_selling_price"])

	def test_sales_history_limit(self):
		# Ensure at least one row; limit clamp is covered by summary unit tests + this call.
		result = get_last_sales_history(self.item.name, limit=1)
		self.assertLessEqual(len(result["sales_history"]), 1)

	def test_multi_currency_price_summary_not_mixed(self):
		from item_price_check.api.sales import build_price_summary

		company_currency = frappe.get_cached_value("Company", self.company, "default_currency")
		other_currency = "USD" if company_currency != "USD" else "EUR"
		history = [
			{"rate": 10, "currency": company_currency, "is_return": 0},
			{"rate": 99, "currency": other_currency, "is_return": 0},
			{"rate": 12, "currency": company_currency, "is_return": 0},
		]
		summary = build_price_summary(history)
		self.assertEqual(summary["currency"], company_currency)
		self.assertEqual(summary["highest_selling_price"], 12)
		self.assertEqual(summary["lowest_selling_price"], 10)
		self.assertEqual(summary["transaction_count"], 2)
