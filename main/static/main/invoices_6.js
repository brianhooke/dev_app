//Allocated Invoices Modal JS
document.addEventListener('DOMContentLoaded', function() {
    // Handle "Existing Invoices" dropdown selection
    document.getElementById('claimsDropdownInvoices').addEventListener('change', function(e) {
        if (e.target.value === 'allocatedInvoicesValue') {
            $('#allocatedInvoicesModal').modal('show');
        }
    });

    // Handle Delete link clicks in the allocated invoices modal
    document.addEventListener('click', function(event) {
        if (event.target && event.target.classList.contains('delete-invoice') && 
            event.target.closest('#allocatedInvoicesModal')) {
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

    // Handle "View" link click in the allocated invoices modal
    document.querySelectorAll('.view-pdf-invoices').forEach(link => {
        link.addEventListener('click', function(event) {
            console.log("View PDF link clicked")
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
                const pdfViewer = document.getElementById('allocatedInvoicesPdfViewer');
                pdfViewer.src = url;
            })
            .catch(error => {
                console.error('Error fetching PDF:', error);
            });
        });
    });
});

function closeModalInvoices() {
    var modal = document.getElementById('combinedModalInvoices');
    modal.parentNode.removeChild(modal);
    document.getElementById('pdfInputInvoices').value = '';
}

$('#sendInvoicesToXeroButton').click(function() {
    var division = $(this).data('division'); // Get the division from the data attribute. 1 is Developer, 2 is Builder
    console.log("Global division for invoices is:", division);
    // Initialize an empty array to store the invoicePks
    var invoicePks = [];
    // Find all the checked checkboxes
    $('input[type="checkbox"]:checked').each(function() {
        // Get the invoicePk from the id of the checkbox
        var invoicePk = $(this).attr('id').replace('sendToXero', '');
        // Add the invoicePk to the array
        invoicePks.push(invoicePk);
    });
    // Make the AJAX request for each invoicePk
    for (var i = 0; i < invoicePks.length; i++) {
        var invoicePk = invoicePks[i];
        // console.log("Division for invoice is:", division);
        $.ajax({
            url: '/post_invoice/?division=' + division, 
            type: 'POST',
            data: JSON.stringify({invoice_pk: invoicePk, division: division}), // Add the division to the data sent in the AJAX request
            contentType: 'application/json; charset=utf-8',
            dataType: 'json',
            success: function(response) {
                // Handle the response here
                console.log(response);
                // Display the response data in an alert box
                alert(JSON.stringify(response));
                location.reload();
            },
            error: function(error) {
                // Handle error here
                console.log(error);
            }
        });
    }
});

// Helper function to get CSRF token
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            // Does this cookie string begin with the name we want?
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}