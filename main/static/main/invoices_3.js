// Select Invoice Type Modal JS (Progress Claim or Direct Cost)
document.addEventListener('DOMContentLoaded', function() {
    // Get all required invoice info & pass to either directCostAllocationInvoices or progressClaimModalData
    document.getElementById('selectInvoiceTypeButton').addEventListener('click', function() {
        const invoiceId = document.getElementById('selectedInvoiceId').value;
        const orderType = document.getElementById('orderTypeSelect').value;
        const invoiceLink = document.querySelector(`[data-invoice-id="${invoiceId}"]`);
        // Pull values from DOM
        const pdfUrl = invoiceLink.getAttribute('data-pdf-url');
        const supplier = document.getElementById('invoiceSupplierName').textContent;
        const totalNet = parseFloat(document.getElementById('invoiceNetAmount').textContent.replace(/,/g, ''));
        const totalGst = parseFloat(document.getElementById('invoiceGSTTotal').textContent.replace(/,/g, ''));
        const invoiceNumber = document.getElementById('invoiceNumber').textContent;
        const invoiceDate = document.getElementById('invoiceDate').textContent;
        const invoiceDueDate = document.getElementById('invoiceDueDate').textContent;
        const grossAmount = totalNet + totalGst;
        const contactPk = invoiceLink.getAttribute('data-contact-pk');

        if (orderType === 'directCosts') {
            directCostAllocationInvoices(
                pdfUrl,
                invoiceId,
                supplier,
                totalNet,
                totalGst,
                [],
                false,
                invoiceNumber,
                invoiceDate,
                invoiceDueDate,
                grossAmount,
                // contactPk // <-- Pass contactPk here
            );
        } else if (orderType === 'progressClaim') {
            progressClaimModalData(
                pdfUrl,
                invoiceId,
                supplier,
                totalNet,
                totalGst,
                [],
                false,
                invoiceNumber,
                invoiceDate,
                invoiceDueDate,
                grossAmount,
                contactPk
            );
        }
        $('#selectInvoiceTypeModal').modal('hide');
    });
});
