document.addEventListener('DOMContentLoaded', function() {
    document.getElementById('claimsDropdownInvoices').addEventListener('change', function(e) {
        if (e.target.value === 'newClaim') {
            var fileInput = document.getElementById('newClaimPdfInputInvoices');
            fileInput.onchange = function() {
                var file = fileInput.files[0];
                if (file) {
                    var fileURL = URL.createObjectURL(file);
                    var pdfViewer = document.getElementById('pdfViewerInvoices');
                    pdfViewer.src = fileURL;
                    $('#createInvoiceSelectModal').modal('show');
                }
            };
            fileInput.click();  // Trigger the file selection dialog
        }
    });

    document.getElementById('saveInvoiceButton').addEventListener('click', gatherInvoiceData);
    
    

    // Handle "Existing Invoices" dropdown selection
    document.getElementById('claimsDropdownInvoices').addEventListener('change', function(e) {
        if (e.target.value === 'existingClaims') {
            $('#existingInvoicesModal').modal('show');
        }
    });

    // Handle "Existing Invoices" dropdown selection
    document.getElementById('claimsDropdownInvoices').addEventListener('change', function(e) {
        if (e.target.value === 'allocatedInvoicesValue') {
            $('#allocatedInvoicesModal').modal('show');
        }
    });

    // Handle "View" link click in the existing invoices modal
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
                const pdfViewer = document.getElementById('existingInvoicesPdfViewer');
                pdfViewer.src = url;
            })
            .catch(error => {
                console.error('Error fetching PDF:', error);
            });
        });
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

    // document.getElementById('invoiceTotalInput').addEventListener('input', function() {
    //     var invoiceTotal = parseFloat(this.value);
    //     if (!isNaN(invoiceTotal)) {
    //         var invoiceGST = (invoiceTotal / 10).toFixed(2);
    //         document.getElementById('invoiceTotalGSTInput').value = invoiceGST;
    //     }
    // });

    var invoiceTotalInput = document.getElementById('invoiceTotalInput');
    var invoiceTotalGSTInput = document.getElementById('invoiceTotalGSTInput');
    var invoiceTotalGrossInput = document.getElementById('invoiceTotalGrossInput');

    function updateInvoiceTotalGross() {
        var invoiceTotal = parseFloat(invoiceTotalInput.value) || 0;
        var invoiceGST = parseFloat(invoiceTotalGSTInput.value) || 0;
        var invoiceTotalGross = (invoiceTotal + invoiceGST).toFixed(2);
        invoiceTotalGrossInput.textContent = invoiceTotalGross;
    }

    invoiceTotalInput.addEventListener('input', function() {
        var invoiceTotal = parseFloat(this.value);
        if (!isNaN(invoiceTotal)) {
            var invoiceGST = (invoiceTotal / 10).toFixed(2);
            invoiceTotalGSTInput.value = invoiceGST;
        }
        updateInvoiceTotalGross();
    });
    invoiceTotalGSTInput.addEventListener('input', updateInvoiceTotalGross);


    // Handle "Process Invoice" link click in the existing invoices modal
    document.querySelectorAll('.process-invoice-invoices').forEach(link => {
        link.addEventListener('click', function(event) {
            event.preventDefault();
            // const invoiceId = this.getAttribute('data-invoice-id');

            console.log(this);
            const invoiceId = this.getAttribute('data-invoice-id');
            console.log(this.getAttribute('data-invoice-id'));
            const pdfUrl = this.getAttribute('data-pdf-url');
            const supplierName = this.getAttribute('data-supplier');
            const invoiceNumber = this.getAttribute('data-invoice-number');
            const totalCost = this.getAttribute('data-total');
            const totalGst = this.getAttribute('data-gst');
            console.log("Invoice GST is", totalGst);

            document.getElementById('invoiceSupplierName').textContent = supplierName;
            document.getElementById('invoiceNumber').textContent = invoiceNumber;
            document.getElementById('invoiceTotal').textContent = parseFloat(totalCost).toLocaleString();
            document.getElementById('invoiceGSTTotal').textContent = parseFloat(totalGst).toLocaleString();
            document.getElementById('selectedInvoiceId').value = invoiceId;

            $('#existingInvoicesModal').modal('hide').on('hidden.bs.modal', function () {
                $('#selectOrderTypeModal').modal('show');
            });
        });
    });

    document.getElementById('selectInvoiceTypeButton').addEventListener('click', function() {
        console.log("Select Invoice Type button clicked");
        const invoiceId = document.getElementById('selectedInvoiceId').value;
        console.log("Invoice ID is", invoiceId);
        const orderType = document.getElementById('orderTypeSelect').value;
        console.log("Order type is", orderType);
        const pdfUrl = document.querySelector(`[data-invoice-id="${invoiceId}"]`).getAttribute('data-pdf-url');
        console.log("PDF URL is", pdfUrl);
        const supplier = document.getElementById('invoiceSupplierName').textContent;
        console.log("Supplier is", supplier);
        const totalCost = parseFloat(document.getElementById('invoiceTotal').textContent.replace(/,/g, ''));
        console.log("Total cost is", totalCost);
        const totalGst = parseFloat(document.getElementById('invoiceGSTTotal').textContent.replace(/,/g, ''));
        console.log("GST is", totalGst);
        const invoiceNumber = document.getElementById('invoiceNumber').textContent;
        console.log("Invoice number is", invoiceNumber);
        if (orderType === 'directCosts') {
            directCostAllocationInvoices(pdfUrl, invoiceId, supplier, totalCost, totalGst, [], false, invoiceNumber);
        }
        $('#selectOrderTypeModal').modal('hide');
    });
});

