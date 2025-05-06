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
});