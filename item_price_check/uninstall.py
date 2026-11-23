# Copyright (c) 2026, Biztek and Contributors
# License: MIT

"""Uninstall cleanup for Item Price Check."""

from __future__ import annotations

import frappe

from item_price_check.constants import PAGE_NAME
from item_price_check.install import remove_custom_fields, remove_navigation


def before_uninstall():
	try:
		remove_navigation()
		remove_custom_fields()
		if frappe.db.exists("Page", PAGE_NAME):
			frappe.delete_doc("Page", PAGE_NAME, force=True, ignore_permissions=True)
		frappe.clear_cache()
	except Exception:
		frappe.log_error(title="item_price_check: before_uninstall failed")


def after_uninstall():
	try:
		frappe.clear_cache()
	except Exception:
		frappe.log_error(title="item_price_check: after_uninstall failed")