// Helper function to get CSRF token
function getCookieInvoices(name) {
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

// Function to display the Direct Cost Allocation Modal
function directCostAllocationInvoices(pdfFilename, invoiceId = "", supplier = "", totalCost = 0.00, totalGst = 0.00, allocations = [], updating = false, invoiceNumber = "") {
    // Ensure all elements exist before modifying them
    const pdfViewer = document.getElementById('directCostInvoicesPdfViewer');
    const supplierElement = document.getElementById('directCostSupplierInvoices');
    const totalElement = document.getElementById('directCostTotalInvoices');
    const totalGSTElement = document.getElementById('gstTotalInvoices');
    const invoiceNumberElement = document.getElementById('directCostInvoiceNumberInvoices');
    const hiddenInvoiceIdElement = document.getElementById('hiddenInvoiceIdInvoices');
    const addRowButton = document.getElementById('addInvoicesRowButton');
    const closeButton = document.getElementById('closeInvoicesBtn');
    // const commitButton = document.getElementById('commitBtnInvoices');
    const saveButton = document.getElementById('saveInvoicesButton');
    const tableBody = document.getElementById('lineItemsTableInvoices').getElementsByTagName('tbody')[0];

    // Log each element to see which one is null
    if (!pdfViewer) {
        console.error('pdfViewer not found');
    }
    if (!supplierElement) {
        console.error('supplierElement not found');
    }
    if (!totalElement) {
        console.error('totalElement not found');
    }
    if (!totalGSTElement) {
        console.error('totalGSTElement not found');
    }
    if (!invoiceNumberElement) {
        console.error('invoiceNumberElement not found');
    }
    if (!hiddenInvoiceIdElement) {
        console.error('hiddenInvoiceIdElement not found');
    }
    if (!addRowButton) {
        console.error('addRowButton not found');
    }
    if (!closeButton) {
        console.error('closeButton not found');
    }
    // if (!commitButton) {
    //     console.error('commitButton not found');
    // }
    if (!saveButton) {
        console.error('saveButton not found');
    }
    if (!tableBody) {
        console.error('tableBody not found');
    }

    // Return if any element is missing
    // if (!pdfViewer || !supplierElement || !totalElement || !invoiceNumberElement || !hiddenInvoiceIdElement || !addRowButton || !closeButton || !commitButton || !updateButton || !tableBody) {
    //     console.error('One or more required elements not found');
    //     return;
    // }
    // Set the PDF URL in the iframe
    pdfViewer.src = pdfFilename;
    // Set the supplier, total cost, and invoice number
    supplierElement.textContent = supplier;
    totalElement.textContent = totalCost.toFixed(2);
    totalGSTElement.textContent = totalGst.toFixed(2);
    invoiceNumberElement.textContent = invoiceNumber;
    hiddenInvoiceIdElement.value = invoiceId;
    // Clear existing line items
    while (tableBody.rows.length > 1) { // Keep the 'Still to Allocate' row
        tableBody.deleteRow(0);
    }
    // Add event listener to the 'add row' button
    addInvoicesRowButton.addEventListener('click', function() {
        addInvoiceLineItem();
        updateStillToAllocateValueInvoices();
    });
    // For each allocation, add a row to the table
    allocations.forEach(function(allocation) {
        addInvoiceLineItem(allocation.item_name, allocation.amount, allocation.notes);
    });
    // Add event listener to the 'total cost' input field
    var totalCostInput = document.getElementById('directCostTotalInvoices');
    totalCostInput.addEventListener('input', updateStillToAllocateValueInvoices);
    // Set up 'close' button event listener
    document.getElementById('closeInvoicesBtn').addEventListener('click', function() {
        $('#directInvoicesCostModal').modal('hide');
    });
    // Set up 'commit' button event listener
    document.getElementById('saveInvoicesButton').addEventListener('click', function() {
        var data = gatherAllocationsDataInvoices();
        if (!data) return;
        data.pdf = document.getElementById('directCostInvoicesPdfViewer').src;
        fetch('/commit_data/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookieInvoices('csrftoken')
            },
            body: JSON.stringify(data)
        }).then(function(response) {
            if (response.ok) {
                alert('Costs uploaded successfully');
                location.reload();
            } else {
                alert('An error occurred.');
            }
        });
    });
    // Set up 'update' button event listener
    // document.getElementById('updateBtnInvoices').addEventListener('click', function() {
    //     var data = gatherAllocationsDataInvoices();
    //     if (!data) return;
    //     fetch('/update_quote/', {
    //         method: 'POST',
    //         headers: {
    //             'Content-Type': 'application/json',
    //             'X-CSRFToken': getCookieInvoices('csrftoken')
    //         },
    //         body: JSON.stringify(data)
    //     }).then(function(response) {
    //         if (response.ok) {
    //             alert('Costs updated successfully');
    //             location.reload();
    //         } else {
    //             alert('An error occurred.');
    //         }
    //     });
    // });
    // Show the modal
    $('#directInvoicesCostModal').modal('show');
}

