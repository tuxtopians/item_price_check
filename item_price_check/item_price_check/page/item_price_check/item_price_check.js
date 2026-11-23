// Copyright (c) 2026, Biztek and Contributors
// License: MIT

frappe.pages["item-price-check"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Item Price Check"),
		single_column: true,
	});
	frappe.item_price_check_page = new ItemPriceCheckPage(page);
};

class ItemPriceCheckPage {
	constructor(page) {
		this.page = page;
		this.data = null;
		this.loading = false;
		this.request_id = 0;
		this.make_filters();
		this.make_actions();
		this.$root = $('<div class="ipc-page mt-3"></div>').appendTo(page.main);
		this.render_empty();
	}

	make_filters() {
		this.item = this.page.add_field({
			label: __("Item"),
			fieldtype: "Link",
			fieldname: "item",
			options: "Item",
			reqd: 1,
			get_query: () => ({
				filters: { disabled: 0, has_variants: 0 },
			}),
			change: () => {
				const value = this.item.get_value();
				if (value) {
					this.load_item(value);
				} else {
					this.data = null;
					this.render_empty();
				}
			},
		});

		this.include_zero = this.page.add_field({
			label: __("Include Zero Stock"),
			fieldtype: "Check",
			fieldname: "include_zero_stock",
			default: 0,
			change: () => {
				if (this.item.get_value()) {
					this.load_item(this.item.get_value());
				}
			},
		});
	}

	make_actions() {
		this.page.set_primary_action(__("Refresh"), () => {
			const value = this.item.get_value();
			if (!value) {
				frappe.msgprint(__("Select an Item"));
				return;
			}
			this.load_item(value);
		}, "refresh");
	}

	render_empty() {
		this.$root.html(
			`<div class="ipc-empty">${__(
				"Search by Item Code, Item Name, or Barcode. Stock, free-to-sell, and the last five sales prices will load automatically."
			)}</div>`
		);
	}

	load_item(item_code) {
		const request_id = ++this.request_id;
		this.loading = true;
		frappe.call({
			method: "item_price_check.api.get_item_price_check_data",
			args: {
				item_code,
				include_zero_stock: this.include_zero.get_value() ? 1 : 0,
				limit: 5,
			},
			freeze: true,
			freeze_message: __("Loading item price check..."),
			callback: (r) => {
				if (request_id !== this.request_id) {
					return;
				}
				this.loading = false;
				this.data = r.message || null;
				if (!this.data) {
					this.$root.html(`<div class="ipc-error">${__("No data returned.")}</div>`);
					return;
				}
				if (this.data.item && this.data.item.item_code && this.item.get_value() !== this.data.item.item_code) {
					this.item.set_value(this.data.item.item_code);
				}
				this.render();
			},
			error: () => {
				if (request_id !== this.request_id) {
					return;
				}
				this.loading = false;
				this.$root.html(
					`<div class="ipc-error">${__("Could not load Item Price Check data. Check permissions and try again.")}</div>`
				);
			},
		});
	}

	render() {
		const data = this.data;
		const item = data.item || {};
		const totals = data.sellable_totals || {};
		const summary = data.price_summary || {};

		this.$root.html(`
			${this.render_item_meta(item)}
			${this.render_summary_cards(totals)}
			<div class="ipc-section-title">${__("Warehouse Stock")}</div>
			${this.render_warehouse_table(data.warehouses || [])}
			<div class="ipc-section-title">${__("Sales Price Summary")}${
				summary.currency ? ` <span class="ipc-muted">(${frappe.utils.escape_html(summary.currency)})</span>` : ""
			}</div>
			${this.render_price_summary(summary)}
			<div class="ipc-section-title">${__("Last 5 Sales")}</div>
			${this.render_sales_table(data.sales_history || [])}
		`);

		this.bind_warehouse_clicks();
	}

	render_item_meta(item) {
		return `
			<div class="ipc-item-meta">
				<div>
					<div class="ipc-meta-label">${__("Item Code")}</div>
					<div class="ipc-meta-value">${frappe.utils.escape_html(item.item_code || "")}</div>
				</div>
				<div>
					<div class="ipc-meta-label">${__("Item Name")}</div>
					<div class="ipc-meta-value">${frappe.utils.escape_html(item.item_name || "")}</div>
				</div>
				<div>
					<div class="ipc-meta-label">${__("Item Group")}</div>
					<div class="ipc-meta-value">${frappe.utils.escape_html(item.item_group || "")}</div>
				</div>
				<div>
					<div class="ipc-meta-label">${__("Stock UOM")} / ${__("Barcode")}</div>
					<div class="ipc-meta-value">${frappe.utils.escape_html(item.stock_uom || "")}${
						item.barcode ? ` · ${frappe.utils.escape_html(item.barcode)}` : ""
					}</div>
				</div>
			</div>
		`;
	}

	render_summary_cards(totals) {
		return `
			<div class="ipc-cards">
				${this.card(__("Actual Stock"), this.fmt_qty(totals.actual_qty))}
				${this.card(__("Reserved Stock"), this.fmt_qty(totals.reserved_qty))}
				${this.card(__("Free To Sell"), this.fmt_qty(totals.free_to_sell), "ipc-card-fts")}
				${this.card(__("Warehouses Available"), cint(totals.warehouses_available))}
			</div>
		`;
	}

