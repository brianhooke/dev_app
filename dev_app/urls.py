from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static
from core.views.pos import view_po_by_unique_id, view_po_pdf_by_unique_id, submit_po_claim, approve_po_claim, upload_invoice_pdf

urlpatterns = [
    # Dashboard app - main homepage and contact management (root level)
    path('', include(('dashboard.urls', 'dashboard'), namespace='dashboard')),
    
    # Public PO view (top-level, shareable URL for suppliers)
    path('po/<str:unique_id>/', view_po_by_unique_id, name='view_po_public'),
    path('po/<str:unique_id>/pdf/', view_po_pdf_by_unique_id, name='view_po_pdf'),
    path('po/<str:unique_id>/submit/', submit_po_claim, name='submit_po_claim'),
    path('po/<str:unique_id>/approve/', approve_po_claim, name='approve_po_claim'),
    path('po/<str:unique_id>/upload-invoice/', upload_invoice_pdf, name='upload_invoice_pdf'),
    
    # Core app - main application logic (with prefix)
    path('core/', include(('core.urls', 'core'), namespace='core')),
    
    # PROJECT_TYPE apps with namespaces
    path('development/', include(('development.urls', 'development'), namespace='development')),
    path('construction/', include(('construction.urls', 'construction'), namespace='construction')),
    path('precast/', include(('precast.urls', 'precast'), namespace='precast')),
    path('pods/', include(('pods.urls', 'pods'), namespace='pods')),
    path('general/', include(('general.urls', 'general'), namespace='general')),
    
    # Authentication URLs (for testing and future use)
    path('accounts/', include('django.contrib.auth.urls')),
    
    # Admin
    path('admin/', admin.site.urls),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)