# Copyright (c) 2026, Biztek and Contributors
# License: MIT

from __future__ import annotations

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import flt

from item_price_check.api.stock import build_warehouse_stock_payload
from item_price_check.constants import WAREHOUSE_EXCLUDE_FIELD
from item_price_check.install import sync_custom_fields
from item_price_check.tests import utils as tu


class TestStockPayload(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		sync_custom_fields()
		cls.company = tu.company()
		cls.item = tu.first_stock_item()
		cls.warehouse = tu.first_warehouse(cls.company)

	def setUp(self):
		if not (self.company and self.item and self.warehouse):
			self.skipTest("Need company, stock item, and warehouse on site")

	def test_payload_with_reservations(self):
		tu.ensure_bin(
			self.item.name,
			self.warehouse,
			actual_qty=100,
			reserved_qty=40,
			reserved_stock=25,
			reserved_qty_for_production=5,
		)
		payload = build_warehouse_stock_payload(self.item.name, include_zero_stock=True)
		row = next(r for r in payload["warehouses"] if r["warehouse"] == self.warehouse)
		# max(40, 25) + 5 = 45; FTS = 55
		self.assertEqual(flt(row["reserved_qty"]), 45)
		self.assertEqual(flt(row["free_to_sell"]), 55)
		self.assertEqual(row["stock_status"], "Available")
		self.assertGreaterEqual(payload["sellable_totals"]["warehouses_available"], 1)

	def test_excluded_warehouse_not_in_sellable_totals(self):
		if not frappe.db.has_column("Warehouse", WAREHOUSE_EXCLUDE_FIELD):
			self.skipTest("Exclude field missing")

		tu.ensure_bin(self.item.name, self.warehouse, actual_qty=50, reserved_qty=0)
		frappe.db.set_value("Warehouse", self.warehouse, WAREHOUSE_EXCLUDE_FIELD, 1, update_modified=False)
		try:
			payload = build_warehouse_stock_payload(self.item.name, include_zero_stock=True)
			row = next(r for r in payload["warehouses"] if r["warehouse"] == self.warehouse)
			self.assertFalse(row["sellable"])
			self.assertEqual(row["stock_status"], "Excluded")
			# Excluded warehouse qty must not inflate sellable FTS.
			sellable_warehouses = [r for r in payload["warehouses"] if r["sellable"] and r["warehouse"] == self.warehouse]
			self.assertEqual(sellable_warehouses, [])
		finally:
			frappe.db.set_value("Warehouse", self.warehouse, WAREHOUSE_EXCLUDE_FIELD, 0, update_modified=False)

	def test_zero_stock_filter(self):
		other = frappe.db.get_value(
			"Warehouse",
			{"disabled": 0, "is_group": 0, "name": ["!=", self.warehouse], "company": self.company},
			"name",
		)
		if not other:
			self.skipTest("Need a second warehouse")

		tu.ensure_bin(self.item.name, self.warehouse, actual_qty=10, reserved_qty=0)
		tu.ensure_bin(self.item.name, other, actual_qty=0, reserved_qty=0)

		without_zero = build_warehouse_stock_payload(self.item.name, include_zero_stock=False)
		with_zero = build_warehouse_stock_payload(self.item.name, include_zero_stock=True)

		self.assertTrue(any(r["warehouse"] == self.warehouse for r in without_zero["warehouses"]))
		self.assertFalse(any(r["warehouse"] == other and flt(r["actual_qty"]) == 0 for r in without_zero["warehouses"]))
		self.assertTrue(any(r["warehouse"] == other for r in with_zero["warehouses"]))

	def test_negative_and_unavailable_status(self):
		tu.ensure_bin(self.item.name, self.warehouse, actual_qty=5, reserved_qty=5)
		payload = build_warehouse_stock_payload(self.item.name, include_zero_stock=True)
		row = next(r for r in payload["warehouses"] if r["warehouse"] == self.warehouse)
		self.assertEqual(flt(row["free_to_sell"]), 0)
		self.assertEqual(row["stock_status"], "Unavailable")

		tu.ensure_bin(self.item.name, self.warehouse, actual_qty=5, reserved_qty=8)
		payload = build_warehouse_stock_payload(self.item.name, include_zero_stock=True)
		row = next(r for r in payload["warehouses"] if r["warehouse"] == self.warehouse)
		self.assertEqual(flt(row["free_to_sell"]), -3)
		self.assertEqual(row["stock_status"], "Negative")
