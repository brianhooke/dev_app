from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # Dashboard app - main homepage and contact management (root level)
    path('', include(('dashboard.urls', 'dashboard'), namespace='dashboard')),
    
    # Core app - main application logic (with prefix)
    path('core/', include(('core.urls', 'core'), namespace='core')),
    
    # PROJECT_TYPE apps with namespaces
    path('development/', include(('development.urls', 'development'), namespace='development')),
    path('construction/', include(('construction.urls', 'construction'), namespace='construction')),
    path('precast/', include(('precast.urls', 'precast'), namespace='precast')),
    path('pods/', include(('pods.urls', 'pods'), namespace='pods')),
    path('general/', include(('general.urls', 'general'), namespace='general')),
    
    # Admin
    path('admin/', admin.site.urls),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)