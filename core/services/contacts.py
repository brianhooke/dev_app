"""
Contacts service module.

Contains business logic for contact operations that is PROJECT_TYPE-agnostic
and reusable across all project types.

Models used: Contacts
"""

from ..models import Contacts


def get_checked_contacts(division):
    """
    Get checked contacts for a division.
    
    Args:
        division: Division ID
        
    Returns:
        list: List of contact dictionaries (checked=True)
    """
    contacts = Contacts.objects.filter(
        division=division,
        checked=True
    ).order_by('contact_name').values()
    return list(contacts)


def get_all_contacts(division):
    """
    Get all contacts for a division (unfiltered).
    
    Args:
        division: Division ID
        
    Returns:
        list: List of all contact dictionaries
    """
    contacts = Contacts.objects.filter(
        division=division
    ).order_by('contact_name').values()
    return list(contacts)
