"""
Dashboard views package.

This package organizes dashboard views into logical modules.
For backward compatibility, all views are re-exported from this __init__.py.

Module Structure (target):
- helpers.py: error_response, success_response
- main.py: dashboard_view
- contacts.py: verify_contact_details, pull_xero_contacts, get_contacts_by_instance,
               create_contact, update_contact_details, update_contact_status
- bills.py: send_bill
- categories.py: get_project_categories, get_project_items, create_category,
                 create_item, reorder_category, reorder_item,
                 download_items_csv_template, upload_items_csv
- pos.py: generate_po_html, get_po_status, preview_po, send_po_email, download_po_pdf
- units.py: get_units, add_unit, reorder_unit, delete_unit
- activities.py: get_recent_activities, get_action_items

MIGRATION NOTE: Views are currently in the legacy _all.py file.
Gradually migrate to submodules as time permits.
"""

# Import everything from the legacy file for backward compatibility
from dashboard.views._all import (
    # Helpers
    error_response,
    success_response,
    
    # Main
    dashboard_view,
    
    # Contacts
    verify_contact_details,
    pull_xero_contacts,
    get_contacts_by_instance,
    create_contact,
    update_contact_details,
    update_contact_status,
    
    # Bills
    send_bill,
    
    # Categories & Items
    get_project_categories,
    get_project_items,
    create_category,
    create_item,
    reorder_category,
    reorder_item,
    download_items_csv_template,
    upload_items_csv,
    
    # PO
    generate_po_html,
    get_po_status,
    preview_po,
    send_po_email,
    download_po_pdf,
    
    # Units
    get_units,
    add_unit,
    reorder_unit,
    delete_unit,
    
    # Activities
    get_recent_activities,
    get_action_items,
)

# Define __all__ for explicit exports
__all__ = [
    'error_response',
    'success_response',
    'dashboard_view',
    'verify_contact_details',
    'pull_xero_contacts',
    'get_contacts_by_instance',
    'create_contact',
    'update_contact_details',
    'update_contact_status',
    'send_bill',
    'get_project_categories',
    'get_project_items',
    'create_category',
    'create_item',
    'reorder_category',
    'reorder_item',
    'download_items_csv_template',
    'upload_items_csv',
    'generate_po_html',
    'get_po_status',
    'preview_po',
    'send_po_email',
    'download_po_pdf',
    'get_units',
    'add_unit',
    'reorder_unit',
    'delete_unit',
    'get_recent_activities',
    'get_action_items',
]
