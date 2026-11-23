# Copyright (c) 2026, Biztek and Contributors
# License: MIT

from __future__ import annotations

from frappe.tests import UnitTestCase

from item_price_check.install import (
	_insert_links_after,
	_link_exists,
	_sidebar_link_row,
	_workspace_link_row,
)


class TestInstallHelpers(UnitTestCase):
	def test_link_exists(self):
		rows = [{"type": "Link", "link_to": "item-price-check"}, {"type": "Card Break"}]
		self.assertTrue(_link_exists(rows, "item-price-check"))
		self.assertFalse(_link_exists(rows, "other"))

	def test_insert_after_matching_link(self):
		rows = [
			{"type": "Link", "link_to": "Item Price", "label": "Item Price"},
			{"type": "Link", "link_to": "Sales Order", "label": "Sales Order"},
		]
		new_rows = [{"type": "Link", "link_to": "item-price-check"}]
		result = _insert_links_after(rows, ("Item Price", "Price List"), new_rows)
		self.assertEqual(result[1]["link_to"], "item-price-check")
		self.assertEqual(result[2]["link_to"], "Sales Order")

	def test_insert_appends_when_anchor_missing(self):
		rows = [{"type": "Link", "link_to": "Sales Order", "label": "Sales Order"}]
		new_rows = [{"type": "Link", "link_to": "item-price-check"}]
		result = _insert_links_after(rows, ("Missing",), new_rows)
		self.assertEqual(result[-1]["link_to"], "item-price-check")

	def test_row_builders(self):
		link = {"label": "Item Price Check", "link_to": "item-price-check", "link_type": "Page"}
		ws = _workspace_link_row(link)
		sb = _sidebar_link_row(link)
		self.assertEqual(ws["type"], "Link")
		self.assertEqual(ws["link_to"], "item-price-check")
		self.assertEqual(sb["child"], 1)
