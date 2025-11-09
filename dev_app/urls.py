from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static

# Base URL patterns (for root domain access)
base_patterns = [
    # Core app - main application logic (no prefix, root level)
    path('', include(('core.urls', 'core'), namespace='core')),
    
    # PROJECT_TYPE apps with namespaces
    path('development/', include(('development.urls', 'development'), namespace='development')),
    path('construction/', include(('construction.urls', 'construction'), namespace='construction')),
    path('precast/', include(('precast.urls', 'precast'), namespace='precast')),
    path('pods/', include(('pods.urls', 'pods'), namespace='pods')),
    path('general/', include(('general.urls', 'general'), namespace='general')),
    
    # Admin
    path('admin/', admin.site.urls),
]

# Main urlpatterns - includes both root and subdirectory access
urlpatterns = [
    # Subdirectory access for mason.build/project_management
    path('project_management/', include(base_patterns)),
    # Root access (for direct EB domain access)
] + base_patterns

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)