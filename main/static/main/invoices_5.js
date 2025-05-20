//Direct Cost Invoice Allocation Modal JS

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
function directCostAllocationInvoices(
    pdfFilename,
    invoiceId = "",
    supplier = "",
    totalNet = 0.00,
    totalGst = 0.00,
    allocations = [],
    updating = false,
    invoiceNumber = "",
    invoiceDate = "",
    invoiceDueDate = "",
    grossAmount = ""
  ) {
    const pdfViewer = document.getElementById('directCostInvoicesPdfViewer');
    const supplierElement = document.getElementById('directCostSupplierInvoices');
    const totalElement = document.getElementById('directCostTotalInvoices');
    const gstTotalElement = document.getElementById('directCostGstTotalInvoices');
    const invoiceNumberElement = document.getElementById('directCostInvoiceNumberInvoices');
    const invoiceDateElement = document.getElementById('directCostInvoiceDateInvoices');
    const invoiceDueDateElement = document.getElementById('directCostInvoiceDueDateInvoices');
    const grossAmountElement = document.getElementById('directCostGrossAmountInvoices');
    const hiddenInvoiceIdElement = document.getElementById('hiddenInvoiceIdInvoices');
  
    // The table where we add line items
    const table = document.getElementById('lineItemsTableInvoices');
    if (!table) {
      console.error("Unable to find lineItemsTableInvoices");
      return;
    }
    const tableBody = table.querySelector('tbody');
    if (!tableBody) {
      console.error("lineItemsTableInvoices has no <tbody>");
      return;
    }
  
    // Set PDF viewer
    if (pdfViewer) pdfViewer.src = pdfFilename;
  
    // Set the modal fields
    if (supplierElement) supplierElement.textContent = supplier;
    if (totalElement) {
      totalElement.textContent = parseFloat(totalNet)
        .toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }
    if (gstTotalElement) {
      gstTotalElement.textContent = parseFloat(totalGst)
        .toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }
    if (invoiceNumberElement) invoiceNumberElement.textContent = invoiceNumber;
    if (invoiceDateElement) invoiceDateElement.textContent = invoiceDate;
    if (invoiceDueDateElement) invoiceDueDateElement.textContent = invoiceDueDate;
    if (grossAmountElement) {
      grossAmountElement.textContent = parseFloat(grossAmount)
        .toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }
  
    // Set the hidden invoice ID
    if (hiddenInvoiceIdElement) hiddenInvoiceIdElement.value = invoiceId;
  
    // Clear existing line items (except the "Still to Allocate" row)
    // We assume the last row is "stillToAllocateInvoicesRow".
    // So let's remove all rows up to that final row.
    while (tableBody.rows.length > 1) {
      tableBody.deleteRow(0); // remove from top
    }
  
    // If you want to automatically add rows for existing allocations:
    if (Array.isArray(allocations)) {
      allocations.forEach((allocation) => {
        // allocation could have item_name, amount, notes, etc.
        addInvoiceLineItem(allocation.item_name, allocation.amount, allocation.notes);
      });
    }

    // Hook up the "+" button to add a new line item
    const addRowButton = document.getElementById('addDirectCostRowButton');
    if (addRowButton) {
      addRowButton.addEventListener('click', function() {
        // Insert a blank row
        addInvoiceLineItem();
        // Recalculate
        updateStillToAllocateValueInvoices();
      });
    }

    // Show the modal
    $('#directCostModal').modal('show');
  }

function addInvoiceLineItem(item, amount, notes = '') {
    var tableBody = document.getElementById('lineItemsTableInvoices').tBodies[0];
    var newRow = document.createElement('tr');
    var select = document.createElement('select');
    select.style.maxWidth = "100%";
    select.innerHTML = '<option value="">Select an item</option>';
    console.log("costings are: " + costings);
    // Add all items to the dropdown, including margin items with order_in_list = -1
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
    // Use the correct IDs from your Direct Cost modal
    const totalNetElement = document.getElementById('directCostTotalInvoices');
    const totalGstElement = document.getElementById('directCostGstTotalInvoices');
    if (!totalNetElement || !totalGstElement) {
      console.error("Missing directCostTotalInvoices or directCostGstTotalInvoices element");
      return;
    }
    // Parse the Net and GST totals
    let totalNet = parseFloat(totalNetElement.textContent.replace(/,/g, ''));
    let totalGst = parseFloat(totalGstElement.textContent.replace(/,/g, ''));
    totalNet = isNaN(totalNet) ? 0 : totalNet;
    totalGst = isNaN(totalGst) ? 0 : totalGst;
    // We'll sum up allocated net/gst from the table
    let allocatedNet = 0;
    let allocatedGst = 0;
    const tableBody = document.getElementById('lineItemsTableInvoices').tBodies[0];
    // We'll skip the last row ("Still to Allocate" row)
    for (let i = 0; i < tableBody.rows.length - 1; i++) {
      const row = tableBody.rows[i];
      // Net and GST columns are 3 and 4 in your table
      const netCell = row.cells[3];
      const gstCell = row.cells[4];
      let netVal = 0;
      let gstVal = 0;
      if (netCell && netCell.firstChild) {
        netVal = parseFloat(netCell.firstChild.value.replace(/,/g, '')) || 0;
      }
      if (gstCell && gstCell.firstChild) {
        gstVal = parseFloat(gstCell.firstChild.value.replace(/,/g, '')) || 0;
      }
      allocatedNet += netVal;
      allocatedGst += gstVal;
    }
    // Calculate how much is still to allocate
    const stillToAllocateInv = (totalNet - allocatedNet).toFixed(2);
    const stillToAllocateGST = (totalGst - allocatedGst).toFixed(2);
    // Update the "still to allocate" cells in your table
    // IDs: stillToAllocateInv and stillToAllocateGST from your HTML
    const stillToAllocateInvElem = document.getElementById('stillToAllocateInv');
    const stillToAllocateGstElem = document.getElementById('stillToAllocateGST');
    if (stillToAllocateInvElem) {
      stillToAllocateInvElem.textContent =
        parseFloat(stillToAllocateInv).toLocaleString('en-US', { minimumFractionDigits: 2 });
    }
    if (stillToAllocateGstElem) {
      stillToAllocateGstElem.textContent =
        parseFloat(stillToAllocateGST).toLocaleString('en-US', { minimumFractionDigits: 2 });
    }
  }
  

