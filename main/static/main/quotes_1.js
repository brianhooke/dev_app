var itemsData = JSON.parse(document.getElementById('items-data').textContent);

document.addEventListener('DOMContentLoaded', function() {
    document.getElementById('dropdown').addEventListener('change', function() {
        if (this.value === 'commitCosts') {
            document.getElementById('pdfInput').click();
        }
    });
    document.getElementById('pdfInput').addEventListener('change', function(event) {
        var file = event.target.files[0];
        if (file) {
            var reader = new FileReader();
            reader.onload = function(e) {
                var pdfData = e.target.result;
                displayCombinedModal(pdfData);
            };
            reader.readAsDataURL(file);
        }
    });
});

function updateHiddenInput(selectElement) {
    var selectedOption = selectElement.options[selectElement.selectedIndex];
    document.getElementById('contact_pk').value = selectedOption.value;
}

function displayCombinedModal(pdfFilename, quote_id = "", supplier = "", contact_pk = "", totalCost = 0.00, allocations = [], updating = false, supplier_quote_number = "") {
    var pdfUrl = pdfFilename;

    // Generate options for the supplier dropdown list
    console.log("Contacts list is: " + contacts);
    var selectableContacts = contacts;
    console.log("selectableContacts is: " + selectableContacts);
    var options = selectableContacts.map(function(contact) {
        if (contact.contact_name === supplier) {
            return `<option value="${contact.contact_pk}" selected>${contact.contact_name}</option>`;
        } else {
            return `<option value="${contact.contact_pk}">${contact.contact_name}</option>`;
        }
    }).join('');

    console.log("dropdown options are: " + options);

    var selectHTML = `
    <select id="supplier" onchange="updateHiddenInput(this)">
        ${options}
    </select>
    <input type="hidden" id="contact_pk" name="contact_pk">
    `;

    var combinedModalHTML = `
        <div id="combinedModal" style="display: flex;">
        <div class="pdf-viewer" style="width: 40%;">
            <iframe src="${pdfUrl}" class="pdf-frame"></iframe>
        </div>
        <div class="cost-details" style="width: 60%;">
            <h2>Enter Quotes</h2>
            <div class="input-field">
                <label for="supplier">Supplier:</label>
                ${selectHTML}
            </div>
            <div class="input-field">
                <label for="totalCost">Total Cost:</label>
                <input type="number" id="totalCost" step="0.01" placeholder="0.00" class="total-cost-input" value="${totalCost}">
            </div>
            <div class="input-field">
                <label for="quoteNumber">Quote #:</label>
                <input type="text" id="quoteNumber" maxlength="255" value="${supplier_quote_number}">
            </div>
            <input type="hidden" id="hiddenQuoteId" value="${quote_id}">
            <h3>Line Items</h3>
            <table id="lineItemsTable" style="table-layout: fixed;">
            <thead>
                <tr>
                    <th rowspan="2" style="width: 17%;">Item</th>
                    <th colspan="2" style="width: 21%;">Uncommitted</th>
                    <th colspan="2" style="width: 21%;">Committed</th>
                    <th rowspan="2" style="width: 16%;">Total</th>
                    <th rowspan="2" style="width: 20%;">Notes</th>
                    <th rowspan="2" class="delete-cell-header" style="width: 5%;"></th>
                </tr>
                <tr>
                    <th style="width: 10%;">Old</th>
                    <th style="width: 15%;">New</th>
                    <th style="width: 10%;">Total</th>
                    <th style="width: 15%;">This Quote</th>
                </tr>
            </thead>
            <tbody>
                <!-- Rows will be added here -->
                <tr id="stillToAllocateRow">
                    <td colspan="5">Still to Allocate</td>
                    <td id="stillToAllocateValue">0.00</td>
                    <td id="notes"></td>
                </tr>
            </tbody>
        </table>
        <button id="addRowButton">+</button>
            <button id="closeBtn">Close</button>
            <button id="commitBtn" style="float: right; display: ${updating ? 'none' : 'inline-block'};">Save</button>
            <button id="updateBtn" style="float: right; display: ${updating ? 'inline-block' : 'none'};">Update</button>
            </div>
    </div>
    `;
    // Create a new div and set its innerHTML to the modal HTML
    var modalDiv = document.createElement('div');
    modalDiv.innerHTML = combinedModalHTML;
    document.body.appendChild(modalDiv);
    // Set the default value of the hidden input field
    document.getElementById('contact_pk').value = contact_pk;
    // Add event listener to the 'add row' button
    document.getElementById('addRowButton').addEventListener('click', function() {
        addLineItem();
        updateStillToAllocateValue();
    });
    // For each allocation, add a row to the table
    allocations.forEach(function(allocation) {
        addLineItem(allocation.item_name, allocation.amount, allocation.notes);
    });
    // Set the default value of the 'total cost' input to 0.00
    var totalCostInput = document.getElementById('totalCost');
    // Add event listener to the 'total cost' input field
    totalCostInput.addEventListener('input', updateStillToAllocateValue);
    // Set up 'close' button event listener
    document.getElementById('closeBtn').addEventListener('click', function() {
        var modal = document.getElementById('combinedModal');
        modal.parentNode.removeChild(modal);
        // Reset the file input
        document.getElementById('pdfInput').value = '';
    });

    function gatherData() {
        var totalCost = parseFloat(document.getElementById('totalCost').value);
        totalCost = isNaN(totalCost) ? 0 : totalCost;
        var allocated = 0;
        var contact_pk = document.getElementById('contact_pk').value;
        var supplier_quote_number = document.getElementById('quoteNumber').value;
        var quote_id = document.getElementById('hiddenQuoteId').value;
        var tableBody = document.getElementById('lineItemsTable').tBodies[0];
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
        if (contact_pk === '') {
            alert('Need to input Supplier Name');
            return null;
        }
        if (supplier_quote_number === '') {
            alert('Supplier Quote # field must have a value');
            return null;
        }
        // Populate the lineItemsTable with the current allocations
        var allocations = Array.from(lineItemsTable.rows).slice(1, -1).map(function(row) {
            var selectElement = row.cells[0].querySelector('select');
            if (selectElement) {
                var selectedOption = selectElement.options[selectElement.selectedIndex];
                var costingId = selectedOption.getAttribute('data-costing-id');
                var amountInput = row.cells[4].querySelector('input');
                var amount = amountInput ? amountInput.value : '';
                var uncommittedInput = row.cells[2].querySelector('input');
                var uncommittedSpan = row.cells[2].querySelector('span');
                var uncommitted = uncommittedInput ? uncommittedInput.value : (uncommittedSpan ? uncommittedSpan.textContent : '0.00');
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
            quote_id: quote_id,
            total_cost: totalCost,
            contact_pk: contact_pk,
            supplier_quote_number: supplier_quote_number,
            allocations: allocations
        };
        console.log("data being sent to server is: " + JSON.stringify(data));
        return data;
    }
    
    document.getElementById('commitBtn').addEventListener('click', function() {
        var data = gatherData();
        if (!data) {
            console.log('Validation failed, stopping POST request');
            return false;
        }
        data.pdf = document.querySelector('.pdf-frame').src;
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
    
    document.getElementById('updateBtn').addEventListener('click', function() {
        var data = gatherData();
        console.log(data);
        if (!data) {
            console.log('Validation failed, stopping POST request');
            return false;
        }
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
}

function addLineItem(item, amount, notes = '') {
    console.log("Item is", item);
    console.log("Amounts is", amount);
    console.log("notes are", notes);
    var tableBody = document.getElementById('lineItemsTable').tBodies[0];
    var newRow = document.createElement('tr');
    var select = document.createElement('select');
    select.style.maxWidth = "100%";
    select.innerHTML = '<option value="">Select an item</option>';
    console.log("costings are: " + costings);
    // Filter out items where category's order_in_list is -1
    // Create a map of items to filter out margin items
    const marginItems = new Set(itemsData.filter(item => item.order_in_list === '-1').map(item => item.item));
    
    costings.forEach(function(costing) {
        // Only add items that are not in the marginItems set
        if (!marginItems.has(costing.item)) {
            select.innerHTML += '<option value="' + costing.item + '" data-costing-id="' + costing.costing_pk + '">' + costing.item + '</option>';
        }
    });
    var firstCell = newRow.insertCell(0);
    firstCell.appendChild(select);
    for (var i = 1; i < 7; i++) {
        var newCell = newRow.insertCell(i);
        if (i === 2 || i === 4) {
            var input = document.createElement('input');
            input.type = 'number';
            input.step = '0.01';
            input.style.width = '100%';
            newCell.appendChild(input);
            input.addEventListener('input', updateStillToAllocateValue);
        } else if (i === 6) {
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
    var deleteCell = newRow.insertCell(7);
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
        console.log('Category order_in_list:', selectedItem ? selectedItem.order_in_list : 'not found');
        
        if (selectedItem) {
            var formattedUncommitted = parseFloat(selectedItem.uncommitted).toFixed(2).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
            newRow.cells[1].innerHTML = formattedUncommitted;
            
            // Always use input field since margin items are filtered out
            var uncommittedCell = newRow.cells[2];
            var uncommittedValue = parseFloat(selectedItem.uncommitted).toFixed(2);
            var input = document.createElement('input');
            input.type = 'number';
            input.step = '0.01';
            input.style.width = '100%';
            input.value = uncommittedValue;
            input.addEventListener('input', updateStillToAllocateValue);
            uncommittedCell.innerHTML = '';
            uncommittedCell.appendChild(input);
            
            var sum = parseFloat(newRow.cells[1].innerHTML.replace(/,/g, '')) + parseFloat(newRow.cells[3].innerHTML.replace(/,/g, ''));
            newRow.cells[5].innerHTML = (isNaN(sum) ? '0' : sum.toFixed(2)).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
            updateStillToAllocateValue();
        }
    });
    if (item) {
        select.value = item;
        var event = new Event('change');
        select.dispatchEvent(event);
    }
    if (amount) {
        newRow.cells[4].children[0].value = amount;
    }
    if (notes) {
        newRow.cells[6].children[0].value = notes;
    }
    select.addEventListener('change', function() {
        var selectedItem = itemsData.find(function(item) {
            return item.item === this.value;
        }.bind(this));
        if (selectedItem) {
            var formattedUncommitted = parseFloat(selectedItem.uncommitted).toFixed(2).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
            newRow.cells[1].innerHTML = formattedUncommitted;
            newRow.cells[2].children[0].value = parseFloat(selectedItem.uncommitted).toFixed(2);
            var sum = parseFloat(newRow.cells[1].innerHTML.replace(/,/g, '')) + parseFloat(newRow.cells[3].innerHTML.replace(/,/g, ''));
            newRow.cells[5].innerHTML = (isNaN(sum) ? '0' : sum.toFixed(2)).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
            updateStillToAllocateValue();
        }
    });
    var stillToAllocateRow = document.getElementById('stillToAllocateRow');
    tableBody.insertBefore(newRow, stillToAllocateRow);
}

function updateStillToAllocateValue() {
    var totalCost = parseFloat(document.getElementById('totalCost').value);
    totalCost = isNaN(totalCost) ? 0 : totalCost;
    var allocated = 0;
    var tableBody = document.getElementById('lineItemsTable').tBodies[0];
    
    for (var i = 0; i < tableBody.rows.length - 1; i++) {
        var row = tableBody.rows[i];
        
        // Get committed value (always input)
        var committedElement = row.cells[4].firstChild;
        var cellValue = parseFloat(committedElement.value ? committedElement.value.replace(/,/g, '') : '0');
        cellValue = isNaN(cellValue) ? 0 : cellValue;
        allocated += cellValue;
        
        // Only add event listeners if elements are inputs
        var uncommittedElement = row.cells[2].firstChild;
        if (uncommittedElement.tagName === 'INPUT') {
            ['input', 'change'].forEach(function(evt) {
                uncommittedElement.addEventListener(evt, updateCellFive);
            });
        }
        
        ['input', 'change'].forEach(function(evt) {
            committedElement.addEventListener(evt, updateCellFive);
        });
    }
    
    var stillToAllocateValue = totalCost - allocated;
    document.getElementById('stillToAllocateValue').innerHTML = stillToAllocateValue.toFixed(2).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

function updateCellFive() {
    var row = this.parentNode.parentNode;
    
    // Get uncommitted value (could be input or span)
    var uncommittedElement = row.cells[2].firstChild;
    var uncommittedValue = uncommittedElement.tagName === 'INPUT' ?
        parseFloat(uncommittedElement.value || 0) :
        parseFloat(uncommittedElement.textContent || 0);
    
    // Get committed value (always input)
    var committedValue = parseFloat(row.cells[4].firstChild.value || 0);
    
    var sum = uncommittedValue + committedValue;
    row.cells[5].innerHTML = (isNaN(sum) ? '0' : sum.toFixed(2)).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

function getCookie(name) {
    var cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        var cookies = document.cookie.split(';');
        for (var i = 0; i < cookies.length; i++) {
            var cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

function closeModal() {
    var modal = document.getElementById('combinedModal');
    modal.parentNode.removeChild(modal);
    document.getElementById('pdfInput').value = '';
}