	card(label, value, extra_class = "") {
		return `
			<div class="ipc-card ${extra_class}">
				<div class="ipc-card-label">${label}</div>
				<div class="ipc-card-value">${value}</div>
			</div>
		`;
	}

	render_warehouse_table(rows) {
		if (!rows.length) {
			return `<div class="ipc-empty">${__("No warehouse stock found for this item.")}</div>`;
		}

		const body = rows
			.map((row) => {
				const fts = flt(row.free_to_sell);
				let row_class = "ipc-clickable";
				if (!row.sellable) {
					row_class += " ipc-row-excluded";
				} else if (fts < 0) {
					row_class += " ipc-row-danger";
				} else if (fts === 0) {
					row_class += " ipc-row-warn";
				}
				return `
					<tr class="${row_class}" data-warehouse="${frappe.utils.escape_html(row.warehouse)}">
						<td>${frappe.utils.escape_html(row.warehouse)}</td>
						<td class="ipc-num">${this.fmt_qty(row.actual_qty)}</td>
						<td class="ipc-num">${this.fmt_qty(row.reserved_qty)}</td>
						<td class="ipc-num">${this.fmt_qty(row.free_to_sell)}</td>
						<td>${this.status_badge(row.stock_status)}</td>
					</tr>
				`;
			})
			.join("");

		return `
			<div class="ipc-table-wrap">
				<table class="ipc-table">
					<thead>
						<tr>
							<th>${__("Warehouse")}</th>
							<th class="ipc-num">${__("Actual Qty")}</th>
							<th class="ipc-num">${__("Reserved Qty")}</th>
							<th class="ipc-num">${__("Free To Sell")}</th>
							<th>${__("Stock Status")}</th>
						</tr>
					</thead>
					<tbody>${body}</tbody>
				</table>
			</div>
		`;
	}

	render_price_summary(summary) {
		if (!summary || summary.last_selling_price == null) {
			return `<div class="ipc-empty">${__("No submitted sales history for price summary.")}</div>`;
		}
		const currency = summary.currency || "";
		return `
			<div class="ipc-price-grid">
				${this.card(__("Last Selling Price"), this.fmt_money(summary.last_selling_price, currency))}
				${this.card(__("Average Selling Price"), this.fmt_money(summary.average_selling_price, currency))}
				${this.card(__("Highest Selling Price"), this.fmt_money(summary.highest_selling_price, currency))}
				${this.card(__("Lowest Selling Price"), this.fmt_money(summary.lowest_selling_price, currency))}
			</div>
		`;
	}

	render_sales_table(rows) {
		if (!rows.length) {
			return `<div class="ipc-empty">${__("No submitted sales invoices found for this item.")}</div>`;
		}

		const body = rows
			.map((row) => {
				const return_badge = row.is_return
					? `<span class="ipc-badge ipc-badge-return">${__("Return")}</span>`
					: "";
				return `
					<tr class="ipc-clickable" data-sales-invoice="${frappe.utils.escape_html(row.sales_invoice)}">
						<td>
							<a href="/app/sales-invoice/${encodeURIComponent(row.sales_invoice)}">
								${frappe.utils.escape_html(frappe.datetime.str_to_user(row.posting_date))}
							</a>
							${return_badge}
						</td>
						<td class="ipc-num">${this.fmt_qty(row.qty)}</td>
						<td class="ipc-num">${this.fmt_money(row.rate, row.currency)}</td>
						<td>${frappe.utils.escape_html(row.currency || "")}</td>
						<td>${frappe.utils.escape_html(row.customer_name || row.customer || "")}</td>
					</tr>
				`;
			})
			.join("");

		return `
			<div class="ipc-table-wrap">
				<table class="ipc-table">
					<thead>
						<tr>
							<th>${__("Posting Date")}</th>
							<th class="ipc-num">${__("Quantity")}</th>
							<th class="ipc-num">${__("Rate")}</th>
							<th>${__("Currency")}</th>
							<th>${__("Customer")}</th>
						</tr>
					</thead>
					<tbody>${body}</tbody>
				</table>
			</div>
		`;
	}

	bind_warehouse_clicks() {
		this.$root.find("tr[data-warehouse]").on("click", (e) => {
			const warehouse = $(e.currentTarget).attr("data-warehouse");
			if (warehouse) {
				frappe.set_route("Form", "Warehouse", warehouse);
			}
		});
		this.$root.find("tr[data-sales-invoice]").on("click", (e) => {
			if ($(e.target).closest("a").length) {
				return;
			}
			const name = $(e.currentTarget).attr("data-sales-invoice");
			if (name) {
				frappe.set_route("Form", "Sales Invoice", name);
			}
		});
	}

	status_badge(status) {
		const map = {
			Available: "ipc-badge-available",
			Unavailable: "ipc-badge-unavailable",
			Negative: "ipc-badge-negative",
			Excluded: "ipc-badge-excluded",
		};
		const cls = map[status] || "";
		return `<span class="ipc-badge ${cls}">${__(status || "")}</span>`;
	}

	fmt_qty(value) {
		return format_number(flt(value), null, 3);
	}

	fmt_money(value, currency) {
		if (value == null || value === "") {
			return "—";
		}
		return format_currency(flt(value), currency || null);
	}
}