async function saveDirectCostInvoices() {
    // 1) Retrieve invoice ID
    const invoiceId = document.getElementById("hiddenInvoiceIdInvoices")?.value || "";
    const table = document.getElementById("lineItemsTableInvoices");
    if (!table) return;
  
    // 2) Check "Still to Allocate" must be 0 for Net and GST
    const stillToAllocateInvElem = document.getElementById("stillToAllocateInv");
    const stillToAllocateGSTElem = document.getElementById("stillToAllocateGST");
    const stillToAllocateNet = parseFloat(stillToAllocateInvElem?.textContent.replace(/,/g, "") || 0);
    const stillToAllocateGst = parseFloat(stillToAllocateGSTElem?.textContent.replace(/,/g, "") || 0);
    if (stillToAllocateNet !== 0 || stillToAllocateGst !== 0) {
      alert("Still to Allocate Net Amount & GST must both be 0.00");
      return;
    }
  
    // 3) Gather Allocations
    const tableBody = table.tBodies[0];
    const rows = tableBody.querySelectorAll("tr");
    const allocations = [];
  
    // We expect the final row to be stillToAllocateInvoicesRow, so we skip it
    rows.forEach(row => {
      if (row.id === "stillToAllocateInvoicesRow") return;
  
      const cells = row.cells;
      if (!cells || !cells.length) return;
  
      /*
        Based on your column definitions, we have:
  
        col0: <select> for item
        col1: 'Old' uncommitted
        col2: 'New' uncommitted input
        col3: 'Net' input
        col4: 'GST' input
        col5: 'Total' cell
        col6: 'Notes' input
        col7: (delete button)
      */
  
      const newUncommittedCell = cells[2];
      const netCell = cells[3];
      const gstCell = cells[4];
      const notesCell = cells[6];
  
      // Retrieve input values
      let newUncommittedVal = 0;
      if (newUncommittedCell && newUncommittedCell.firstChild) {
        newUncommittedVal = parseFloat(newUncommittedCell.firstChild.value || "0") || 0;
      }
  
      let netVal = 0;
      if (netCell && netCell.firstChild) {
        netVal = parseFloat(netCell.firstChild.value || "0") || 0;
      }
  
      let gstVal = 0;
      if (gstCell && gstCell.firstChild) {
        gstVal = parseFloat(gstCell.firstChild.value || "0") || 0;
      }
  
      let notesVal = "";
      if (notesCell && notesCell.firstChild) {
        notesVal = notesCell.firstChild.value || "";
      }
  
      // If net=0 & gst=0 & newUncommitted=0 & no notes => skip
      if (netVal === 0 && gstVal === 0 && newUncommittedVal === 0 && !notesVal.trim()) {
        return;
      }
  
      // 4) Retrieve item_pk from <select> or data-costing-id
      let itemPk = null;
      const firstCell = cells[0];
      if (firstCell) {
        // If there's a <select>
        const select = firstCell.querySelector("select");
        if (select) {
          const selectedVal = select.value?.trim();
          if ((netVal !== 0 || gstVal !== 0 || newUncommittedVal !== 0) && !selectedVal) {
            alert("Amounts allocated but no Line Item selected from Dropdown box.");
            throw new Error("Validation halted saveDirectCostInvoices");
          }
          const selectedOption = select.querySelector(`option[value="${selectedVal}"]`);
          if (selectedOption) {
            itemPk = selectedOption.getAttribute("data-costing-id");
          }
        }
      }
      if (!itemPk) return;
  
      // Optionally, if you have "allocation_type" logic, set it. For direct cost, you might set allocation_type = 0 or 1
      let allocation_type = 0; // or 1 if needed
  
      allocations.push({
        item_pk: itemPk,
        uncommitted_new: newUncommittedVal, // Changed from new_uncommitted to uncommitted_new to match server expectation
        net: netVal,
        gst: gstVal,
        notes: notesVal,
        allocation_type: allocation_type
      });
    });
  
    // 5) Build Payload
    const payload = {
      invoice_id: invoiceId,
      allocations: allocations
    };
  
    console.log("Sending Direct Cost payload:", payload);
  
    // 6) POST
    try {
      const response = await fetch("/post_direct_cost_data/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCookieInvoices("csrftoken"),
        },
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        throw new Error(`Network response was not ok. Status: ${response.status}`);
      }
      const result = await response.json();
      alert("Direct cost data posted successfully!");
      location.reload();
    } catch (error) {
      console.error("Error posting direct cost data:", error);
      alert("Error saving direct cost data:\n" + error.message);
    }
  }
  