function addInvoiceLineItem(item, amount, notes = '') {
    console.log("Item is", item);
    console.log("Amounts is", amount);
    console.log("notes are", notes);
    var tableBody = document.getElementById('lineItemsTableInvoices').tBodies[0];
    var newRow = document.createElement('tr');
    var select = document.createElement('select');
    select.style.maxWidth = "100%";
    select.innerHTML = '<option value="">Select an item</option>';
    console.log("costings are: " + costings);
    costings.forEach(function(costing) {
        select.innerHTML += '<option value="' + costing.item + '" data-costing-id="' + costing.costing_pk + '">' + costing.item + '</option>';
    });
    var firstCell = newRow.insertCell(0);
    firstCell.appendChild(select);
    for (var i = 1; i < 7; i++) { // Adjusted the loop to run one less iteration
        var newCell = newRow.insertCell(i);
        if (i === 2 || i === 3 || i === 4) { // Being uncommitted, net and GST amount for this invoice cells
            var input = document.createElement('input');
            input.type = 'number';
            input.step = '0.01';
            input.style.width = '100%';
            newCell.appendChild(input);
            input.addEventListener('input', updateStillToAllocateValueInvoices);
            input.addEventListener('change', updateStillToAllocateValueInvoices);
        } else if (i === 6) { // Notes input
            var input = document.createElement('input');
            input.type = 'text';
            input.style.width = '100%';
            newCell.appendChild(input);
            if (notes) {
                input.value = notes;
            }
        } else {
            newCell.innerHTML = '0';
        }
    }
    var deleteCell = newRow.insertCell(7); // Shifted the delete button one cell to the left
    deleteCell.className = 'delete-cell';
    var deleteButton = document.createElement('button');
    deleteButton.textContent = 'x';
    deleteButton.addEventListener('click', function() {
        newRow.remove();
        updateStillToAllocateValueInvoices(); // Recalculate allocation when a row is deleted
    });
    deleteCell.appendChild(deleteButton);
    select.addEventListener('change', function() {
        console.log('Selected value:', this.value);
        console.log('Items data:', itemsData);
        var selectedItem = itemsData.find(function(item) {
            return item.item === this.value;
        }.bind(this));
        console.log('Selected item:', selectedItem);
        if (selectedItem) {
            var formattedUncommitted = parseFloat(selectedItem.uncommitted).toFixed(2).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
            newRow.cells[1].innerHTML = formattedUncommitted; // Add fixed uncommitted value to the cell
            newRow.cells[2].children[0].value = selectedItem.uncommitted; // Add fixed uncommitted value to the cell
            newRow.cells[3].children[0].value = '0'; // Make Net Amount amount input default to 0.
            newRow.cells[4].children[0].value = '0'; // Make GST Amount amount input default to 0.
            var sum = parseFloat(newRow.cells[2].children[0].value) + parseFloat(newRow.cells[3].children[0].value);
            newRow.cells[5].innerHTML = (isNaN(sum) ? '0' : sum.toFixed(2)).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
            updateStillToAllocateValueInvoices();
        }
    });
    if (item) {
        select.value = item;
        var event = new Event('change');
        select.dispatchEvent(event);
    }
    if (amount) {
        newRow.cells[3].children[0].value = amount; // Adjusted cell references
    }
    if (notes) {
        newRow.cells[6].children[0].value = notes; // Adjusted cell references
    }
    select.addEventListener('change', function() {
        var selectedItem = itemsData.find(function(item) {
            return item.item === this.value;
        }.bind(this));
        if (selectedItem) {
            var formattedUncommitted = parseFloat(selectedItem.uncommitted).toFixed(2).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
            newRow.cells[1].innerHTML = formattedUncommitted; // Adjusted cell references
            var sum = parseFloat(newRow.cells[1].innerHTML.replace(/,/g, '')) + parseFloat(newRow.cells[3].children[0].value);
            newRow.cells[5].innerHTML = (isNaN(sum) ? '0' : sum.toFixed(2)).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
            updateStillToAllocateValueInvoices();
        }
    });
    var stillToAllocateInvoicesRow = document.getElementById('stillToAllocateInvoicesRow');
    tableBody.insertBefore(newRow, stillToAllocateInvoicesRow);
}



