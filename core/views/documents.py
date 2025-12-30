"""
Documents-related views.
"""

import csv
from decimal import Decimal, InvalidOperation
from django.template import loader
from ..forms import CSVUploadForm
from django.http import HttpResponse, JsonResponse
from ..models import Categories, Contacts, Quotes, Costing, Quote_allocations, DesignCategories, PlanPdfs, ReportPdfs, ReportCategories, Po_globals, Po_orders, Po_order_detail, SPVData, Letterhead, Bills, Bill_allocations, HC_claims, HC_claim_allocations, Projects, Hc_variation, Hc_variation_allocations
import json
from django.shortcuts import render
from django.forms.models import model_to_dict
from django.db.models import Sum, Case, When, IntegerField, Q, F, Prefetch, Max
from ..services import quotes as quote_service
from ..services import pos as pos_service
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import get_object_or_404
import uuid
from django.core.files.base import ContentFile
import base64
from django.conf import settings
from PyPDF2 import PdfReader, PdfWriter
import os
import logging
from io import BytesIO
from django.core.files.storage import default_storage
from datetime import datetime, date, timedelta
import re
from django.core.mail import send_mail
from django.db import connection
from collections import defaultdict
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from io import BytesIO
from django.core.mail import EmailMessage
from urllib.parse import urljoin
import textwrap
from django.core import serializers
from reportlab.lib import colors
import requests
from decimal import Decimal
from ratelimit import limits, sleep_and_retry
from urllib.request import urlretrieve
from django.shortcuts import render
from django.http import JsonResponse, HttpResponseBadRequest
from django.forms.models import model_to_dict
from django.db.models import Sum
from ..models import Bills, Contacts, Costing, Categories, Quote_allocations, Quotes, Po_globals, Po_orders, SPVData
import json
from django.db.models import Q, Sum
import ssl
import urllib.request
from django.core.exceptions import ValidationError
from ..formulas import Committed
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction

ssl._create_default_https_context = ssl._create_unverified_context

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)  

