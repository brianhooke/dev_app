"""
View helpers: response envelopes and auth decorators.

The audit (see BEST_PRACTICE_AUDIT.md, P-3 / P-10) found ~150 `JsonResponse`
call sites all rolling their own success/error envelope and ~183 views
using `@csrf_exempt` to avoid having to think about auth. This module
centralises both.

Usage:

    from .views._helpers import api_login_required, api_public, json_ok, json_err

    @api_login_required
    def update_thing(request):
        ...
        return json_ok({'thing_pk': thing.pk})

    @api_public  # explicit allowlist for genuinely public endpoints
    def webhook(request):
        ...
        return json_err('bad signature', status=403)

The two decorators MUST be applied to every JSON view eventually. Until
the sweep is finished they coexist with raw `@csrf_exempt`; use `@api_*`
on new code and migrate views opportunistically.
"""
from functools import wraps

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt


# ---------------------------------------------------------------------------
# Response envelopes
# ---------------------------------------------------------------------------

def json_ok(payload=None, **extra):
    """Return ``{"status": "success", **payload, **extra}``."""
    body = {'status': 'success'}
    if payload:
        body.update(payload)
    if extra:
        body.update(extra)
    return JsonResponse(body)


def json_err(message, *, status=400, code=None, **extra):
    """Return ``{"status": "error", "message": ..., "code": ...}``."""
    body = {'status': 'error', 'message': message}
    if code is not None:
        body['code'] = code
    if extra:
        body.update(extra)
    return JsonResponse(body, status=status)


# ---------------------------------------------------------------------------
# Auth decorators
# ---------------------------------------------------------------------------

def api_login_required(view_func):
    """Require an authenticated user; reply with JSON 401 on failure.

    Use this on every JSON endpoint that mutates or returns user data.
    Replaces the bare ``@csrf_exempt`` pattern (which left endpoints both
    unauthenticated and CSRF-bypassed).
    """
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not getattr(request, 'user', None) or not request.user.is_authenticated:
            return json_err('Authentication required', status=401, code='not_authenticated')
        return view_func(request, *args, **kwargs)
    return _wrapped


def api_public(view_func):
    """Marks a view as intentionally public (e.g. supplier PO flow, healthcheck).

    Equivalent to ``@csrf_exempt`` but documents the intent in code review:
    ``@api_public`` calls out that the lack of auth is deliberate. Use it
    sparingly and pair with rate limiting / signed tokens / a checklist.
    """
    return csrf_exempt(view_func)
