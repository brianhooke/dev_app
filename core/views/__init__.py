"""
Core views package.

This package contains view functions for the core app.
All views are re-exported here for backward compatibility.
"""

# Dashboard views
from .main import main, homepage_view, build_view

# Quote views
from .quotes import (
    commit_data, update_quote, delete_quote, get_quote_allocations,
    update_uncommitted, get_quotes_by_supplier
)

# Bill/Invoice views
from .bills import (
    delete_invoice, upload_invoice, upload_invoice_allocations,
    post_invoice, test_xero_invoice, get_invoices_by_supplier,
    get_invoice_allocations
)

# PO views
from .pos import (
    create_po_order, generate_po_pdf, view_po_pdf, wrap_text,
    send_po_email, generate_po_pdf_bytes, send_po_email_view
)

# Claims views
from .claims import (
    associate_sc_claims_with_hc_claim, update_fixedonsite,
    update_hc_claim_data, get_claim_table, send_hc_claim_to_xero,
    delete_variation, create_variation, post_progress_claim_data,
    post_direct_cost_data
)

# Document views
from .documents import (
    drawings, drawings_view, model_viewer_view, create_plan,
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
    upload_letterhead, update_contacts, xeroapi, make_api_request,
    get_xero_token, get_xero_contacts, mark_sent_to_boutique,
    test_contact_id, upload_margin_category_and_lines
)
