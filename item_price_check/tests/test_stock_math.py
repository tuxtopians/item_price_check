# Copyright (c) 2026, Biztek and Contributors
# License: MIT

from __future__ import annotations

from frappe.tests import UnitTestCase

from item_price_check.api.stock import (
	calculate_applicable_reserved,
	calculate_free_to_sell,
	is_warehouse_sellable,
	stock_status,
)


class TestStockMath(UnitTestCase):
	def test_fts_basic(self):
		self.assertEqual(calculate_free_to_sell(150, 30), 120)

	def test_fts_negative_stock(self):
		self.assertEqual(calculate_free_to_sell(-5, 0), -5)
		self.assertEqual(calculate_free_to_sell(10, 25), -15)

	def test_no_double_count_so_and_sre(self):
		# SRE is a subset of SO soft reserve — take max, not sum.
		self.assertEqual(
			calculate_applicable_reserved(reserved_qty=50, reserved_stock=30),
			50,
		)
		self.assertEqual(
			calculate_applicable_reserved(reserved_qty=20, reserved_stock=35),
			35,
		)

	def test_manufacturing_reservations_added(self):
		reserved = calculate_applicable_reserved(
			reserved_qty=10,
			reserved_stock=5,
			reserved_qty_for_production=3,
			reserved_qty_for_sub_contract=2,
			reserved_qty_for_production_plan=1,
		)
		self.assertEqual(reserved, 16)
		self.assertEqual(calculate_free_to_sell(100, reserved), 84)

	def test_stock_status(self):
		self.assertEqual(stock_status(12), "Available")
		self.assertEqual(stock_status(0), "Unavailable")
		self.assertEqual(stock_status(-1), "Negative")

	def test_warehouse_sellable_rules(self):
		self.assertTrue(is_warehouse_sellable())
		self.assertFalse(is_warehouse_sellable(disabled=1))
		self.assertFalse(is_warehouse_sellable(is_group=1))
		self.assertFalse(is_warehouse_sellable(is_rejected_warehouse=1))
		self.assertFalse(is_warehouse_sellable(exclude_from_fts=1))
		self.assertFalse(is_warehouse_sellable(warehouse_type="Damaged"))
		self.assertFalse(is_warehouse_sellable(warehouse_type="transit"))
		self.assertTrue(is_warehouse_sellable(warehouse_type="Stores"))
		self.assertTrue(
			is_warehouse_sellable(
				warehouse_type="Damaged",
				excluded_types=("Transit",),
			)
		)
