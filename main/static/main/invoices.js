document.getElementById('claimsDropdown').addEventListener('change', function(e) {
    if (e.target.value === 'newClaim') {
        var fileInput = document.getElementById('newClaimPdfInput');
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
                const pdfViewer = document.getElementById('existingInvoicesPdfViewer');
                pdfViewer.src = url;
            })
            .catch(error => {
                console.error('Error fetching PDF:', error);
            });
        });
    });

    // Handle "Process Invoice" link click in the existing invoices modal
    document.querySelectorAll('.process-invoice').forEach(link => {
        link.addEventListener('click', function(event) {
            event.preventDefault();
            const invoiceId = this.getAttribute('data-invoice-id');
            const pdfUrl = this.getAttribute('data-pdf-url');
            const supplierName = this.getAttribute('data-supplier');
            const invoiceNumber = this.getAttribute('data-invoice-number');
            const totalCost = this.getAttribute('data-total');

            document.getElementById('invoiceSupplierName').textContent = supplierName;
            document.getElementById('invoiceNumber').textContent = invoiceNumber;
            document.getElementById('invoiceTotal').textContent = totalCost;
            document.getElementById('selectedInvoiceId').value = invoiceId;

            $('#existingInvoicesModal').modal('hide').on('hidden.bs.modal', function () {
                $('#selectOrderTypeModal').modal('show');
            });
        });
    });

    document.getElementById('selectOrderTypeButton').addEventListener('click', function() {
        const invoiceId = document.getElementById('selectedInvoiceId').value;
        const orderType = document.getElementById('orderTypeSelect').value;
        const pdfUrl = document.querySelector(`[data-invoice-id="${invoiceId}"]`).getAttribute('data-pdf-url');
        const supplier = document.getElementById('invoiceSupplierName').textContent;
        const totalCost = parseFloat(document.getElementById('invoiceTotal').textContent);
        const invoiceNumber = document.getElementById('invoiceNumber').textContent;

        if (orderType === 'directCosts') {
            directCostAllocation(pdfUrl, invoiceId, supplier, totalCost, [], false, invoiceNumber);
        }

        $('#selectOrderTypeModal').modal('hide');
    });
});

