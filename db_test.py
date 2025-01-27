#!/usr/bin/env python3
import os
import django

# Point to your Django settings
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dev_app.settings.local")

# Initialize Django
django.setup()

from main.models import Quotes, Quote_allocations, Invoices, Invoice_allocations


def build_data_structures():
    """
    Builds two lists based on your specification.
    """

    # 1) progress_claim_quote_allocations
    #    For each unique contact_pk in Quotes, collect all quote allocations.
    progress_claim_quote_allocations = []
    
    # Distinct contact_pks from the Quotes table
    distinct_contacts_quotes = Quotes.objects.values_list("contact_pk", flat=True).distinct()
    
    for contact_id in distinct_contacts_quotes:
        # Gather all quotes for this contact
        quotes_for_contact = Quotes.objects.filter(contact_pk=contact_id)
        
        # We'll store the data for this contact in a dictionary
        contact_entry = {
            "contact_pk": contact_id,
            "quotes": []
        }
        
        for q in quotes_for_contact:
            # Get all allocations for this quote
            q_allocs = Quote_allocations.objects.filter(quotes_pk=q)
            
            # Convert each allocation to a small dict
            allocations_list = []
            for qa in q_allocs:
                allocations_list.append({
                    "item": qa.item.pk,           # or qa.item.some_field
                    "amount": str(qa.amount)
                })
            
            # Build the quote dict
            # (Per your instructions, "quote_number" = the quote's PK)
            quote_dict = {
                "quote_number": q.quotes_pk,
                "allocations": allocations_list
            }
            contact_entry["quotes"].append(quote_dict)
        
        progress_claim_quote_allocations.append(contact_entry)
    
    # 2) progress_claim_invoice_allocations
    #    For each unique contact_pk in Invoices (where invoice_status != 0),
    #    collect invoice allocations. Sort the invoices by invoice_date ascending.
    progress_claim_invoice_allocations = []
    
    # Distinct contact_pks from Invoices where invoice_status != 0
    distinct_contacts_invoices = (
        Invoices.objects
        .exclude(invoice_status=0)
        .values_list("contact_pk", flat=True)
        .distinct()
    )
    
    for contact_id in distinct_contacts_invoices:
        # Gather all relevant invoices for this contact
        invoices_for_contact = (
            Invoices.objects
            .filter(contact_pk=contact_id)
            .exclude(invoice_status=0)
            .order_by("invoice_date")
        )
        
        contact_entry = {
            "contact_pk": contact_id,
            "invoices": []
        }
        
        for inv in invoices_for_contact:
            # Get invoice allocations
            i_allocs = Invoice_allocations.objects.filter(invoice_pk=inv)
            
            # Build item list, determining the invoice_allocation_type
            allocation_list = []
            for ia in i_allocs:
                if inv.invoice_type == 2 and ia.allocation_type == 0:
                    allocation_type_str = "progress_claim"
                else:
                    allocation_type_str = "direct_cost"
                
                allocation_list.append({
                    "item": ia.item.pk,
                    "amount": str(ia.amount),
                    "invoice_allocation_type": allocation_type_str
                })
            
            invoice_dict = {
                "invoice_number": inv.invoice_pk,
                "allocations": allocation_list
            }
            contact_entry["invoices"].append(invoice_dict)
        
        progress_claim_invoice_allocations.append(contact_entry)
    
    return progress_claim_quote_allocations, progress_claim_invoice_allocations


def main():
    # Build the data structures
    pc_quote_allocs, pc_invoice_allocs = build_data_structures()
    
    # Print them out (for demonstration). You could also manipulate them further or convert them to JSON, etc.
    print("Progress Claim Quote Allocations:\n")
    for entry in pc_quote_allocs:
        print(entry)
    
    print("\nProgress Claim Invoice Allocations:\n")
    for entry in pc_invoice_allocs:
        print(entry)


if __name__ == "__main__":
    main()
