document.getElementById('claimsDropdown').addEventListener('change', function(e) {
    if (e.target.value === 'newClaim') {
        var fileInput = document.getElementById('newClaimPdfInput');
        fileInput.onchange = function() {
            var file = fileInput.files[0];
            if (file) {
                var fileURL = URL.createObjectURL(file);
                var pdfViewer = document.getElementById('pdfViewer');
                pdfViewer.src = fileURL;
                $('#createInvoiceSelectModal').modal('show');
            }
        };
        fileInput.click();  // Trigger the file selection dialog
    }
});

document.getElementById('saveInvoiceButton').addEventListener('click', gatherData);

function gatherData() {
    var supplierSelect = document.getElementById('invoiceSupplierSelect');
    var invoiceNumber = document.getElementById('invoiceNumberInput').value;
    var invoiceTotal = document.getElementById('invoiceTotalInput').value;
    var fileInput = document.getElementById('newClaimPdfInput');
    var file = fileInput.files[0];
    
    var formData = new FormData();
    formData.append('supplier', supplierSelect.value);
    formData.append('invoice_number', invoiceNumber);
    formData.append('invoice_total', invoiceTotal);
    formData.append('pdf', file);

    fetch('/upload_invoice/', {
        method: 'POST',
        body: formData,
        headers: {
            'X-CSRFToken': getCookie('csrftoken')
        }
    }).then(response => response.json())
      .then(data => {
          if (data.success) {
              alert('Invoice uploaded successfully.');
              location.reload();
          } else {
              alert('Error uploading invoice.');
          }
      }).catch(error => {
          console.error('Error:', error);
      });
}

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

document.addEventListener('DOMContentLoaded', function() {
    // Handle "Existing Invoices" dropdown selection
    document.getElementById('claimsDropdown').addEventListener('change', function(e) {
        if (e.target.value === 'existingClaims') {
            $('#existingInvoicesModal').modal('show');
        }
    });

    // Handle "View" link click in the existing invoices modal
    document.querySelectorAll('.view-pdf').forEach(link => {
        link.addEventListener('click', function(event) {
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
                const pdfViewer = document.getElementById('existingPdfViewer');
                pdfViewer.src = url;
            })
            .catch(error => {
                console.error('Error fetching PDF:', error);
            });
        });
    });
});