@csrf_exempt
def create_plan(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        category_name = data.get('plan')
        category_type = data.get('categoryType')
        if category_name:
            if category_type == 1:  
                new_category = DesignCategories(design_category=category_name)
            elif category_type == 2:  
                new_category = ReportCategories(report_category=category_name)
            else:
                return JsonResponse({'status': 'error', 'error': 'Invalid category type'}, status=400)
            new_category.save()
            return JsonResponse({'status': 'success'}, status=201)
        else:
            return JsonResponse({'status': 'error', 'error': 'Invalid data'}, status=400)
    else:
        return JsonResponse({'status': 'error', 'error': 'Invalid method'}, status=405)
from django.core.files.storage import default_storage

@csrf_exempt
def upload_design_pdf(request):
    if request.method == 'POST':
        # LOGGING: Document upload debug
        logger.info(f"=== DOCUMENT UPLOAD DEBUG START ===")
        logger.info(f"DJANGO_SETTINGS_MODULE: {getattr(settings, 'DJANGO_SETTINGS_MODULE', 'NOT SET')}")
        logger.info(f"DEBUG: {getattr(settings, 'DEBUG', 'NOT SET')}")
        logger.info(f"MEDIA_URL: {getattr(settings, 'MEDIA_URL', 'NOT SET')}")
        logger.info(f"DEFAULT_FILE_STORAGE: {getattr(settings, 'DEFAULT_FILE_STORAGE', 'NOT SET')}")
        logger.info(f"Storage backend class: {type(default_storage).__name__}")
        
        logger.info('Received POST request.')
        try:
            pdf_file = request.FILES['pdfFile']
            category_select = request.POST['categorySelect']
            pdf_name_values = json.loads(request.POST['pdfNameValues'])
            rev_num_values = json.loads(request.POST['revNumValues'])  
            logger.info(f'pdf_name_values: {pdf_name_values}')
            logger.info(f'rev_num_values: {rev_num_values}')
        except Exception as e:
            logger.error(f'Error parsing POST data: {e}')
            return JsonResponse({'status': 'error', 'error': 'Error parsing POST data'}, status=400)
        logger.info(f'Type of pdf_name_values: {type(pdf_name_values)}')
        logger.info(f'Type of rev_num_values: {type(rev_num_values)}')
        category = DesignCategories.objects.get(design_category_pk=category_select)
        logger.info(f'Category: {category.design_category}')
        pdf = PdfReader(pdf_file)
        pages = pdf.pages  
        logger.info(f'Number of pages: {len(pages)}')
        for page_number, page in enumerate(pages):
            try:
                pdf_writer = PdfWriter()
                pdf_writer.add_page(page)
            except AssertionError:
                logger.error(f'Error processing page {page_number}. Skipping.')
                continue
            plan_number = pdf_name_values.get(str(page_number + 1), None)
            rev_number = rev_num_values.get(str(page_number + 1), None)
            if not plan_number or not rev_number:
                logger.warning(f'Missing plan_number or rev_number for page {page_number}. Skipping.')
                continue
            output_filename = f'plans/{category.design_category}_{plan_number}_{rev_number}.pdf'
            logger.info(f'Saving page {page_number} as {output_filename}.')
            output_pdf = BytesIO()
            pdf_writer.write(output_pdf)
            output_pdf.seek(0)
            
            # LOGGING: Check storage before save
            logger.info(f"About to save to storage: {type(default_storage).__name__}")
            saved_path = default_storage.save(output_filename, output_pdf)
            logger.info(f"File saved to path: {saved_path}")
            logger.info(f"File exists in storage: {default_storage.exists(saved_path)}")
            
            plan_pdf = PlanPdfs.objects.create(
                file=output_filename,
                design_category=category,
                plan_number=plan_number,
                rev_number=rev_number
            )
            logger.info(f'Successfully created PlanPdfs object for page {page_number}.')
            logger.info(f"PlanPdfs.file field: {plan_pdf.file}")
            logger.info(f"PlanPdfs.file.url: {plan_pdf.file.url}")
            logger.info(f"=== DOCUMENT UPLOAD DEBUG END ===")         
    return JsonResponse({'status': 'success'})
@csrf_exempt
def get_design_pdf_url(request, design_category, plan_number, rev_number=None):
    try:
        if rev_number is None:
            plan_pdf = PlanPdfs.objects.get(design_category=design_category, plan_number=plan_number)
        else:
            plan_pdf = PlanPdfs.objects.get(design_category=design_category, plan_number=plan_number, rev_number=rev_number)
        file_url = plan_pdf.file.url
        if file_url.startswith('/media/media/'):
            file_url = '/media/' + file_url[12:]  
        rev_numbers = PlanPdfs.objects.filter(design_category=design_category, plan_number=plan_number).values_list('rev_number', flat=True)
        return JsonResponse({'file_url': file_url, 'rev_numbers': list(rev_numbers)})
    except PlanPdfs.DoesNotExist:
        return JsonResponse({'error': 'PlanPdfs not found'}, status=404)
@csrf_exempt
def upload_report_pdf(request):
    if request.method == 'POST':
        logger.info('Received POST request.')
        try:
            pdf_file = request.FILES['pdfFile']
            category_select = request.POST['categorySelect']
            pdf_name_value = request.POST['pdfNameValue']
            logger.info(f'pdf_name_value: {pdf_name_value}')
        except Exception as e:
            logger.error(f'Error parsing POST data: {e}')
            return JsonResponse({'status': 'error', 'error': 'Error parsing POST data'}, status=400)
        category = ReportCategories.objects.get(report_category_pk=category_select)
        logger.info(f'Category: {category.report_category}')
        plan_number = pdf_name_value
        if not plan_number:
            logger.warning(f'Missing plan_number. Skipping.')
            return JsonResponse({'status': 'error', 'error': 'Missing plan_number'}, status=400)
        datetime_str = datetime.now().strftime("%Y%m%d%H%M%S")  
        output_filename = f'reports/{category.report_category}_{plan_number}_{datetime_str}.pdf'
        logger.info(f'Saving file as {output_filename}.')
        default_storage.save(output_filename, pdf_file)
        ReportPdfs.objects.create(
            file=output_filename,
            report_category=category,
            report_reference=plan_number
        )
        logger.info(f'Successfully created ReportPdfs object.')         
    return JsonResponse({'status': 'success'})
@csrf_exempt
def get_report_pdf_url(request, report_category, report_reference=None):
    try:
        if report_reference:
            report_pdf = ReportPdfs.objects.get(report_category=report_category, report_reference=report_reference)
            file_url = report_pdf.file.url
            if file_url.startswith('/media/media/'):
                file_url = '/media/' + file_url[12:]  
            return JsonResponse({'file_url': file_url})
        else:
            report_pdfs = ReportPdfs.objects.filter(report_category=report_category)
            response_data = []
            for report_pdf in report_pdfs:
                file_url = report_pdf.file.url
                if file_url.startswith('/media/media/'):
                    file_url = '/media/' + file_url[12:]  
                response_data.append({
                    'file_url': file_url,
                    'report_reference': report_pdf.report_reference
                })
            return JsonResponse({'data': response_data})
    except ReportPdfs.DoesNotExist:
        return JsonResponse({'error': 'ReportPdfs not found'}, status=404)
def alphanumeric_sort_key(s):
    return [int(part) if part.isdigit() else part for part in re.split('([0-9]+)', s)]


# ============================================================================
# PROJECT DOCUMENT MANAGEMENT VIEWS
# ============================================================================

from django.views.decorators.http import require_http_methods
from ..models import Document_folders, Document_files
import mimetypes


@require_http_methods(["GET"])
def get_project_folders(request, project_pk):
    """
    Get all folders and files for a project
    Returns nested folder structure with files
    """
    try:
        # Get all folders for this project
        folders = Document_folders.objects.filter(
            project_id=project_pk
        ).prefetch_related(
            Prefetch(
                'files',
                queryset=Document_files.objects.all().order_by('file_name')
            )
        ).order_by('order_index', 'folder_name')
        
        # Build folder data
        folders_data = []
        for folder in folders:
            files_data = []
            for file in folder.files.all():
                files_data.append({
                    'file_pk': file.file_pk,
                    'file_name': file.file_name,
                    'file_url': file.file.url if file.file else None,
                    'file_type': file.file_type or '',
                    'file_size': file.file_size or 0,
                    'uploaded_at': file.uploaded_at.isoformat() if file.uploaded_at else None,
                    'description': file.description or ''
                })
            
            folders_data.append({
                'folder_pk': folder.folder_pk,
                'folder_name': folder.folder_name,
                'parent_folder_id': folder.parent_folder_id,
                'order_index': folder.order_index,
                'files': files_data
            })
        
        logger.info(f"Retrieved {len(folders_data)} folders for project {project_pk}")
        
        return JsonResponse({
            'status': 'success',
            'folders': folders_data
        })
        
    except Exception as e:
        logger.error(f"Error getting project folders: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Error getting folders: {str(e)}'
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def create_folder(request):
    """
    Create a new folder
    
    Expected POST data:
    {
        "project_pk": int,
        "folder_name": string,
        "parent_folder_id": int (optional)
    }
    """
    try:
        data = json.loads(request.body)
        
        project_pk = data.get('project_pk')
        folder_name = data.get('folder_name', '').strip()
        parent_folder_id = data.get('parent_folder_id')
        
        if not project_pk or not folder_name:
            return JsonResponse({
                'status': 'error',
                'message': 'Project PK and folder name are required'
            }, status=400)
        
        # Get project
        try:
            project = Projects.objects.get(projects_pk=project_pk)
        except Projects.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Project not found'
            }, status=404)
        
        # Get parent folder if specified
        parent_folder = None
        if parent_folder_id:
            try:
                parent_folder = Document_folders.objects.get(folder_pk=parent_folder_id)
            except Document_folders.DoesNotExist:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Parent folder not found'
                }, status=404)
        
        # Create folder
        folder = Document_folders.objects.create(
            project=project,
            folder_name=folder_name,
            parent_folder=parent_folder
        )
        
        logger.info(f"Created folder '{folder_name}' for project {project.project}")
        
        return JsonResponse({
            'status': 'success',
            'folder_pk': folder.folder_pk,
            'folder_name': folder.folder_name
        })
        
    except Exception as e:
        logger.error(f"Error creating folder: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Error creating folder: {str(e)}'
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def rename_folder(request):
    """
    Rename a folder
    
    Expected POST data:
    {
        "folder_pk": int,
        "new_name": string
    }
    """
    try:
        data = json.loads(request.body)
        
        folder_pk = data.get('folder_pk')
        new_name = data.get('new_name', '').strip()
        
        if not folder_pk or not new_name:
            return JsonResponse({
                'status': 'error',
                'message': 'Folder PK and new name are required'
            }, status=400)
        
        # Get folder
        try:
            folder = Document_folders.objects.get(folder_pk=folder_pk)
        except Document_folders.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Folder not found'
            }, status=404)
        
        old_name = folder.folder_name
        folder.folder_name = new_name
        folder.save()
        
        logger.info(f"Renamed folder from '{old_name}' to '{new_name}'")
        
        return JsonResponse({
            'status': 'success',
            'message': 'Folder renamed successfully'
        })
        
    except Exception as e:
        logger.error(f"Error renaming folder: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Error renaming folder: {str(e)}'
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def rename_file(request):
    """
    Rename a file
    
    Expected POST data:
    {
        "file_pk": int,
        "new_name": string
    }
    """
    try:
        data = json.loads(request.body)
        
        file_pk = data.get('file_pk')
        new_name = data.get('new_name', '').strip()
        
        if not file_pk or not new_name:
            return JsonResponse({
                'status': 'error',
                'message': 'File PK and new name are required'
            }, status=400)
        
        # Get file
        try:
            doc_file = Document_files.objects.get(file_pk=file_pk)
        except Document_files.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'File not found'
            }, status=404)
        
        old_name = doc_file.file_name
        doc_file.file_name = new_name
        doc_file.save()
        
        logger.info(f"Renamed file from '{old_name}' to '{new_name}'")
        
        return JsonResponse({
            'status': 'success',
            'message': 'File renamed successfully'
        })
        
    except Exception as e:
        logger.error(f"Error renaming file: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Error renaming file: {str(e)}'
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def delete_folder(request):
    """
    Delete a folder and all its contents
    
    Expected POST data:
    {
        "folder_pk": int
    }
    """
    try:
        data = json.loads(request.body)
        
        folder_pk = data.get('folder_pk')
        
        if not folder_pk:
            return JsonResponse({
                'status': 'error',
                'message': 'Folder PK is required'
            }, status=400)
        
        # Get folder
        try:
            folder = Document_folders.objects.get(folder_pk=folder_pk)
        except Document_folders.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Folder not found'
            }, status=404)
        
        folder_name = folder.folder_name
        
        # Delete folder (CASCADE will delete subfolders and files)
        folder.delete()
        
        logger.info(f"Deleted folder '{folder_name}' and all its contents")
        
        return JsonResponse({
            'status': 'success',
            'message': 'Folder deleted successfully'
        })
        
    except Exception as e:
        logger.error(f"Error deleting folder: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Error deleting folder: {str(e)}'
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def upload_files(request):
    """
    Upload files to a folder
    """
    try:
        folder_pk = request.POST.get('folder_pk')
        files = request.FILES.getlist('files')
        
        if not folder_pk:
            return JsonResponse({
                'status': 'error',
                'message': 'Folder PK is required'
            }, status=400)
        
        if not files:
            return JsonResponse({
                'status': 'error',
                'message': 'No files provided'
            }, status=400)
        
        # Get folder
        try:
            folder = Document_folders.objects.get(folder_pk=folder_pk)
        except Document_folders.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Folder not found'
            }, status=404)
        
        uploaded_files = []
        
        for file in files:
            # Get file extension and type
            file_name = file.name
            file_ext = os.path.splitext(file_name)[1].lower().replace('.', '')
            file_type = file_ext
            
            # Guess MIME type
            mime_type, _ = mimetypes.guess_type(file_name)
            
            # Create document file
            doc_file = Document_files.objects.create(
                folder=folder,
                file_name=file_name,
                file=file,
                file_type=file_type,
                file_size=file.size
            )
            
            uploaded_files.append({
                'file_pk': doc_file.file_pk,
                'file_name': doc_file.file_name
            })
            
            logger.info(f"Uploaded file '{file_name}' to folder '{folder.folder_name}'")
        
        return JsonResponse({
            'status': 'success',
            'message': f'Uploaded {len(uploaded_files)} file(s)',
            'files': uploaded_files
        })
        
    except Exception as e:
        logger.error(f"Error uploading files: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Error uploading files: {str(e)}'
        }, status=500)


