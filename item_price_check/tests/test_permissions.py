# Copyright (c) 2026, Biztek and Contributors
# License: MIT

from __future__ import annotations

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from item_price_check.api.page_data import get_item_details, get_item_price_check_data
from item_price_check.tests import utils as tu


class TestItemPriceCheckPermissions(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.item = tu.first_stock_item()

	def setUp(self):
		if not self.item:
			self.skipTest("Need a stock item")

	def test_read_permission_enforced(self):
		with patch("item_price_check.api.page_data.frappe.has_permission") as mocked:
			mocked.side_effect = frappe.PermissionError
			with self.assertRaises(frappe.PermissionError):
				get_item_details(self.item.name)
			with self.assertRaises(frappe.PermissionError):
				get_item_price_check_data(self.item.name)

	def test_guest_cannot_call(self):
		frappe.set_user("Guest")
		try:
			with self.assertRaises((frappe.PermissionError, frappe.ValidationError)):
				get_item_price_check_data(self.item.name)
		finally:
			frappe.set_user("Administrator")

	def test_empty_item_throws(self):
		with self.assertRaises(frappe.ValidationError):
			get_item_details("")
