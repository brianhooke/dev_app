"""
Core utilities package.
"""

from .project_type import (
    get_project_type,
    get_project,
    set_project_type,
    set_active_project,
    get_template_for_project_type,
    is_project_type,
    get_available_project_types,
)

__all__ = [
    'get_project_type',
    'get_project',
    'set_project_type',
    'set_active_project',
    'get_template_for_project_type',
    'is_project_type',
    'get_available_project_types',
]