@require_http_methods(["GET"])
def download_file(request, file_pk):
    """
    Download a file
    """
    try:
        # Get file
        try:
            doc_file = Document_files.objects.get(file_pk=file_pk)
        except Document_files.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'File not found'
            }, status=404)
        
        # Return file
        if doc_file.file:
            response = HttpResponse(doc_file.file.read(), content_type='application/octet-stream')
            response['Content-Disposition'] = f'attachment; filename="{doc_file.file_name}"'
            return response
        else:
            return JsonResponse({
                'status': 'error',
                'message': 'File content not found'
            }, status=404)
        
    except Exception as e:
        logger.error(f"Error downloading file: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Error downloading file: {str(e)}'
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def delete_file(request):
    """
    Delete a file
    
    Expected POST data:
    {
        "file_pk": int
    }
    """
    try:
        data = json.loads(request.body)
        
        file_pk = data.get('file_pk')
        
        if not file_pk:
            return JsonResponse({
                'status': 'error',
                'message': 'File PK is required'
            }, status=400)
        
        # Get file
        try:
            doc_file = Document_files.objects.get(file_pk=file_pk)
        except Document_files.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'File not found'
            }, status=404)
        
        file_name = doc_file.file_name
        
        # Delete the physical file
        if doc_file.file:
            doc_file.file.delete(save=False)
        
        # Delete the database record
        doc_file.delete()
        
        logger.info(f"Deleted file '{file_name}'")
        
        return JsonResponse({
            'status': 'success',
            'message': 'File deleted successfully'
        })
        
    except Exception as e:
        logger.error(f"Error deleting file: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Error deleting file: {str(e)}'
        }, status=500)