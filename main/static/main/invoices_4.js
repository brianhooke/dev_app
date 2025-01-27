//Progress Claim Invoice Allocation Modal JS

document.addEventListener('DOMContentLoaded', function() {
  });

  document.getElementById('addVariationButton').addEventListener('click', function() {
    addProgressClaimLine();
  });
  
/* Creates or finds the "Variations" heading row (unchanged) */
function createOrFindVariationsRow(tableBody, stillRow, colSpan) {
    let variationsRow = document.getElementById('variationsHeadingRow');
    if (!variationsRow) {
      variationsRow = document.createElement('tr');
      variationsRow.id = 'variationsHeadingRow';
      const variationsCell = variationsRow.insertCell();
      variationsCell.colSpan = colSpan;
      variationsCell.textContent = "Variations";
      variationsCell.style.fontWeight = "bold";
      variationsCell.style.fontSize = "1.2em";
      tableBody.insertBefore(variationsRow, stillRow);
    }
    return variationsRow;
  }
  
  /* Updated progressClaimModalData to tag direct-cost lines with data-variation-row="1" */
  function progressClaimModalData(
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
    grossAmount = "",
    contactPk = null
  ) {
    const pdfViewer = document.getElementById('progressClaimInvoicesPdfViewer');
    const supplierElement = document.getElementById('progressClaimSupplierInvoices');
    const totalElement = document.getElementById('progressClaimTotalInvoices');
    const gstTotalElement = document.getElementById('progressClaimGstTotalInvoices');
    const invoiceNumberElement = document.getElementById('progressClaimInvoiceNumberInvoices');
    const invoiceDateElement = document.getElementById('progressClaimInvoiceDateInvoices');
    const invoiceDueDateElement = document.getElementById('progressClaimInvoiceDueDateInvoices');
    const grossAmountElement = document.getElementById('progressClaimGrossAmountInvoices');
    const hiddenInvoiceIdElement = document.getElementById('hiddenInvoiceIdInvoices');
    const table = document.getElementById('progressClaimLineItemsTableInvoices');
    const tableHead = table.querySelector('thead');
    const tableBody = table.querySelector('tbody');
  
    pdfViewer.src = pdfFilename;
    supplierElement.textContent = supplier;
    totalElement.textContent = totalNet.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    gstTotalElement.textContent = totalGst.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    invoiceNumberElement.textContent = invoiceNumber;
    invoiceDateElement.textContent = invoiceDate;
    invoiceDueDateElement.textContent = invoiceDueDate;
    grossAmountElement.textContent = parseFloat(grossAmount).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    hiddenInvoiceIdElement.value = invoiceId;
  
    let quoteData = [];
    let invoiceData = [];
    const quoteObj = progress_claim_quote_allocations.find(o => o.contact_pk === parseInt(contactPk));
    if (quoteObj) {
      quoteData = quoteObj.quotes.map(q => ({
        quote_number: q.quote_number,
        quote_allocations: q.allocations.map(a => ({
          item_pk: a.item_pk,
          item_name: a.item_name,
          amount: a.amount
        }))
      }));
    }
    const invoiceObj = progress_claim_invoice_allocations.find(o => o.contact_pk === parseInt(contactPk));
    if (invoiceObj) {
      invoiceData = invoiceObj.invoices.map(i => ({
        invoice_number: i.invoice_number,
        invoice_allocations: i.allocations.map(a => ({
          item_pk: a.item_pk,
          item_name: a.item_name,
          amount: a.amount,
          invoice_allocation_type: a.invoice_allocation_type
        }))
      }));
    }
  
    if ((!quoteData.length) && (!invoiceData.length)) {
      alert('No data available for this contact.');
      return;
    }
  
    const numQuotes = quoteData.length;
    const numInvoices = invoiceData.length;
    while (tableHead.rows.length > 0) tableHead.deleteRow(0);
    while (tableBody.rows.length > 0) tableBody.deleteRow(0);
  
    const firstRow = tableHead.insertRow();
    const secondRow = tableHead.insertRow();
    const gradientStyle = "background: linear-gradient(45deg,#B3E1DD 0%,#A090D0 100%); color:#fff; text-align:center;";
  
    let cell = firstRow.insertCell();
    cell.rowSpan = 2;
    cell.style.cssText = gradientStyle + "width:15%;";
    cell.textContent = "Item";
  
    cell = firstRow.insertCell();
    cell.colSpan = numQuotes + 1;
    cell.style.cssText = gradientStyle;
    cell.textContent = "Committed Quotes";
  
    cell = firstRow.insertCell();
    cell.colSpan = numInvoices + 1;
    cell.style.cssText = gradientStyle;
    cell.textContent = "Previous Claims";
  
    cell = firstRow.insertCell();
    cell.colSpan = 2;
    cell.style.cssText = gradientStyle;
    cell.textContent = "This Claim";
  
    cell = firstRow.insertCell();
    cell.rowSpan = 2;
    cell.style.cssText = gradientStyle + "width:10%;";
    cell.textContent = "Still to Claim";
  
    for (let i = 0; i < numQuotes; i++) {
      cell = secondRow.insertCell();
      cell.style.cssText = gradientStyle;
      cell.textContent = `Quote ${i + 1}`;
    }
    cell = secondRow.insertCell();
    cell.style.cssText = gradientStyle;
    cell.textContent = "Total";
    for (let i = 0; i < numInvoices; i++) {
      cell = secondRow.insertCell();
      cell.style.cssText = gradientStyle;
      cell.textContent = `Invoice ${i + 1}`;
    }
    cell = secondRow.insertCell();
    cell.style.cssText = gradientStyle;
    cell.textContent = "Total";
    cell = secondRow.insertCell();
    cell.style.cssText = gradientStyle;
    cell.textContent = "Net";
    cell = secondRow.insertCell();
    cell.style.cssText = gradientStyle;
    cell.textContent = "GST";
  
    const consolidatedItems = {};
    const directCostItems = {};
  
    quoteData.forEach((q, qIndex) => {
      q.quote_allocations.forEach(a => {
        const k = a.item_pk;
        if (!consolidatedItems[k]) {
          consolidatedItems[k] = {
            itemPk: a.item_pk,
            itemName: a.item_name,
            quoteValues: Array(numQuotes).fill(0),
            invoiceValues: Array(numInvoices).fill(0)
          };
        }
        consolidatedItems[k].quoteValues[qIndex] += parseFloat(a.amount) || 0;
      });
    });
  
    invoiceData.forEach((inv, invIndex) => {
      inv.invoice_allocations.forEach(a => {
        if (a.invoice_allocation_type === "progress_claim") {
          const k = a.item_pk;
          if (!consolidatedItems[k]) {
            consolidatedItems[k] = {
              itemPk: a.item_pk,
              itemName: a.item_name,
              quoteValues: Array(numQuotes).fill(0),
              invoiceValues: Array(numInvoices).fill(0)
            };
          }
          consolidatedItems[k].invoiceValues[invIndex] += parseFloat(a.amount) || 0;
        } else {
          const k = a.item_pk;
          if (!directCostItems[k]) {
            directCostItems[k] = {
              itemPk: a.item_pk,
              itemName: a.item_name,
              invoiceValues: Array(numInvoices).fill(0)
            };
          }
          directCostItems[k].invoiceValues[invIndex] += parseFloat(a.amount) || 0;
        }
      });
    });
  
    Object.entries(consolidatedItems).forEach(([k, d]) => {
      const newRow = document.createElement('tr');
      const itemCell = newRow.insertCell();
      itemCell.textContent = d.itemName;
      itemCell.setAttribute("data-costing-id", d.itemPk);
  
      d.quoteValues.forEach(amount => {
        const c = newRow.insertCell();
        c.textContent = amount === 0 ? '-' : amount.toLocaleString('en-US', { minimumFractionDigits: 2 });
      });
  
      const totalQuoteCell = newRow.insertCell();
      const totalQuote = d.quoteValues.reduce((s, v) => s + v, 0);
      totalQuoteCell.textContent = totalQuote === 0 ? '-' : totalQuote.toLocaleString('en-US', { minimumFractionDigits: 2 });
      totalQuoteCell.style.fontWeight = 'bold';
  
      d.invoiceValues.forEach(amount => {
        const c = newRow.insertCell();
        c.textContent = amount === 0 ? '-' : amount.toLocaleString('en-US', { minimumFractionDigits: 2 });
      });
  
      const totalInvoiceCell = newRow.insertCell();
      const totalInvoice = d.invoiceValues.reduce((s, v) => s + v, 0);
      totalInvoiceCell.textContent = totalInvoice === 0 ? '-' : totalInvoice.toLocaleString('en-US', { minimumFractionDigits: 2 });
      totalInvoiceCell.style.fontWeight = 'bold';
  
      const netCell = newRow.insertCell();
      const netInput = document.createElement('input');
      netInput.type = 'number';
      netInput.step = '0.01';
      netInput.style.width = '100%';
      netInput.addEventListener('input', updateStillToAllocateValues);
      netCell.appendChild(netInput);
  
      const gstCell = newRow.insertCell();
      const gstInput = document.createElement('input');
      gstInput.type = 'number';
      gstInput.step = '0.01';
      gstInput.style.width = '100%';
      gstInput.addEventListener('input', updateStillToAllocateValues);
      gstCell.appendChild(gstInput);
  
      const stillCell = newRow.insertCell();
      const stillVal = totalQuote - totalInvoice - (parseFloat(netInput.value) || 0);
      stillCell.textContent = stillVal.toLocaleString('en-US', { minimumFractionDigits: 2 });
      netInput.addEventListener('input', () => {
        const newVal = totalQuote - totalInvoice - (parseFloat(netInput.value) || 0);
        stillCell.textContent = newVal.toLocaleString('en-US', { minimumFractionDigits: 2 });
      });
      gstInput.addEventListener('input', () => {
        const newVal = totalQuote - totalInvoice - (parseFloat(netInput.value) || 0);
        stillCell.textContent = newVal.toLocaleString('en-US', { minimumFractionDigits: 2 });
      });
  
      tableBody.appendChild(newRow);
    });
  
    // Compute sums for quotes/invoices/still, then build Totals row
    const allRows = tableBody.querySelectorAll('tr');
    let sumsQuotes = Array(numQuotes).fill(0);
    let sumsInvoices = Array(numInvoices).fill(0);
    let sumQuotesTotal = 0;
    let sumInvoicesTotal = 0;
    let sumStillColumn = 0;
  
    allRows.forEach(row => {
      if (row.id === "variationsHeadingRow" || row.id === "progressClaimstillToAllocateInvoicesRow") return;
      const cells = row.cells;
      if (!cells.length) return;
      for (let q = 0; q < numQuotes; q++) {
        const valQ = parseFloat(cells[1 + q]?.textContent.replace(/,/g, '')) || 0;
        sumsQuotes[q] += isNaN(valQ) ? 0 : valQ;
      }
      const idxQuotesTotal = 1 + numQuotes;
      const valQuotesTotal = parseFloat(cells[idxQuotesTotal]?.textContent.replace(/,/g, '')) || 0;
      sumQuotesTotal += isNaN(valQuotesTotal) ? 0 : valQuotesTotal;
      for (let i = 0; i < numInvoices; i++) {
        const idxInv = 2 + numQuotes + i;
        const valInv = parseFloat(cells[idxInv]?.textContent.replace(/,/g, '')) || 0;
        sumsInvoices[i] += isNaN(valInv) ? 0 : valInv;
      }
      const idxInvTotal = 2 + numQuotes + numInvoices;
      const valInvTotal = parseFloat(cells[idxInvTotal]?.textContent.replace(/,/g, '')) || 0;
      sumInvoicesTotal += isNaN(valInvTotal) ? 0 : valInvTotal;
      const idxStill = 5 + numQuotes + numInvoices;
      const valStill = parseFloat(cells[idxStill]?.textContent.replace(/,/g, '')) || 0;
      sumStillColumn += isNaN(valStill) ? 0 : valStill;
    });
  
    const totalsRow = document.createElement('tr');
    const totalsLabelCell = totalsRow.insertCell();
    totalsLabelCell.textContent = "Totals";
    totalsLabelCell.style.fontWeight = "bold";
  
    for (let q = 0; q < numQuotes; q++) {
      const c = totalsRow.insertCell();
      c.style.fontWeight = "bold";
      c.textContent = sumsQuotes[q] === 0 ? "-" : sumsQuotes[q].toLocaleString('en-US', { minimumFractionDigits:2 });
    }
  
    const totalsQuotesCell = totalsRow.insertCell();
    totalsQuotesCell.style.fontWeight = "bold";
    totalsQuotesCell.textContent = sumQuotesTotal === 0 ? "-" : sumQuotesTotal.toLocaleString('en-US', { minimumFractionDigits:2 });
  
    for (let i = 0; i < numInvoices; i++) {
      const c = totalsRow.insertCell();
      c.style.fontWeight = "bold";
      c.textContent = sumsInvoices[i] === 0 ? "-" : sumsInvoices[i].toLocaleString('en-US', { minimumFractionDigits:2 });
    }
  
    const totalsInvCell = totalsRow.insertCell();
    totalsInvCell.style.fontWeight = "bold";
    totalsInvCell.textContent = sumInvoicesTotal === 0 ? "-" : sumInvoicesTotal.toLocaleString('en-US', { minimumFractionDigits:2 });
  
    totalsRow.insertCell().textContent = "";
    totalsRow.insertCell().textContent = "";
  
    const stillTotalsCell = totalsRow.insertCell();
    stillTotalsCell.style.fontWeight = "bold";
    if (sumStillColumn === 0) {
      stillTotalsCell.textContent = "-";
    } else {
      stillTotalsCell.textContent = sumStillColumn.toLocaleString('en-US', { minimumFractionDigits:2 });
    }
    tableBody.appendChild(totalsRow);
  
    const stillRow = document.createElement('tr');
    stillRow.id = "progressClaimstillToAllocateInvoicesRow";
    const labelTd = document.createElement('td');
    labelTd.textContent = "Still to Allocate";
    labelTd.colSpan = numQuotes + numInvoices + 3;
    stillRow.appendChild(labelTd);
  
    const netTd = document.createElement('td');
    netTd.id = "progressClaimStillToAllocateInv";
    netTd.textContent = "0.00";
    stillRow.appendChild(netTd);
  
    const gstTd = document.createElement('td');
    gstTd.id = "progressClaimStillToAllocateGST";
    gstTd.textContent = "0.00";
    stillRow.appendChild(gstTd);
  
    const stillClaimTd = document.createElement('td');
    stillClaimTd.id = "progressClaimTotal";
    stillClaimTd.textContent = "";
    stillRow.appendChild(stillClaimTd);
  
    tableBody.appendChild(stillRow);
    table.setAttribute('data-num-quotes', numQuotes.toString());
    table.setAttribute('data-num-invoices', numInvoices.toString());
    updateStillToAllocateValues();
    $('#progressClaimModal').modal('show');
  
    const directCostKeys = Object.keys(directCostItems);
    if (directCostKeys.length > 0) {
      const colSpan = numQuotes + numInvoices + 5;
      createOrFindVariationsRow(tableBody, stillRow, colSpan);
  
      directCostKeys.forEach(k => {
        const d = directCostItems[k];
        const newRow = document.createElement('tr');
        /* Tag direct-cost rows as variations: */
        newRow.setAttribute("data-variation-row", "1");
  
        const itemCell = newRow.insertCell();
        itemCell.textContent = d.itemName;
        itemCell.setAttribute("data-costing-id", d.itemPk);
  
        /* ... insert columns for quotes, invoices, etc. exactly as before ... */
  
        /* For example: */
        for (let i = 0; i < numQuotes; i++) {
          const td = newRow.insertCell();
          td.textContent = "-";
        }
        const quoteTotalCell = newRow.insertCell();
        quoteTotalCell.textContent = "-";
  
        let sumDC = 0;
        for (let i = 0; i < numInvoices; i++) {
          const invCell = newRow.insertCell();
          const amt = d.invoiceValues[i] || 0;
          invCell.textContent = amt === 0 ? "-" : amt.toLocaleString("en-US", { minimumFractionDigits: 2 });
          sumDC += amt;
        }
        const invTotalCell = newRow.insertCell();
        if (sumDC === 0) {
          invTotalCell.textContent = "-";
        } else {
          invTotalCell.textContent = sumDC.toLocaleString("en-US", { minimumFractionDigits: 2 });
          invTotalCell.style.fontWeight = "bold";
        }
  
        const netCell = newRow.insertCell();
        const netInput = document.createElement('input');
        netInput.type = 'number';
        netInput.step = '0.01';
        netInput.style.width = '100%';
        netInput.addEventListener('input', updateStillToAllocateValues);
        netCell.appendChild(netInput);
  
        const gstCell = newRow.insertCell();
        const gstInput = document.createElement('input');
        gstInput.type = 'number';
        gstInput.step = '0.01';
        gstInput.style.width = '100%';
        gstInput.addEventListener('input', updateStillToAllocateValues);
        gstCell.appendChild(gstInput);
  
        const stillCell = newRow.insertCell();
        const stillVal = sumDC - (parseFloat(netInput.value) || 0);
        stillCell.textContent = stillVal.toLocaleString("en-US", { minimumFractionDigits: 2 });
        netInput.addEventListener('input', () => {
          const newVal = sumDC - (parseFloat(netInput.value) || 0);
          stillCell.textContent = newVal.toLocaleString("en-US", { minimumFractionDigits: 2 });
        });
        gstInput.addEventListener('input', () => {
          const newVal = sumDC - (parseFloat(netInput.value) || 0);
          stillCell.textContent = newVal.toLocaleString("en-US", { minimumFractionDigits: 2 });
        });
  
        tableBody.insertBefore(newRow, stillRow);
      });
    }
  }
  
