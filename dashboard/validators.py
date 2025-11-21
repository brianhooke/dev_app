"""
Validation utilities for dashboard app.

Provides reusable validators for contact details including email, BSB, account numbers, and ABN.
"""

import re
from django.core.exceptions import ValidationError


def validate_email(email):
    """
    Validate email format.
    
    Args:
        email (str): Email address to validate
        
    Returns:
        str: Validated email address
        
    Raises:
        ValidationError: If email format is invalid
    """
    if not email:
        raise ValidationError('Email is required')
    
    email = email.strip()
    email_regex = r'^[^\s@]+@[^\s@]+\.[^\s@]+$'
    if not re.match(email_regex, email):
        raise ValidationError('Invalid email format')
    
    return email


def validate_bsb(bsb):
    """
    Validate BSB is exactly 6 digits.
    
    Args:
        bsb (str): BSB to validate (may contain dashes)
        
    Returns:
        str: Validated BSB without dashes (6 digits)
        
    Raises:
        ValidationError: If BSB is not exactly 6 digits
    """
    if not bsb:
        raise ValidationError('BSB is required')
    
    bsb_digits = bsb.replace('-', '').strip()
    if not bsb_digits.isdigit() or len(bsb_digits) != 6:
        raise ValidationError('BSB must be exactly 6 digits')
    
    return bsb_digits


def validate_account_number(account):
    """
    Validate account number is at least 6 digits.
    
    Args:
        account (str): Account number to validate
        
    Returns:
        str: Validated account number
        
    Raises:
        ValidationError: If account number is invalid
    """
    if not account:
        raise ValidationError('Account Number is required')
    
    account = account.strip()
    if not account.isdigit() or len(account) < 6:
        raise ValidationError('Account Number must be at least 6 digits')
    
    return account


def validate_abn(abn):
    """
    Validate ABN is exactly 11 digits (optional field).
    
    Args:
        abn (str): ABN to validate (may contain spaces)
        
    Returns:
        str: Validated ABN without spaces (11 digits) or empty string if not provided
        
    Raises:
        ValidationError: If ABN is provided but not exactly 11 digits
    """
    if not abn:
        return ''
    
    abn_digits = abn.replace(' ', '').strip()
    if not abn_digits.isdigit() or len(abn_digits) != 11:
        raise ValidationError('ABN must be exactly 11 digits if provided')
    
    return abn_digits


def validate_required_field(value, field_name):
    """
    Validate that a required field is not empty.
    
    Args:
        value (str): Value to validate
        field_name (str): Name of the field for error message
        
    Returns:
        str: Validated value (stripped)
        
    Raises:
        ValidationError: If value is empty
    """
    if not value or not value.strip():
        raise ValidationError(f'{field_name} is required')
    
    return value.strip()