// Function to display the Direct Cost Allocation Modal
function directCostAllocation(pdfFilename, invoiceId = "", supplier = "", totalCost = 0.00, allocations = [], updating = false, invoiceNumber = "") {
    // Set the PDF URL in the iframe
    document.getElementById('directCostInvoicesPdfViewer').src = pdfFilename;

    // Set the supplier, total cost, and invoice number
    document.getElementById('directCostSupplier').textContent = supplier;
    document.getElementById('directCostTotal').textContent = totalCost.toFixed(2);
    document.getElementById('directCostInvoiceNumber').textContent = invoiceNumber;
    document.getElementById('hiddenInvoiceId').value = invoiceId;

    // Clear existing line items
    var tableBody = document.getElementById('lineItemsTableInvoices').getElementsByTagName('tbody')[0];
    while (tableBody.rows.length > 1) { // Keep the 'Still to Allocate' row
        tableBody.deleteRow(0);
    }

    // Add event listener to the 'add row' button
    document.getElementById('addInvoicesRowButton').addEventListener('click', function() {
        addInvoiceLineItem();
        updateStillToAllocateValue();
    });

    // For each allocation, add a row to the table
    allocations.forEach(function(allocation) {
        addInvoiceLineItem(allocation.item_name, allocation.amount, allocation.notes);
    });

    // Add event listener to the 'total cost' input field
    var totalCostInput = document.getElementById('directCostTotal');
    totalCostInput.addEventListener('input', updateStillToAllocateValue);

    // Set up 'close' button event listener
    document.getElementById('closeBtn').addEventListener('click', function() {
        $('#directInvoicesCostModal').modal('hide');
    });

    // Set up 'commit' button event listener
    document.getElementById('commitBtn').addEventListener('click', function() {
        var data = gatherData();
        if (!data) return;
        data.pdf = document.getElementById('directCostInvoicesPdfViewer').src;
        fetch('/commit_data/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
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
    document.getElementById('updateBtn').addEventListener('click', function() {
        var data = gatherData();
        if (!data) return;
        fetch('/update_quote/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify(data)
        }).then(function(response) {
            if (response.ok) {
                alert('Costs updated successfully');
                location.reload();
            } else {
                alert('An error occurred.');
            }
        });
    });

    // Show the modal
    $('#directInvoicesCostModal').modal('show');
}

function gatherData() {
    var totalCost = parseFloat(document.getElementById('directCostTotal').textContent);
    totalCost = isNaN(totalCost) ? 0 : totalCost;
    var allocated = 0;
    var contactPk = document.getElementById('hiddenInvoiceId').value;
    var invoiceNumber = document.getElementById('directCostInvoiceNumber').textContent;
    var tableBody = document.getElementById('lineItemsTableInvoices').tBodies[0];
    for (var i = 0; i < tableBody.rows.length - 1; i++) {
        var cellValue = parseFloat(tableBody.rows[i].cells[4].firstChild.value.replace(/,/g, ''));
        cellValue = isNaN(cellValue) ? 0 : cellValue;
        allocated += cellValue;
    }
    allocated = parseFloat(allocated.toFixed(2));
    if (totalCost !== allocated) {
        alert('Total Cost does not equal Total Allocated ' + totalCost.toString() + ' vs ' + allocated.toString());
        return null;
    }
    if (contactPk === '') {
        alert('Need to input Supplier Name');
        return null;
    }
    if (invoiceNumber === '') {
        alert('Invoice # field must have a value');
        return null;
    }
    // Populate the lineItemsTable with the current allocations
    var allocations = Array.from(lineItemsTableInvoices.rows).slice(1, -1).map(function(row) {
        var selectElement = row.cells[0].querySelector('select');
        if (selectElement) {
            var selectedOption = selectElement.options[selectedOption.selectedIndex];
            var costingId = selectedOption.getAttribute('data-costing-id');
            var amountInput = row.cells[4].querySelector('input');
            var amount = amountInput ? amountInput.value : '';
            var uncommittedInput = row.cells[2].querySelector('input');
            var uncommitted = uncommittedInput ? uncommittedInput.value : '';
            var notesInput = row.cells[6].querySelector('input');
            var notes = notesInput ? notesInput.value : '';
            return {
                item: costingId,
                amount: amount,
                uncommitted: uncommitted,
                notes: notes
            };
        } else {
            return null;
        }
    }).filter(function(item) {
        return item !== null;
    });
    var data = {
        quote_id: invoiceId,
        total_cost: totalCost,
        contact_pk: contactPk,
        supplier_quote_number: invoiceNumber,
        allocations: allocations
    };
    console.log("data being sent to server is: " + JSON.stringify(data));
    return data;
}

function addInvoiceLineItem(item, amount, notes = '') {
    console.log("Item is", item);
    console.log("Amounts is", amount);
    console.log("notes are", notes);
    var tableBody = document.getElementById('lineItemsTable').tBodies[0];
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
    for (var i = 1; i < 6; i++) { // Adjusted the loop to run one less iteration
        var newCell = newRow.insertCell(i);
        if (i === 1 || i === 3) { // Shifted the input boxes one cell to the left
            var input = document.createElement('input');
            input.type = 'number';
            input.step = '0.01';
            input.style.width = '100%';
            newCell.appendChild(input);
            input.addEventListener('input', updateStillToAllocateValue);
        } else if (i === 5) { // Shifted the notes input box one cell to the left
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
    var deleteCell = newRow.insertCell(6); // Shifted the delete button one cell to the left
    deleteCell.className = 'delete-cell';
    var deleteButton = document.createElement('button');
    deleteButton.textContent = 'x';
    deleteButton.addEventListener('click', function() {
        newRow.remove();
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
            newRow.cells[0].innerHTML = formattedUncommitted; // Adjusted cell references
            newRow.cells[1].children[0].value = parseFloat(selectedItem.uncommitted).toFixed(2); // Adjusted cell references
            var sum = parseFloat(newRow.cells[0].innerHTML.replace(/,/g, '')) + parseFloat(newRow.cells[2].innerHTML.replace(/,/g, '')); // Adjusted cell references
            newRow.cells[4].innerHTML = (isNaN(sum) ? '0' : sum.toFixed(2)).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ","); // Adjusted cell references
            updateStillToAllocateValue();
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
        newRow.cells[5].children[0].value = notes; // Adjusted cell references
    }
    select.addEventListener('change', function() {
        var selectedItem = itemsData.find(function(item) {
            return item.item === this.value;
        }.bind(this));
        if (selectedItem) {
            var formattedUncommitted = parseFloat(selectedItem.uncommitted).toFixed(2).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
            newRow.cells[0].innerHTML = formattedUncommitted; // Adjusted cell references
            newRow.cells[1].children[0].value = parseFloat(selectedItem.uncommitted).toFixed(2); // Adjusted cell references
            var sum = parseFloat(newRow.cells[0].innerHTML.replace(/,/g, '')) + parseFloat(newRow.cells[2].innerHTML.replace(/,/g, '')); // Adjusted cell references
            newRow.cells[4].innerHTML = (isNaN(sum) ? '0' : sum.toFixed(2)).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ","); // Adjusted cell references
            updateStillToAllocateValue();
        }
    });
    var stillToAllocateInvoicesRow = document.getElementById('stillToAllocateInvoicesRow');
    tableBody.insertBefore(newRow, stillToAllocateInvoicesRow);
}