function updateStillToAllocateValueInvoices() {
    var totalCost = parseFloat(document.getElementById('directCostTotalInvoices').innerText.replace(/,/g, '')); 
    var totalGst = parseFloat(document.getElementById('gstTotalInvoices').innerText.replace(/,/g, '')); 
    console.log("Total cost for updateAllocate is", totalCost);
    console.log("Total GST for updateAllocate is", totalGst);
    totalCost = isNaN(totalCost) ? 0 : totalCost;
    totalGst = isNaN(totalGst) ? 0 : totalGst;
    var allocated = 0;
    var GstAllocated = 0;
    var tableBody = document.getElementById('lineItemsTableInvoices').tBodies[0];
    for (var i = 0; i < tableBody.rows.length - 1; i++) {
        var cell = tableBody.rows[i].cells[3]; // Set of cells of 'allocated' amount to be counted up towards 'still to allocate total'
        var GstCell = tableBody.rows[i].cells[4]; // Set of GST cells of 'allocated' amount to be counted up towards 'still to allocate total'
        var cellValue = 0;
        var GstCellValue = 0;
        if (cell && cell.firstChild) {
            cellValue = parseFloat(cell.firstChild.value.replace(/,/g, ''));
        }
        if (GstCell && GstCell.firstChild) {
            GstCellValue = parseFloat(GstCell.firstChild.value.replace(/,/g, ''));
        }
        cellValue = isNaN(cellValue) ? 0 : cellValue;
        GstCellValue = isNaN(GstCellValue) ? 0 : GstCellValue;
        allocated += cellValue;
        GstAllocated += GstCellValue;
        // Updating the total if uncommitted, net $, or GST changes
        ['input', 'change'].forEach(function(evt) {
            tableBody.rows[i].cells[2].firstChild.addEventListener(evt, updateRowTotalInvoices);
            tableBody.rows[i].cells[3].firstChild.addEventListener(evt, updateRowTotalInvoices);
            tableBody.rows[i].cells[4].firstChild.addEventListener(evt, updateRowTotalInvoices);
        });
    }
    console.log("Allocated is", allocated);
    console.log("GST Allocated is", GstAllocated);
    var stillToAllocateInv = totalCost - allocated;
    var stillToAllocateGST = totalGst - GstAllocated;
    document.getElementById('stillToAllocateInv').innerHTML = stillToAllocateInv.toFixed(2).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
    document.getElementById('stillToAllocateGST').innerHTML = stillToAllocateGST.toFixed(2).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}


