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
                        console.error('Error deleting invoice:', data.message);
                        alert('Error deleting invoice: ' + data.message);
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    alert('An error occurred while deleting the invoice.');
                });
            }
        }
    });

    // Handle Update link clicks in the allocated invoices modal
    document.addEventListener('click', async function(event) {
        if (event.target && event.target.classList.contains('update-invoice') && 
            event.target.closest('#allocatedInvoicesModal')) {
            event.preventDefault();
            
            const invoiceId = event.target.getAttribute('data-invoice-id');
            const invoiceType = event.target.getAttribute('data-invoice-type');
            const pdfUrl = event.target.getAttribute('data-pdf-url');
            const supplier = event.target.getAttribute('data-supplier');
            const totalNet = event.target.getAttribute('data-total-net');
            const totalGst = event.target.getAttribute('data-total-gst');
            const invoiceNumber = event.target.getAttribute('data-invoice-number');
            const invoiceDate = event.target.getAttribute('data-invoice-date');
            const invoiceDueDate = event.target.getAttribute('data-invoice-due-date');
            
            console.log('Update clicked for invoice ID:', invoiceId);
            console.log('Invoice type:', invoiceType, '(1 = Direct Cost, 2 = Progress Claim)');
            
            // Stage 2a: Implement Direct Cost invoice update functionality (for invoiceType 1)
            if (invoiceType === '1') { // Direct Cost Invoice
                try {
                    // Close the allocated invoices modal
                    $('#allocatedInvoicesModal').modal('hide');
                    
                    // Show loading indicator or message
                    console.log('Fetching allocation data for invoice ID:', invoiceId);
                    
                    // Fetch existing allocations from backend
                    const response = await fetch(`/get_invoice_allocations/${invoiceId}/`);
                    
                    if (!response.ok) {
                        throw new Error(`Error fetching allocations: ${response.statusText}`);
                    }
                    
                    const data = await response.json();
                    console.log('Fetched allocation data:', data);
                    
                    // Format allocations for the Direct Cost modal
                    const formattedAllocations = data.allocations.map(alloc => ({
                        item_name: alloc.item,
                        item_pk: alloc.item_pk,
                        net: alloc.amount,
                        gst: alloc.gst_amount,
                        notes: alloc.notes || ''
                    }));
                    
                    console.log('Formatted allocations for Direct Cost modal:', formattedAllocations);
                    
                    // Open the Direct Cost modal with the data
                    directCostAllocationInvoices(
                        pdfUrl,
                        invoiceId,
                        supplier,
                        totalNet,
                        totalGst,
                        formattedAllocations,
                        true, // updating = true
                        invoiceNumber,
                        invoiceDate,
                        invoiceDueDate,
                        parseFloat(totalNet) + parseFloat(totalGst) // gross amount
                    );
                    
                } catch (error) {
                    console.error('Error updating Direct Cost invoice:', error);
                    alert('Error fetching invoice allocation data: ' + error.message);
                }
            } 
            // Stage 2b: Implement Progress Claim invoice update functionality
            else if (invoiceType === '2') {
                try {
                    // Close the allocated invoices modal
                    $('#allocatedInvoicesModal').modal('hide');
                    
                    // Show loading indicator or message
                    console.log('Fetching allocation data for Progress Claim invoice ID:', invoiceId);
                    
                    const url = `/get_invoice_allocations/${invoiceId}/`;
                    console.log(`Fetching allocations from: ${url}`);
                    console.log('Update link clicked with details:', {
                        invoiceId,
                        invoiceType,
                        supplier,
                        totalNet,
                        totalGst,
                        invoiceNumber,
                        invoiceDate,
                        invoiceDueDate,
                        pdfUrl,
                        'data-contact-pk': event.target.getAttribute('data-contact-pk')
                    });
                    
                    // Check if the Progress Claim modal exists
                    if (!document.getElementById('progressClaimModal')) {
                        console.error('Progress Claim modal not found in the DOM');
                        alert('Progress Claim modal not found in the DOM');
                        return;
                    }
                    
                    // Add a hidden input to track that we're updating if it doesn't exist
                    if (!document.getElementById('hiddenUpdatingProgressClaim')) {
                        const hiddenInput = document.createElement('input');
                        hiddenInput.type = 'hidden';
                        hiddenInput.id = 'hiddenUpdatingProgressClaim';
                        hiddenInput.value = 'true';
                        document.getElementById('progressClaimModal').querySelector('.modal-content').appendChild(hiddenInput);
                        console.log('Created hiddenUpdatingProgressClaim input');
                    }
                    
                    // Check if all HTML elements exist
                    console.log('Modal elements check after ensuring hidden input:', {
                        'progressClaimModal': !!document.getElementById('progressClaimModal'),
                        'hiddenUpdatingProgressClaim': !!document.getElementById('hiddenUpdatingProgressClaim'),
                        'modal-title': !!document.querySelector('#progressClaimModal .modal-title'),
                        'saveButton': !!document.getElementById('saveProgressClaimButton')
                    });
                    
                    // This will be the URL to fetch the existing allocations for this invoice
                    const fetchUrl = `/get_invoice_allocations/${invoiceId}/`;
                    console.log('Fetching existing allocations from URL:', fetchUrl);
                    
                    // Fetch the existing allocations
                    fetch(fetchUrl)
                    .then(response => {
                        console.log('Response status:', response.status);
                        return response.json();
                    })
                    .then(data => {
                        console.log('API response received:', data);
                        
                        // The response has an 'allocations' property containing the array
                        const allocationsArray = data.allocations || [];
                        const contactPkFromApi = data.contact_pk || event.target.getAttribute('data-contact-pk'); // Use API's contact_pk if available, otherwise use from the DOM
                        const otherInvoicesArray = data.other_invoices || [];
                        
                        console.log('Allocations array:', allocationsArray);
                        console.log('Contact PK from API:', contactPkFromApi);
                        console.log('Contact PK from DOM:', event.target.getAttribute('data-contact-pk'));
                        console.log('Other invoices:', otherInvoicesArray);
                        
                        // Create the properly formatted data structure for progressClaimModalData
                        // This matches what the function expects based on memory 5d3bb973-e0b3-445c-8e25-01857e28fdc9
                        window.progress_claim_invoice_allocations = [{
                            contact_pk: contactPkFromApi,
                            invoices: otherInvoicesArray
                        }];
                        
                        if (!allocationsArray || allocationsArray.length === 0) {
                            console.error('No allocations found for this invoice!');
                            alert('No existing allocations found for this invoice. Please try again.');
                            return;
                        }
                        
                        // Convert the allocations to the format expected by the modal
                        const formattedAllocations = allocationsArray.map(alloc => {
                            console.log('Processing allocation:', alloc);
                            return {
                                item_pk: alloc.item_pk, // Changed from costing_item_id to match the API response
                                item_name: alloc.item, // Changed from costing_item_name to match the API response
                                net: alloc.amount, // Changed from net_amount to match the API response
                                gst: alloc.gst_amount,
                                allocation_type: alloc.allocation_type
                            };
                        });
                        
                        console.log('Formatted allocations for Progress Claim modal:', formattedAllocations);
                        
                        // Set the hidden input to indicate we're updating
                        const hiddenUpdatingElement = document.getElementById('hiddenUpdatingProgressClaim') || createHiddenUpdatingInput();
                        hiddenUpdatingElement.value = 'true';
                        
                        // Update modal title and button text
                        const updateModalTitle = document.querySelector('#progressClaimModal .modal-title');
                        const updateSaveButton = document.getElementById('saveProgressClaimInvoicesButton');
                        
                        if (updateModalTitle) {
                            updateModalTitle.textContent = 'Update Progress Claim Allocations';
                            console.log('Updated modal title');
                        } else {
                            console.error('Modal title element not found');
                        }
                        
                        if (updateSaveButton) {
                            updateSaveButton.textContent = 'Update Allocations';
                            console.log('Updated save button text');
                        } else {
                            console.error('Save button element not found');
                        }
                        
                        // Open the modal with the existing allocations
                        progressClaimModalData(
                            pdfUrl,
                            invoiceId,
                            supplier,
                            totalNet,
                            totalGst,
                            formattedAllocations,
                            true, // updating = true
                            invoiceNumber,
                            invoiceDate,
                            invoiceDueDate,
                            parseFloat(totalNet) + parseFloat(totalGst), // gross amount
                            contactPkFromApi // Use the contact_pk from the API response
                        );
                        
                        // Log that the modal should be showing
                        console.log('Progress Claim modal should now be displayed with allocation data');
                        
                        const saveButton = document.querySelector('#saveProgressClaimInvoicesButton');
                        if (saveButton) {
                            saveButton.textContent = "Update Allocation";
                            console.log('Updated save button text to: Update Allocation');
                        } else {
                            console.error('Save button element not found!');
                        }
                    })
                    .catch(error => {
                        console.error('Error fetching allocations:', error);
                        alert('Error loading existing allocations. Please try again.');
                    });
                } catch (error) {
                    console.error('Error in Progress Claim update handler:', error);
                    alert('Error preparing Progress Claim update: ' + error.message);
                }
            }
        }
    });

    // Handle "View" link click in the allocated invoices modal
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
                const pdfViewer = document.getElementById('allocatedInvoicesPdfViewer');
                pdfViewer.src = url;
            })
            .catch(error => {
                console.error('Error fetching PDF:', error);
            });
        });
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