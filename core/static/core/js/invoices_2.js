/* LEGACY: invoices_2.js
 * ======================
 * This file is marked for migration to AllocationsManager.
 * New implementation: invoices_section.js
 * 
 * DO NOT DELETE until all functionality is verified in the new implementation.
 * See: ALLOCATIONS_MANAGER_MIGRATION.md for migration status.
 * 
 * This file handles: Existing Invoices Modal (modal system in build.html)
 * Note: Modal system is separate from reusable_allocations_section system
 */

document.addEventListener('DOMContentLoaded', function() {
    // Handle "Existing Invoices" dropdown selection
    document.getElementById('claimsDropdownInvoices').addEventListener('change', function(e) {
        if (e.target.value === 'existingClaims') {
            $('#unallocatedInvoicesModal').modal('show');
        }
    });

    // Reset dropdown when modals are closed
    $('#unallocatedInvoicesModal, #selectInvoiceTypeModal, #allocatedInvoicesModal').on('hidden.bs.modal', function() {
        console.log('Modal closed, resetting claimsDropdownInvoices');
        $('#claimsDropdownInvoices').val('Invoices');
    });

    // Handle "View" link click in the existing invoices modal
    document.querySelectorAll('.view-pdf-invoices').forEach(link => {
        link.addEventListener('click', function(event) {
            console.log("View PDF link clicked");
            event.preventDefault();
            const pdfUrl = this.getAttribute('data-url');
            fetch(pdfUrl, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/pdf'
                }
            })
            .then(response => response.blob())
            .then(blob => {
                const url = URL.createObjectURL(blob);
                const pdfViewer = document.getElementById('existingInvoicesPdfViewer');
                pdfViewer.src = url;
            })
            .catch(error => {
                console.error('Error fetching PDF:', error);
            });
        });
    });

    // Handle "Process Invoice" link click in the existing invoices modal
    document.querySelectorAll('.process-invoice-invoices').forEach(link => {
        link.addEventListener('click', function(event) {
            event.preventDefault();
            const invoiceId = this.getAttribute('data-invoice-id');
            const pdfUrl = this.getAttribute('data-pdf-url');
            const supplierName = this.getAttribute('data-supplier');
            const invoiceNumber = this.getAttribute('data-invoice-number');
            const totalNet = this.getAttribute('data-total');
            const totalGst = this.getAttribute('data-gst');
            const grossAmount = parseFloat(totalNet) + parseFloat(totalGst);
            const invoiceDate = this.getAttribute('data-invoice-date');
            const invoiceDueDate = this.getAttribute('data-invoice-due-date');
            const possibleProgressClaim = this.getAttribute('data-possible-progress-claim');
            document.getElementById('invoiceSupplierName').textContent = supplierName;
            document.getElementById('invoiceNumber').textContent = invoiceNumber;
            document.getElementById('invoiceGrossAmount').textContent = grossAmount.toLocaleString();
            document.getElementById('invoiceNetAmount').textContent = parseFloat(totalNet).toLocaleString();
            document.getElementById('invoiceGSTTotal').textContent = parseFloat(totalGst).toLocaleString();
            document.getElementById('invoiceDate').textContent = invoiceDate;
            document.getElementById('invoiceDueDate').textContent = invoiceDueDate;
            document.getElementById('selectedInvoiceId').value = invoiceId;
            const orderTypeSelect = document.getElementById('orderTypeSelect');
            const noQuotesMessage = document.getElementById('noQuotesMessage');
            if (possibleProgressClaim === '1') {
                orderTypeSelect.querySelector('option[value="progressClaim"]').disabled = false;
                noQuotesMessage.style.display = 'none';
            } else {
                orderTypeSelect.querySelector('option[value="progressClaim"]').disabled = true;
                noQuotesMessage.style.display = 'block';
            }
            $('#unallocatedInvoicesModal').modal('hide').on('hidden.bs.modal', function () {
                $('#selectInvoiceTypeModal').modal('show');
            });
        });
    });

    // Handle Delete link clicks in the unallocated invoices modal
    document.addEventListener('click', function(event) {
        if (event.target && event.target.classList.contains('delete-invoice') && 
            event.target.closest('#unallocatedInvoicesModal')) {
            event.preventDefault();
            const invoiceId = event.target.getAttribute('data-invoice-id');
            const confirmed = window.confirm('Are you sure you want to delete this invoice?');
            
            if (confirmed) {
                // Send delete request to the server
                fetch('/delete_invoice/', {
                    method: 'DELETE',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCookie('csrftoken')
                    },
                    body: JSON.stringify({
                        invoice_id: invoiceId
                    })
                })
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'success') {
                        // Remove the row from the table
                        event.target.closest('tr').remove();
                    } else {
                        console.error('Server response:', data);
                        window.alert('Failed to delete invoice: ' + (data.message || 'Unknown error'));
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    window.alert('An error occurred while deleting the invoice');
                });
            }
        }
    });
});

// Helper function to get CSRF token
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}