function updateRowTotalInvoices() {
    var row = this.parentNode.parentNode;
    var sum = parseFloat(row.cells[2].children[0].value) + parseFloat(row.cells[3].children[0].value);
    // var sum = parseFloat(row.cells[2].firstChild.value || 0) + parseFloat(row.cells[4].firstChild.value || 0);
    row.cells[5].innerHTML = (isNaN(sum) ? '0' : sum.toFixed(2)).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

function closeModalInvoices() {
    var modal = document.getElementById('combinedModalInvoices');
    modal.parentNode.removeChild(modal);
    document.getElementById('pdfInputInvoices').value = '';
}


function gatherInvoiceData() {
    console.log("Gathering invoice data and allocations...");
    var formData = new FormData(); // Define formData here
    var supplierSelect = document.getElementById('invoiceSupplierSelect');
    if (supplierSelect.value !== 'Select Supplier...') {
        formData.append('supplier', supplierSelect.value);
    } else {
        console.error('No supplier selected.');
        alert('Please select a supplier.');
        return;
    }
    var invoiceNumber = document.getElementById('invoiceNumberInput').value;
    var invoiceTotal = document.getElementById('invoiceTotalInput').value;
    var invoiceTotalGST = document.getElementById('invoiceTotalGSTInput').value; // Get the GST total value
    var fileInput = document.getElementById('newClaimPdfInputInvoices');
    var file = fileInput.files[0];
    var invoiceDate = document.getElementById('invoiceDateInput').value;
    var invoiceDueDate = document.getElementById('invoiceDueDateInput').value;
    console.log("Invoice Date:", invoiceDate);
    console.log("Invoice Due Date:", invoiceDueDate);
    console.log("Supplier:", supplierSelect.value);
    console.log("Invoice Number:", invoiceNumber);
    console.log("Invoice Total:", invoiceTotal);
    console.log("Invoice Total GST:", invoiceTotalGST); // Log the GST total value
    console.log("File:", file);
    formData.append('invoice_number', invoiceNumber);
    formData.append('invoice_total', invoiceTotal);
    formData.append('invoice_total_gst', invoiceTotalGST); // Append the GST total value to formData
    formData.append('pdf', file);
    formData.append('invoice_date', invoiceDate);
    formData.append('invoice_due_date', invoiceDueDate);
    // var tableBody = document.getElementById('lineItemsTableInvoices').tBodies[0];
    // var allocations = [];
    // for (var i = 0; i < tableBody.rows.length - 1; i++) {
    //     var row = tableBody.rows[i];
    //     var itemSelect = row.cells[0].querySelector('select');
    //     var uncommittedInput = row.cells[2].querySelector('input');
    //     var thisInvoiceInput = row.cells[3].querySelector('input');
    //     var notesInput = row.cells[5].querySelector('input');
    //     var allocation = {
    //         item: itemSelect ? itemSelect.value : '',
    //         uncommitted: uncommittedInput ? parseFloat(uncommittedInput.value) : 0,
    //         thisInvoice: thisInvoiceInput ? parseFloat(thisInvoiceInput.value) : 0,
    //         notes: notesInput ? notesInput.value : ''
    //     };
    //     allocations.push(allocation);
    //     console.log("Allocation for row", i, ":", allocation);
    // }
    // formData.append('allocations', JSON.stringify(allocations));
    // console.log("Allocations JSON:", JSON.stringify(allocations));
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

function gatherAllocationsDataInvoices() {
    console.log("Gathering invoice data and allocations...");
    var invoice_pk = document.getElementById('hiddenInvoiceIdInvoices').value;
    console.log("Invoice PK:", invoice_pk);

    var stillToAllocateInv = parseFloat(document.getElementById('stillToAllocateInv').innerText.replace(/,/g, ''));
    var stillToAllocateGST = parseFloat(document.getElementById('stillToAllocateGST').innerText.replace(/,/g, ''));

    // Check if still to allocate values are zero
    if (stillToAllocateInv !== 0) {
        alert('Invoice net total does not equal allocated net amounts');
        return;
    }
    if (stillToAllocateGST !== 0) {
        alert('Invoice gst total does not equal allocated gst amounts');
        return;
    }

    var formData = new FormData();
    formData.append('invoice_pk', invoice_pk);
    var tableBody = document.getElementById('lineItemsTableInvoices').tBodies[0];
    var allocations = [];
    for (var i = 0; i < tableBody.rows.length - 1; i++) {
        var row = tableBody.rows[i];
        var itemSelect = row.cells[0].querySelector('select');
        var uncommittedInput = row.cells[2].querySelector('input');
        var thisInvoiceInput = row.cells[3].querySelector('input');
        var gstInput = row.cells[4].querySelector('input'); // Get the GST input field
        var notesInput = row.cells[5].querySelector('input');
        var allocation = {
            item: itemSelect ? itemSelect.options[itemSelect.selectedIndex].getAttribute('data-costing-id') : '',
            uncommitted: uncommittedInput ? parseFloat(uncommittedInput.value) : 0,
            thisInvoice: thisInvoiceInput ? parseFloat(thisInvoiceInput.value) : 0,
            gst_amount: gstInput ? parseFloat(gstInput.value) : 0, // Include gst_amount in the allocation
            notes: notesInput ? notesInput.value : ''
        };
        allocations.push(allocation);
        console.log("Allocation for row", i, ":", allocation);
    }
    formData.append('allocations', JSON.stringify(allocations));
    console.log("Allocations JSON:", JSON.stringify(allocations));
    fetch('/upload_invoice_allocations/', {
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
              alert('Error uploading invoice.');
          }
      }).catch(error => {
          console.error('Error:', error);
      });
}

$(document).on('click', '.process-invoice-invoices', function(e) {
    e.preventDefault();  // Prevent the default action of the link
    var invoicePk = $(this).data('invoice-id');  // Get the invoice_pk from the data attribute
    postInvoice(invoicePk);  // Call the postInvoice function with the invoice_pk
});

function postInvoice(invoicePk) {
    fetch('/post_invoice/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookieInvoices('csrftoken')
        },
        body: JSON.stringify({ invoice_pk: invoicePk })
    })
    .then(response => response.json())
    .then(data => {
        // Handle the response here
        console.log(data);
    })
    .catch((error) => {
        console.error('Error:', error);
    });
}
