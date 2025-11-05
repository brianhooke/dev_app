"""
Utility functions for PROJECT_TYPE resolution and management.

Provides helper functions for views and templates to work with PROJECT_TYPE.
"""

from django.shortcuts import get_object_or_404
from ..models import Projects


def get_project_type(request):
    """
    Get the active project_type from the request.
    
    Args:
        request: Django request object
        
    Returns:
        str: Project type ('general', 'development', 'construction', 'precast', 'pods')
    """
    return getattr(request, 'project_type', 'general')


def get_project(request):
    """
    Get the active project from the request.
    
    Args:
        request: Django request object
        
    Returns:
        Projects: Active project instance or None
    """
    return getattr(request, 'project', None)


def set_project_type(request, project_type):
    """
    Set the active project_type in the session.
    
    Args:
        request: Django request object
        project_type: Project type to set
    """
    if project_type in dict(Projects.PROJECT_TYPE_CHOICES):
        request.session['project_type'] = project_type


def set_active_project(request, project_pk):
    """
    Set the active project in the session.
    
    Args:
        request: Django request object
        project_pk: Primary key of the project to activate
    """
    project = get_object_or_404(Projects, projects_pk=project_pk)
    request.session['project_pk'] = project_pk
    request.session['project_type'] = project.project_type


def get_template_for_project_type(base_template, request, fallback_to_core=True):
    """
    Get the appropriate template path based on project_type.
    
    Tries to use PROJECT_TYPE-specific template first, falls back to core template.
    
    Args:
        base_template: Base template name (e.g., 'homepage.html')
        request: Django request object
        fallback_to_core: If True, fallback to core template if PROJECT_TYPE template doesn't exist
        
    Returns:
        str: Template path to use
        
    Example:
        >>> get_template_for_project_type('homepage.html', request)
        'development/homepage.html'  # if project_type is 'development'
        'core/homepage.html'  # if development/homepage.html doesn't exist
    """
    project_type = get_project_type(request)
    
    # Try PROJECT_TYPE-specific template first
    project_template = f'{project_type}/{base_template}'
    
    if fallback_to_core:
        # For now, always fallback to core
        # In production, you'd check if the template exists
        return f'core/{base_template}'
    
    return project_template


def is_project_type(request, project_type):
    """
    Check if the current project_type matches the given type.
    
    Args:
        request: Django request object
        project_type: Project type to check
        
    Returns:
        bool: True if current project_type matches
    """
    return get_project_type(request) == project_type


def get_available_project_types():
    """
    Get list of available project types.
    
    Returns:
        list: List of (value, label) tuples for project types
    """
    return Projects.PROJECT_TYPE_CHOICES
