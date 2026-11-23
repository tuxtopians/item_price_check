# Copyright (c) 2026, Biztek and Contributors
# License: MIT

from __future__ import annotations

import frappe
from frappe.tests import IntegrationTestCase

from item_price_check.constants import PAGE_LABEL, PAGE_NAME, WAREHOUSE_EXCLUDE_FIELD
from item_price_check.install import (
	after_install,
	after_migrate,
	remove_navigation,
	sync_custom_fields,
	sync_navigation,
	sync_page,
)
from item_price_check.uninstall import after_uninstall, before_uninstall


class TestInstallSync(IntegrationTestCase):
	def test_page_exists_after_sync(self):
		sync_page()
		self.assertTrue(frappe.db.exists("Page", PAGE_NAME))
		page = frappe.get_doc("Page", PAGE_NAME)
		self.assertEqual(page.title, "Item Price Check")
		roles = {r.role for r in page.roles}
		self.assertIn("Sales User", roles)
		self.assertIn("Stock User", roles)
		self.assertIn("System Manager", roles)

	def test_custom_field_created(self):
		sync_custom_fields()
		self.assertTrue(frappe.db.exists("Custom Field", f"Warehouse-{WAREHOUSE_EXCLUDE_FIELD}"))
		self.assertTrue(frappe.db.has_column("Warehouse", WAREHOUSE_EXCLUDE_FIELD))

	def test_navigation_sync_idempotent(self):
		sync_page()
		sync_navigation()
		sync_navigation()
		found = False
		for workspace in ("Sales", "Selling"):
			if not frappe.db.exists("Workspace", workspace):
				continue
			ws = frappe.get_doc("Workspace", workspace)
			if any(r.type == "Link" and r.link_to == PAGE_NAME for r in ws.links):
				found = True
				labels = [r.label for r in ws.links if r.link_to == PAGE_NAME]
				self.assertIn(PAGE_LABEL, labels)
		if frappe.db.exists("Workspace", "Selling") or frappe.db.exists("Workspace", "Sales"):
			self.assertTrue(found)

	def test_after_install_and_migrate_hooks(self):
		after_install()
		after_migrate()
		self.assertTrue(frappe.db.exists("Page", PAGE_NAME))

	def test_remove_and_restore_navigation(self):
		sync_page()
		sync_navigation()
		remove_navigation()
		for workspace in ("Sales", "Selling"):
			if not frappe.db.exists("Workspace", workspace):
				continue
			ws = frappe.get_doc("Workspace", workspace)
			self.assertFalse(any(r.type == "Link" and r.link_to == PAGE_NAME for r in ws.links))
		sync_navigation()
		self.assertTrue(
			any(
				frappe.db.exists("Workspace", w)
				and any(
					r.type == "Link" and r.link_to == PAGE_NAME
					for r in frappe.get_doc("Workspace", w).links
				)
				for w in ("Sales", "Selling")
			)
		)

	def test_uninstall_hooks_run_without_error(self):
		sync_custom_fields()
		sync_page()
		sync_navigation()
		before_uninstall()
		after_uninstall()
		# Restore for other tests / site use.
		after_install()
		self.assertTrue(frappe.db.exists("Page", PAGE_NAME))
		self.assertTrue(frappe.db.exists("Custom Field", f"Warehouse-{WAREHOUSE_EXCLUDE_FIELD}"))