/* Updated addProgressClaimLine to mark newly added rows as "variations" by default */
function addProgressClaimLine() {
    const table = document.getElementById('progressClaimLineItemsTableInvoices');
    const tableBody = table.tBodies[0];
    if (!tableBody) return;
    const stillRow = document.getElementById('progressClaimstillToAllocateInvoicesRow');
    if (!stillRow) return;
  
    const numQuotes = parseInt(table.getAttribute('data-num-quotes')) || 0;
    const numInvoices = parseInt(table.getAttribute('data-num-invoices')) || 0;
    const colSpan = numQuotes + numInvoices + 5;
  
    createOrFindVariationsRow(tableBody, stillRow, colSpan);
  
    const newRow = document.createElement('tr');
    /* Tag these user-added lines as variations: */
    newRow.setAttribute("data-variation-row", "1");
  
    const itemCell = newRow.insertCell();
    const select = document.createElement('select');
    select.style.maxWidth = "100%";
    select.innerHTML = '<option value="">Select an item</option>';
    costings.forEach(costing => {
      select.innerHTML += `
        <option value="${costing.item}" data-costing-id="${costing.costing_pk}">
          ${costing.item}
        </option>`;
    });
    itemCell.appendChild(select);
  
    for (let i = 0; i < numQuotes; i++) {
      const quoteCell = newRow.insertCell();
      quoteCell.textContent = "-";
    }
    const quoteTotalCell = newRow.insertCell();
    quoteTotalCell.textContent = "-";
  
    for (let i = 0; i < numInvoices; i++) {
      const invCell = newRow.insertCell();
      invCell.textContent = "-";
    }
    const invTotalCell = newRow.insertCell();
    invTotalCell.textContent = "-";
  
    const netCell = newRow.insertCell();
    const netInput = document.createElement('input');
    netInput.type = 'number';
    netInput.step = '0.01';
    netInput.style.width = '100%';
    netInput.addEventListener('input', updateStillToAllocateValues);
    netCell.appendChild(netInput);
  
    const gstCell = newRow.insertCell();
    const gstInput = document.createElement('input');
    gstInput.type = 'number';
    gstInput.step = '0.01';
    gstInput.style.width = '100%';
    gstInput.addEventListener('input', updateStillToAllocateValues);
    gstCell.appendChild(gstInput);
  
    const stillCell = newRow.insertCell();
    stillCell.textContent = "";
  
    tableBody.insertBefore(newRow, stillRow);
  }
  
  // Reuse your updateStillToAllocateValues function as-is
  function updateStillToAllocateValues() {
    const netTotalElement = document.getElementById('progressClaimTotalInvoices');
    const gstTotalElement = document.getElementById('progressClaimGstTotalInvoices');
    const stillToAllocateNetElement = document.getElementById('progressClaimStillToAllocateInv');
    const stillToAllocateGstElement = document.getElementById('progressClaimStillToAllocateGST');
    const table = document.getElementById('progressClaimLineItemsTableInvoices');
    if (!table) return;
    const tableBody = table.tBodies[0];
    const numQuotes = parseInt(table.getAttribute('data-num-quotes')) || 0;
    const numInvoices = parseInt(table.getAttribute('data-num-invoices')) || 0;
    const netTotal = parseFloat(netTotalElement?.textContent.replace(/,/g, '') || 0) || 0;
    const gstTotal = parseFloat(gstTotalElement?.textContent.replace(/,/g, '') || 0) || 0;
  
    let allocatedNet = 0;
    let allocatedGst = 0;
  
    // The last row is for "Still to Allocate", so skip that
    for (let i = 0; i < tableBody.rows.length - 1; i++) {
      const row = tableBody.rows[i];
      const netIndex = numQuotes + numInvoices + 3;
      const gstIndex = numQuotes + numInvoices + 4;
      const netInput = row.cells[netIndex]?.querySelector('input');
      const gstInput = row.cells[gstIndex]?.querySelector('input');
      const netVal = parseFloat(netInput?.value || 0) || 0;
      const gstVal = parseFloat(gstInput?.value || 0) || 0;
      allocatedNet += netVal;
      allocatedGst += gstVal;
    }
  
    const stillToAllocateNet = netTotal - allocatedNet;
    const stillToAllocateGst = gstTotal - allocatedGst;
    stillToAllocateNetElement.textContent = stillToAllocateNet.toFixed(2);
    stillToAllocateGstElement.textContent = stillToAllocateGst.toFixed(2);
  
    const stillRow = document.getElementById("progressClaimstillToAllocateInvoicesRow");
    let cells = stillRow.cells;
    if (cells.length > 1) {
      cells[1].textContent = stillToAllocateNet.toFixed(2);
      if (cells.length > 2) cells[2].textContent = stillToAllocateGst.toFixed(2);
    }
  }
  
