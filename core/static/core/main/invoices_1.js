//Upload Invoice Modal JS
document.addEventListener('DOMContentLoaded', function() {
    // Event listener for the invoice claims dropdown
    document.getElementById('claimsDropdownInvoices').addEventListener('change', function(e) {
        if (e.target.value === 'newClaim') {
            var fileInput = document.getElementById('newClaimPdfInputInvoices');
            // Define what happens when a file is selected
            fileInput.onchange = function() {
                var file = fileInput.files[0];
                if (file) {
                    var fileURL = URL.createObjectURL(file);
                    var pdfViewer = document.getElementById('pdfViewerInvoices');
                    pdfViewer.src = fileURL;
                    $('#uploadInvoiceModal').modal('show'); // Show modal with jQuery
                }
            };
            // Trigger the file selection dialog
            fileInput.click();
        }
    });


    
    // Event listener for the save invoice button
    document.getElementById('saveInvoiceButton').addEventListener('click', gatherInvoiceData);
    // Setup for real-time calculation and display of invoice totals
    var invoiceNetInput = document.getElementById('invoiceNetInput');
    var invoiceGSTInput = document.getElementById('invoiceGSTInput');
    var invoiceGrossTotalDisplay = document.getElementById('invoiceGrossTotalDisplay');
    // Function to update the gross total whenever net or GST values change
    function updateInvoiceTotalGross() {
        var invoiceTotal = parseFloat(invoiceNetInput.value) || 0;
        var invoiceGST = parseFloat(invoiceGSTInput.value) || 0;
        var invoiceTotalGross = (invoiceTotal + invoiceGST).toFixed(2);
        invoiceGrossTotalDisplay.textContent = invoiceTotalGross;
    }
    // Event listener for net input changes
    invoiceNetInput.addEventListener('input', function() {
        var invoiceTotal = parseFloat(this.value);
        if (!isNaN(invoiceTotal)) {
            var invoiceGST = (invoiceTotal / 10).toFixed(2);
            invoiceGSTInput.value = invoiceGST; // Automatically calculate GST as 10% of net
        }
        updateInvoiceTotalGross();
    });
    // Event listener for GST input changes
    invoiceGSTInput.addEventListener('input', updateInvoiceTotalGross);
});

// Function to gather and upload new invoice data
function gatherInvoiceData() {
    var formData = new FormData();
    var supplierSelect = document.getElementById('invoiceSupplierSelect');
    // Check if a supplier has been selected
    if (supplierSelect.value !== 'Select Supplier...') {
        formData.append('supplier', supplierSelect.value);
    } else {
        console.error('No supplier selected.');
        alert('Please select a supplier.');
        return;
    }
    var invoiceDivision = division; // Note: 'division' should be defined or passed as an argument
    var invoiceNumber = document.getElementById('invoiceNumberInput').value;
    var invoiceTotal = document.getElementById('invoiceNetInput').value;
    var invoiceTotalGST = document.getElementById('invoiceGSTInput').value; // Get the GST total value
    var fileInput = document.getElementById('newClaimPdfInputInvoices');
    var file = fileInput.files[0];
    var invoiceDate = document.getElementById('invoiceDateInput').value;
    var invoiceDueDate = document.getElementById('invoiceDueDateInput').value;
    // Append all necessary data to FormData
    formData.append('invoiceDivision', invoiceDivision);
    formData.append('invoice_number', invoiceNumber);
    formData.append('invoice_total', invoiceTotal);
    formData.append('invoice_total_gst', invoiceTotalGST);
    formData.append('pdf', file);
    formData.append('invoice_date', invoiceDate);
    formData.append('invoice_due_date', invoiceDueDate);
    // Send the form data to the server
    fetch('/upload_invoice/', {
        method: 'POST',
        body: formData,
        headers: {
            'X-CSRFToken': getCookieInvoices('csrftoken')
        }
    }).then(response => response.json())
      .then(data => {
          if (data.success) {
              console.log('Invoice uploaded successfully.');
              alert('Invoice uploaded successfully.');
              location.reload();
          } else {
              console.error('Error uploading invoice:', data.error);
          }
      });
}