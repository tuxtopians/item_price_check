# Copyright (c) 2026, Biztek and Contributors
# License: MIT

from __future__ import annotations

from frappe.tests import UnitTestCase
from frappe.utils import flt

from item_price_check.api.sales import build_price_summary


class TestSalesSummary(UnitTestCase):
	def test_empty_history(self):
		summary = build_price_summary([])
		self.assertIsNone(summary["last_selling_price"])
		self.assertEqual(summary["transaction_count"], 0)

	def test_single_currency_stats(self):
		history = [
			{"rate": 100, "currency": "AED", "is_return": 0},
			{"rate": 120, "currency": "AED", "is_return": 0},
			{"rate": 80, "currency": "AED", "is_return": 0},
		]
		summary = build_price_summary(history)
		self.assertEqual(summary["currency"], "AED")
		self.assertEqual(summary["last_selling_price"], 100)
		self.assertEqual(summary["highest_selling_price"], 120)
		self.assertEqual(summary["lowest_selling_price"], 80)
		self.assertEqual(flt(summary["average_selling_price"], 2), 100.0)
		self.assertEqual(summary["transaction_count"], 3)

	def test_ignores_other_currency(self):
		history = [
			{"rate": 100, "currency": "AED", "is_return": 0},
			{"rate": 50, "currency": "USD", "is_return": 0},
			{"rate": 90, "currency": "AED", "is_return": 0},
		]
		summary = build_price_summary(history)
		self.assertEqual(summary["currency"], "AED")
		self.assertEqual(summary["transaction_count"], 2)
		self.assertEqual(summary["highest_selling_price"], 100)
		self.assertEqual(summary["lowest_selling_price"], 90)

	def test_returns_excluded_from_preferred_stats(self):
		history = [
			{"rate": 100, "currency": "AED", "is_return": 0},
			{"rate": 40, "currency": "AED", "is_return": 1},
			{"rate": 120, "currency": "AED", "is_return": 0},
		]
		summary = build_price_summary(history)
		self.assertEqual(summary["last_selling_price"], 100)
		self.assertEqual(summary["transaction_count"], 2)
		self.assertEqual(summary["lowest_selling_price"], 100)

	def test_return_only_history_falls_back(self):
		history = [{"rate": 40, "currency": "AED", "is_return": 1}]
		summary = build_price_summary(history)
		self.assertEqual(summary["currency"], "AED")
		self.assertEqual(summary["last_selling_price"], 40)
		self.assertEqual(summary["transaction_count"], 1)