/* Updated saveProgressClaimInvoices: now uses row.getAttribute("data-variation-row") */
async function saveProgressClaimInvoices() {
    const invoiceId = document.getElementById("hiddenInvoiceIdInvoices").value;
    const table = document.getElementById("progressClaimLineItemsTableInvoices");
    if (!table) return;
  
    const stillToAllocateNet = parseFloat(document.getElementById("progressClaimStillToAllocateInv")?.textContent.replace(/,/g, "") || 0);
    const stillToAllocateGst = parseFloat(document.getElementById("progressClaimStillToAllocateGST")?.textContent.replace(/,/g, "") || 0);
    if (stillToAllocateNet !== 0 || stillToAllocateGst !== 0) {
      alert("Still to Allocate Net Amount & GST must both be 0.00");
      return;
    }
  
    const tableBody = table.tBodies[0];
    const rows = tableBody.querySelectorAll("tr");
    const numQuotes = parseInt(table.getAttribute("data-num-quotes")) || 0;
    const numInvoices = parseInt(table.getAttribute("data-num-invoices")) || 0;
    const allocations = [];
  
    rows.forEach((row) => {
      if (row.id === "variationsHeadingRow" || row.id === "progressClaimstillToAllocateInvoicesRow") return;
  
      const cells = row.cells;
      if (!cells?.length) return;
      const netIndex = numQuotes + numInvoices + 3;
      const gstIndex = numQuotes + numInvoices + 4;
      const netInput = cells[netIndex]?.querySelector("input");
      const gstInput = cells[gstIndex]?.querySelector("input");
      if (!netInput || !gstInput) return;
  
      const netVal = parseFloat(netInput.value || "0") || 0;
      const gstVal = parseFloat(gstInput.value || "0") || 0;
      if (netVal === 0 && gstVal === 0) return;
  
      // Use data-variation-row attribute
      let allocation_type = 0;
      if (row.getAttribute("data-variation-row") === "1") {
        allocation_type = 1;
      }
  
      let itemPk = cells[0]?.getAttribute("data-costing-id") || null;
  
      // If there's a <select>, we still want to check an item is selected
      const select = cells[0]?.querySelector("select");
      if (select) {
        const selectedVal = select.value?.trim();
        if ((netVal !== 0 || gstVal !== 0) && !selectedVal) {
          alert("Amounts allocated to a Variation but no Line Item selected from Dropdown box.");
          throw new Error("Validation halted saveProgressClaimInvoices");
        }
        const selectedOption = select.querySelector(`option[value="${selectedVal}"]`);
        if (selectedOption) {
          itemPk = selectedOption.getAttribute("data-costing-id") || null;
        }
      }
  
      if (!itemPk) return;
  
      allocations.push({
        item_pk: itemPk,
        net: netVal,
        gst: gstVal,
        allocation_type: allocation_type,
      });
    });
  
    const payload = {
      invoice_id: invoiceId,
      allocations: allocations,
    };
  
    console.log("Sending payload:", payload);
  
try {
    const response = await fetch("/post_progress_claim_data/", {
        method: "POST",
        headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCookie("csrftoken"),
        },
        body: JSON.stringify(payload),
    });
    if (!response.ok) {
        throw new Error(`Network response was not ok. Status: ${response.status}`);
    }
    const result = await response.json();
    alert("Progress claim data posted successfully!");
    location.reload(); // <--- Add this line to refresh the page on success
    } catch (error) {
    console.error("Error posting progress claim data:", error);
    alert("Error saving progress claim data:\n" + error.message);
    }
      
  
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
}