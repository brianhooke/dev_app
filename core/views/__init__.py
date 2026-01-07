"""
Core views package.

This package contains view functions for the core app.
All views are re-exported here for backward compatibility.
"""

# Quote views
from .quotes import (
    commit_data, update_quote, delete_quote, get_quote_allocations,
    get_quote_allocations_by_quotes,
    get_quote_allocations_for_quote, create_quote_allocation, update_quote_allocation, delete_quote_allocation
)

# Contract Budget views
from .contract_budget import update_uncommitted, get_project_committed_amounts

# HC Variations views
from .hc_variations import (
    hc_variations_view, get_hc_variations, get_hc_variation_allocations,
    save_hc_variation, delete_hc_variation, update_hc_variation_allocation,
    delete_hc_variation_allocation
)

# Bill/Invoice views
from .bills import (
    delete_bill, upload_bill, upload_bill_allocations,
    post_bill, test_xero_bill, get_bills_by_supplier,
    get_bill_allocations
)

# PO views
from .pos import (
    create_po_order, generate_po_pdf, wrap_text,
    send_po_email, generate_po_pdf_bytes, send_po_email_view, view_po_by_unique_id, view_po_pdf_by_unique_id, submit_po_claim, approve_po_claim, upload_bill_pdf, get_po_table_data_for_invoice,
    get_quotes_by_supplier
)

# Claims views - now imported from construction app for backward compatibility
from construction.views.claims import (
    associate_sc_claims_with_hc_claim, update_fixedonsite,
    update_hc_claim_data, get_claim_table, send_hc_claim_to_xero,
    delete_variation, create_variation, post_progress_claim_data,
    post_direct_cost_data
)

# Document views
from .documents import (
    create_plan,
    upload_design_pdf, get_design_pdf_url, upload_report_pdf,
    get_report_pdf_url, alphanumeric_sort_key
)

# Project type views
from .project_type import (
    switch_project_type, switch_project, get_current_project_info,
    project_selector_view
)

# Other utility views (still in main.py for now)
from .main import (
    create_contacts, send_test_email, send_test_email_view,
    upload_categories, upload_costings, update_contract_budget_amounts,
    upload_letterhead, update_contacts, upload_margin_category_and_lines
)

# Bill views (consolidated from main.py into bills.py)
from .bills import (
    bills_view, get_project_bills, update_allocated_bill,
    get_unallocated_bill_allocations, create_unallocated_invoice_allocation,
    update_unallocated_invoice_allocation, delete_unallocated_invoice_allocation,
    allocate_bill, unallocate_bill, approve_bill, get_allocated_bills
)

# Database management views
from .database_wipe import wipe_database

# Contact views
from .contacts import (
    verify_contact_details, pull_xero_contacts, get_contacts_by_instance,
    create_contact, update_contact_details, update_contact_status
)

# Dashboard views (moved from dashboard app)
from .dashboard import (
    error_response, success_response, dashboard_view,
    send_bill, get_project_categories, get_project_items,
    create_category, create_item, reorder_category, reorder_item,
    download_items_csv_template, upload_items_csv,
    generate_po_html, get_po_status, preview_po,
    send_po_email as dashboard_send_po_email, download_po_pdf,
    get_units, add_unit, reorder_unit, delete_unit,
    get_recent_activities, get_action_items
)

# Rates views
from .rates import get_rates_data, create_new_category_costing_unit_quantity, update_category_costing_order_in_list, update_item_unit, update_item_operator, update_item_operator_value, update_category_name, update_item_name

# DEPRECATED: get_xero_token, get_xero_contacts - use OAuth2 in xero_oauth.py instead
