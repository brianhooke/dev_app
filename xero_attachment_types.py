"""
MIME types for bill/receipt attachments aligned with Xero Accounting API attachments
and Xero Files inbox behaviour.

References (Xero does not publish one flat enum in OpenAPI; this set is derived from
Xero API examples, Files API validation messages, and Xero product documentation
for common business attachments):

- https://developer.xero.com/documentation/api/accounting/attachments
- https://developer.xero.com/documentation/api/files/types
- Xero OpenAPI examples (e.g. image/jpeg, image/png, image/jpg, application/pdf)

Deploy: include this module in the Lambda deployment artifact next to lambda_function.py
so imports resolve (same layout as this repository).
"""

from __future__ import annotations

import mimetypes
from typing import Optional

# Lowercased MIME main/subtypes Xero accepts for typical invoice/bill/receipt files.
# Includes image/* and office formats seen in Xero UI and API examples.
XERO_ACCOUNTING_ATTACHMENT_MIME_TYPES: frozenset[str] = frozenset(
    {
        "application/pdf",
        # Images (receipts / scans)
        "image/jpeg",
        "image/jpg",  # appears in Xero OpenAPI examples (non-RFC alias)
        "image/pjpeg",
        "image/png",
        "image/gif",
        "image/webp",
        "image/tiff",
        "image/bmp",
        "image/heic",
        "image/heif",
        "image/svg+xml",
        # Microsoft Office
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-powerpoint",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        # OpenDocument (commonly accepted where Office is)
        "application/vnd.oasis.opendocument.text",
        "application/vnd.oasis.opendocument.spreadsheet",
        "application/vnd.oasis.opendocument.presentation",
        # Text / data / archives (Files inbox / Hubdoc-style workflows)
        "text/plain",
        "text/csv",
        "text/html",
        "text/xml",
        "application/xml",
        "application/rtf",
        "text/rtf",
        "application/zip",
        "application/x-zip-compressed",
    }
)


def normalize_email_content_type(content_type: str) -> str:
    """Normalise RFC and Xero quirks to a canonical lowercase type."""
    raw = (content_type or "").strip().lower()
    if not raw:
        return ""
    if raw in ("image/jpg", "application/jpg", "image/pjpeg"):
        return "image/jpeg"
    return raw


def resolve_attachment_content_type(
    declared_content_type: Optional[str], filename: Optional[str]
) -> str:
    """
    Prefer the declared MIME type; if missing or generic, guess from filename.
    """
    ct = normalize_email_content_type(declared_content_type or "")
    if ct and ct != "application/octet-stream":
        return ct
    guessed, _ = mimetypes.guess_type(filename or "")
    return normalize_email_content_type(guessed or "")


def is_allowed_xero_email_attachment_content_type(
    declared_content_type: Optional[str], filename: Optional[str]
) -> bool:
    """True if this part should be ingested as a bill attachment (Lambda filter)."""
    ct = resolve_attachment_content_type(declared_content_type, filename)
    return bool(ct) and ct in XERO_ACCOUNTING_ATTACHMENT_MIME_TYPES


def presigned_get_response_content_type(
    filename: Optional[str], stored_content_type: Optional[str]
) -> Optional[str]:
    """
    Content-Type to pass to S3 presigned get_object for correct browser inline display.

    Returns None to let S3 use the object's stored metadata (fallback).
    """
    ct = resolve_attachment_content_type(stored_content_type, filename)
    if ct in XERO_ACCOUNTING_ATTACHMENT_MIME_TYPES:
        return ct
    return None
