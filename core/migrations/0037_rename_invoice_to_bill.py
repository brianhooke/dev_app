from django.db import migrations


class Migration(migrations.Migration):
    """
    Rename Invoices model to Bills and Invoice_allocations to Bill_allocations.
    
    Uses raw SQL for SQLite to rename columns, then updates Django's model tracking.
    The db_table meta option keeps the actual table names unchanged.
    """

    dependencies = [
        ('core', '0036_add_performance_indexes'),
    ]

    operations = [
        # Rename columns in core_invoices table using SQLite ALTER TABLE
        migrations.RunSQL(
            sql=[
                'ALTER TABLE core_invoices RENAME COLUMN invoice_pk TO bill_pk;',
                'ALTER TABLE core_invoices RENAME COLUMN invoice_status TO bill_status;',
                'ALTER TABLE core_invoices RENAME COLUMN invoice_xero_id TO bill_xero_id;',
                'ALTER TABLE core_invoices RENAME COLUMN supplier_invoice_number TO supplier_bill_number;',
                'ALTER TABLE core_invoices RENAME COLUMN invoice_date TO bill_date;',
                'ALTER TABLE core_invoices RENAME COLUMN invoice_due_date TO bill_due_date;',
                'ALTER TABLE core_invoices RENAME COLUMN invoice_type TO bill_type;',
            ],
            reverse_sql=[
                'ALTER TABLE core_invoices RENAME COLUMN bill_pk TO invoice_pk;',
                'ALTER TABLE core_invoices RENAME COLUMN bill_status TO invoice_status;',
                'ALTER TABLE core_invoices RENAME COLUMN bill_xero_id TO invoice_xero_id;',
                'ALTER TABLE core_invoices RENAME COLUMN supplier_bill_number TO supplier_invoice_number;',
                'ALTER TABLE core_invoices RENAME COLUMN bill_date TO invoice_date;',
                'ALTER TABLE core_invoices RENAME COLUMN bill_due_date TO invoice_due_date;',
                'ALTER TABLE core_invoices RENAME COLUMN bill_type TO invoice_type;',
            ],
        ),
        # Rename columns in core_invoice_allocations table
        migrations.RunSQL(
            sql=[
                'ALTER TABLE core_invoice_allocations RENAME COLUMN invoice_allocations_pk TO bill_allocation_pk;',
                'ALTER TABLE core_invoice_allocations RENAME COLUMN invoice_pk_id TO bill_id;',
            ],
            reverse_sql=[
                'ALTER TABLE core_invoice_allocations RENAME COLUMN bill_allocation_pk TO invoice_allocations_pk;',
                'ALTER TABLE core_invoice_allocations RENAME COLUMN bill_id TO invoice_pk_id;',
            ],
        ),
        # Update Django's content types table to track the model rename
        migrations.RunSQL(
            sql=[
                "UPDATE django_content_type SET model='bills' WHERE app_label='core' AND model='invoices';",
                "UPDATE django_content_type SET model='bill_allocations' WHERE app_label='core' AND model='invoice_allocations';",
            ],
            reverse_sql=[
                "UPDATE django_content_type SET model='invoices' WHERE app_label='core' AND model='bills';",
                "UPDATE django_content_type SET model='invoice_allocations' WHERE app_label='core' AND model='bill_allocations';",
            ],
        ),
    ]
