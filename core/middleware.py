"""
Middleware for PROJECT_TYPE resolution.

Determines the active PROJECT_TYPE for each request and attaches it to the request object.
"""

from .models import Projects, ProjectTypes


class ProjectTypeMiddleware:
    """
    Middleware to determine and attach project_type to each request.
    
    Resolution strategy:
    1. Check session for stored project_type
    2. Check if there's a single project in database, use its type
    3. Default to 'general' if no project exists
    
    Attaches:
    - request.project_type: The active project type string
    - request.project: The active Projects model instance (if exists)
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Resolve project_type for this request
        project_type = self.resolve_project_type(request)
        
        # Attach to request
        request.project_type = project_type
        
        # Also attach the project instance if available
        request.project = self.get_active_project(request)
        
        response = self.get_response(request)
        return response
    
    def resolve_project_type(self, request):
        """
        Resolve the active project_type for this request.
        
        Args:
            request: Django request object
            
        Returns:
            str: Project type ('general', 'development', 'construction', 'precast', 'pods')
        """
        # Strategy 1: Check session
        if 'project_type' in request.session:
            return request.session['project_type']
        
        # Strategy 2: Check if there's a single project, use its type
        project = self.get_active_project(request)
        if project:
            return project.project_type
        
        # Strategy 3: Default to 'general'
        return 'general'
    
    def get_active_project(self, request):
        """
        Get the active project for this request.
        
        Args:
            request: Django request object
            
        Returns:
            Projects: Active project instance or None
        """
        # Check session for stored project_pk
        if 'project_pk' in request.session:
            try:
                return Projects.objects.get(projects_pk=request.session['project_pk'])
            except Projects.DoesNotExist:
                pass
        
        # If only one project exists, use it
        projects = Projects.objects.all()
        if projects.count() == 1:
            return projects.first()
        
        return None


class ProjectTypeContextProcessor:
    """
    Context processor to make project_type available in all templates.
    
    This is a callable class that can be used as a context processor.
    """
    
    def __call__(self, request):
        """
        Add project_type and project to template context.
        
        Args:
            request: Django request object
            
        Returns:
            dict: Context variables for templates
        """
        return {
            'project_type': getattr(request, 'project_type', 'general'),
            'project': getattr(request, 'project', None),
        }


# Function-based context processor (alternative to class-based)
def project_type_context(request):
    """
    Context processor to make project_type available in templates.
    
    Usage in settings.py:
        TEMPLATES = [{
            'OPTIONS': {
                'context_processors': [
                    'core.middleware.project_type_context',
                ],
            },
        }]
    
    Args:
        request: Django request object
        
    Returns:
        dict: Context variables for templates
    """
    return {
        'project_type': getattr(request, 'project_type', 'general'),
        'project': getattr(request, 'project', None),
        'PROJECT_TYPE_CHOICES': ProjectTypes.PROJECT_TYPE_CHOICES,
    }
