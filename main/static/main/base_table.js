function formatDropdownContextDate(dateString) {
  if (!dateString) {
    return '-';
  }
    var trimmed = dateString.trim();  
  if (trimmed.indexOf('/') === -1) {
    console.error("Date string does not contain '/':", trimmed);
    return 'Invalid Date';
  }
  const parts = trimmed.split('/');  
  if (parts.length < 3) {
    console.error("Date string does not have at least 3 parts:", trimmed);
    return 'Invalid Date';
  }
    const dayStr = parts[0].trim();
  const monthStr = parts[1].trim();
  const yearStr = parts[2].trim();
  const dayNum = parseInt(dayStr, 10);
  const monthNum = parseInt(monthStr, 10);
  const yearNum = parseInt(yearStr, 10);
    if (isNaN(dayNum) || isNaN(monthNum) || isNaN(yearNum)) {
    console.error("One or more parts are not valid numbers:", {
      original: dateString,
      trimmed: trimmed,
      dayStr: dayStr,
      monthStr: monthStr,
      yearStr: yearStr,
      dayNum: dayNum,
      monthNum: monthNum,
      yearNum: yearNum
    });
    return 'Invalid Date';
  }
    const date = new Date(yearNum, monthNum - 1, dayNum);
  if (isNaN(date.getTime())) {
    console.error("Final constructed Date is invalid. Details:", {
      original: dateString,
      trimmed: trimmed,
      constructedDate: date
    });
    return 'Invalid Date';
  }
    const day = date.getDate().toString().padStart(2, '0');
  const month = date.toLocaleString('en-US', { month: 'short' });
  const year = date.getFullYear().toString().slice(-2);
  const formatted = `${day}-${month}-${year}`;
  return formatted;
}

// Initialize once DOM is fully loaded to avoid race conditions
document.addEventListener('DOMContentLoaded', function() {
  // Step 1: Update all contract budgets to include variation amounts
  updateAllContractBudgets();
  
  // Step 2: After updating budgets, toggle collapse state
  setTimeout(function() {
    // First expand all rows so category values can be calculated
    document.querySelectorAll('tr[data-toggle="collapse"]').forEach(row => {
      if (row.classList.contains('collapsed')) {
        row.click();
      }
    });
    
    // Then recalculate all category totals
    recalculateAllCategoryTotals();
    
    // Then collapse all rows to start with a clean view
    document.querySelectorAll('tr[data-toggle="collapse"]').forEach(row => {
      if (!row.classList.contains('collapsed')) {
        row.click();
      }
    });
  }, 100);
  
  /**
   * Closes all dropdown menus except for the one specified
   * @param {Event} event - The click event
   * @param {Element|null} exceptDropdown - The dropdown to keep open, or null to close all
   */
  function closeAllDropdownsExcept(event, exceptDropdown) {
    const dropdowns = document.querySelectorAll('.dropdown-content');
    dropdowns.forEach(dropdown => {
      if (dropdown !== exceptDropdown && !dropdown.contains(event.target)) {
        dropdown.style.display = 'none';
      }
    });
  }

  // Add event listener to close dropdowns when clicking outside
  document.addEventListener('click', function(event) {
    closeAllDropdownsExcept(event, null);
  });
  
  // Add click event listeners for contract budget cells
  document.querySelectorAll('.contract-budget-cell').forEach(cell => {
    cell.addEventListener('click', function(event) {
      const costingPk = this.getAttribute('data-costing-pk');
      toggleContractBudgetDropdown(this, costingPk, event);
    });
  });
  
  // Update the main totals row to include HC variations
  updateMainTotalsRow();
});

/**
 * Recalculate all category totals
 */
function recalculateAllCategoryTotals() {
  document.querySelectorAll('tr[data-toggle="collapse"]').forEach(row => {
    const groupNumber = row.getAttribute('data-target')?.replace('.group', '');
    if (groupNumber) {
      // Force recalculation of category totals
      $(row).trigger('click').trigger('click');
    }
  });
}

/**
 * Update the main totals row to correctly include HC variations in the Contract Budget column
 */
function updateMainTotalsRow() {
  var grandTotalContractBudget = 0;
  
  // Process each costing item to recalculate the total contract budget
  const costingRows = document.querySelectorAll('tr[data-costing-pk]');
  costingRows.forEach(row => {
    const costingPk = row.getAttribute('data-costing-pk');
    if (costingPk) {
      // Use our function that includes HC variations
      const totalBudget = calculateContractBudgetWithVariations(costingPk);
      grandTotalContractBudget += totalBudget;
    }
  });
  
  // Update the HTML in the totals row
  const totalRowContractBudgetCell = document.querySelector('#totalRow td:nth-child(3)');
  if (totalRowContractBudgetCell) {
    if (grandTotalContractBudget === 0) {
      totalRowContractBudgetCell.innerHTML = '-';
    } else {
      const formattedTotal = grandTotalContractBudget.toLocaleString('en-US', { 
        minimumFractionDigits: 2, 
        maximumFractionDigits: 2 
      });
      totalRowContractBudgetCell.innerHTML = '<strong>' + formattedTotal + '</strong>';
    }
  }
}

/**
 * Calculate the total contract budget for a costing item by adding the original budget
 * and any variation amounts allocated to that item
 */
function calculateContractBudgetWithVariations(costingPk) {
  // Get the original contract budget
  const budgetElement = document.getElementById(`contract-budget-${costingPk}`);
  if (!budgetElement) return 0;
  
  const originalBudget = parseFloat(budgetElement.getAttribute('data-original-budget') || 0);
  let totalVariations = 0;
  
  // Find all variation allocations for this costing item
  if (typeof hc_variation_allocations !== 'undefined') {
    const variations = hc_variation_allocations.filter(v => v.costing_pk == costingPk);
    
    // Sum up the variation amounts
    for (const variation of variations) {
      totalVariations += parseFloat(variation.amount || 0);
    }
  }
  
  // Return the sum of original budget and all variations
  return originalBudget + totalVariations;
}

/**
 * Update all contract budget displays to include variations
 */
function updateAllContractBudgets() {
  // Process each costing item
  const costingRows = document.querySelectorAll('tr[data-costing-pk]');
  costingRows.forEach(row => {
    const costingPk = row.getAttribute('data-costing-pk');
    const budgetElement = document.getElementById(`contract-budget-${costingPk}`);
    
    if (budgetElement) {
      const totalBudget = calculateContractBudgetWithVariations(costingPk);
      
      // Format the amount with commas and 2 decimal places
      const formattedBudget = totalBudget === 0 ? '-' : 
        totalBudget.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
      
      budgetElement.textContent = formattedBudget;
      
      // Populate the dropdown with variation details
      populateContractBudgetDropdown(costingPk);
    }
  });
}

/**
 * Format date for display in dropdowns
 */
function formatDropdownDate(dateStr) {
  if (!dateStr) return '-';
  
  try {
    // Parse the date string (format: YYYY-MM-DD)
    const parts = dateStr.split('-');
    if (parts.length !== 3) return dateStr;
    
    // Create a Date object (months are 0-indexed in JavaScript)
    const date = new Date(parts[0], parts[1] - 1, parts[2]);
    
    // Get the day
    const day = date.getDate().toString().padStart(2, '0');
    
    // Get the 3-letter month name
    const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    const month = monthNames[date.getMonth()];
    
    // Get the 2-digit year
    const year = date.getFullYear().toString().slice(2);
    
    // Format as DD-MMM-YY
    return `${day}-${month}-${year}`;
  } catch (e) {
    console.error('Error formatting date:', e);
    return dateStr;
  }
}

/**
 * Populate the contract budget dropdown with variation details
 */
function populateContractBudgetDropdown(costingPk) {
  if (typeof hc_variation_allocations === 'undefined') return;
  
  const dropdown = document.getElementById(`contract-budget-dropdown-${costingPk}`);
  if (!dropdown) return;
  
  const dropdownBody = dropdown.querySelector('.dropdown-body');
  if (!dropdownBody) return;
  
  // Find all variation allocations for this costing item
  const variations = hc_variation_allocations.filter(v => v.costing_pk == costingPk);
  
  // Clear existing variation rows (except the original budget row)
  const originalRow = dropdownBody.querySelector('.dropdown-row');
  dropdownBody.innerHTML = '';
  if (originalRow) {
    dropdownBody.appendChild(originalRow);
  }
  
  // Only add HC Variations section if there are variations for this costing
  if (variations.length > 0) {
    // Add HC Variations section header
    const variationsHeader = document.createElement('div');
    variationsHeader.className = 'dropdown-row dropdown-section-header';
    variationsHeader.innerHTML = '<div><strong>HC Variations</strong></div><div></div><div></div>';
    dropdownBody.appendChild(variationsHeader);
    
    // Add rows for each variation allocation
    for (const variation of variations) {
      const row = document.createElement('div');
      row.className = 'dropdown-row';
      
      const dateCell = document.createElement('div');
      dateCell.textContent = formatDropdownDate(variation.variation_date) || '-';
      
      const notesCell = document.createElement('div');
      notesCell.textContent = variation.notes || '-';
      
      const amountCell = document.createElement('div');
      const amount = parseFloat(variation.amount || 0);
      amountCell.textContent = '$' + amount.toLocaleString('en-US', { 
        minimumFractionDigits: 2, 
        maximumFractionDigits: 2 
      });
      
      row.appendChild(dateCell);
      row.appendChild(notesCell);
      row.appendChild(amountCell);
      
      dropdownBody.appendChild(row);
    }
  }
}

/**
 * Initialize the displayed contract budgets with variation amounts
 */
function updateAllContractBudgets() {
  // Process each costing item
  const costingRows = document.querySelectorAll('tr[data-costing-pk]');
  costingRows.forEach(row => {
    const costingPk = row.getAttribute('data-costing-pk');
    const budgetElement = document.getElementById(`contract-budget-${costingPk}`);
    
    if (budgetElement) {
      const totalBudget = calculateContractBudgetWithVariations(costingPk);
      
      // Format the amount with commas and 2 decimal places
      const formattedBudget = totalBudget === 0 ? '-' : 
        totalBudget.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
      
      budgetElement.textContent = formattedBudget;
    }
  });
}

document.querySelectorAll('.save-costs').forEach(function(button) {
  button.addEventListener('click', function() {
    var costing_pk = this.getAttribute('data-id');
    var uncommitted = document.getElementById('uncommittedInput' + costing_pk).value;
    var notes = document.getElementById('notesInput' + costing_pk).value;
    if (!costing_pk || !uncommitted) {
      alert('Costing ID or uncommitted value is missing');
      return;
    }
    var data = { 
      'costing_pk': costing_pk, 
      'uncommitted': uncommitted,
      'notes': notes 
    };
    fetch('/update_uncommitted/', {
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
    }).catch(function(error) {
      console.error('Error:', error);
      alert('An error occurred while updating the costs.');
    });
  });
});

$('[data-toggle="collapse"]').on('click', function () {
  $(this).toggleClass('collapsed');
  var groupNumber = $(this).data('target').replace('.group', '');
  var sumContractBudget = 0, sumWorkingBudget = 0, sumUncommitted = 0,
      sumCommitted = 0, sumC2C = 0, sumInvoiced = 0, sumFixedOnSite = 0;
  $('.group' + groupNumber).each(function () {
    // Get the costing PK from the row's data attribute
    var costingPk = $(this).data('costing-pk');
    
    // Extract values from cells, using appropriate selectors
    var contractBudgetCell = $(this).find('td').eq(2);
    var workingBudget = $(this).find('td').eq(3).find('.working-budget-value').text().replace(/,/g, '').trim();
    var uncommitted = $(this).find('td').eq(4).text().replace(/,/g, '').trim();
    var committed = $(this).find('td').eq(5).text().replace(/,/g, '').trim();
    
    // For C2C - try both with and without span selector
    var c2c = $(this).find('td').eq(6).text().replace(/,/g, '').trim();
    if (c2c === '-') c2c = '0';
    
    // For invoiced - be careful with the selection
    var invoicedCell = $(this).find('td').eq(7);
    var invoicedText = invoicedCell.find('.invoiced-value').length > 0 ? 
                       invoicedCell.find('.invoiced-value').text().replace(/,/g, '').trim() : 
                       invoicedCell.text().replace(/,/g, '').trim();
    if (invoicedText === '-') invoicedText = '0';
    
    var fixedOnSite = $(this).find('td').eq(8).text().replace(/,/g, '').trim();
    if (fixedOnSite === '-') fixedOnSite = '0';
    
    // Calculate contract budget properly to include HC variations
    var contractBudget = 0;
    if (costingPk) {
      // Use our dedicated function that includes HC variations
      contractBudget = calculateContractBudgetWithVariations(costingPk);
    } else {
      // Fallback to displayed text if no costingPk is available
      var contractBudgetText = contractBudgetCell.text().replace(/,/g, '').trim();
      contractBudget = (contractBudgetText === '-' || contractBudgetText === '' || isNaN(parseFloat(contractBudgetText))) ? 0 : parseFloat(contractBudgetText);
    }
    
    // Make sure we have valid numbers
    var invoiced = invoicedText;
    workingBudget = (workingBudget === '-' || workingBudget === '') ? 0 : parseFloat(workingBudget);
    uncommitted = (uncommitted === '-' || uncommitted === '') ? 0 : parseFloat(uncommitted);
    committed = (committed === '-' || committed === '') ? 0 : parseFloat(committed);
    c2c = (c2c === '-' || c2c === '') ? 0 : parseFloat(c2c);
    fixedOnSite = (fixedOnSite === '-' || fixedOnSite === '') ? 0 : parseFloat(fixedOnSite);
    invoiced = (invoiced === '-' || invoiced === '') ? 0 : parseFloat(invoiced || '0');
    
    // Add to running totals
    sumContractBudget += contractBudget;
    sumWorkingBudget += workingBudget;
    sumUncommitted += uncommitted;
    sumCommitted += committed;
    sumC2C += c2c;
    sumFixedOnSite += fixedOnSite;
    sumInvoiced += invoiced;
  });
  function formatNumber(num) {
    return num.toString().replace(/(\d)(?=(\d{3})+(?!\d))/g, '$1,');
  }
  var row = $(this).closest('tr'),
      contractBudgetCell = row.find('td').eq(2),
      workingBudgetCell = row.find('td').eq(3),
      uncommittedCell = row.find('td').eq(4),
      committedCell = row.find('td').eq(5),
      c2cCell = row.find('td').eq(6),
      invoicedCell = row.find('td').eq(7),
      fixedOnSiteCell = row.find('td').eq(8);
  if ($(this).hasClass('collapsed')) {
    contractBudgetCell.data('original', contractBudgetCell.html());
    workingBudgetCell.data('original', workingBudgetCell.html());
    uncommittedCell.data('original', uncommittedCell.html());
    committedCell.data('original', committedCell.html());
    c2cCell.data('original', c2cCell.html());
    fixedOnSiteCell.data('original', fixedOnSiteCell.html());
    invoicedCell.data('original', invoicedCell.html());
;
    
    contractBudgetCell.html(sumContractBudget.toFixed(2) == 0.00 ? '-' : '<strong>' + formatNumber(sumContractBudget.toFixed(2)) + '</strong>');
    workingBudgetCell.html(sumWorkingBudget.toFixed(2) == 0.00 ? '-' : '<strong>' + formatNumber(sumWorkingBudget.toFixed(2)) + '</strong>');
    uncommittedCell.html(sumUncommitted.toFixed(2) == 0.00 ? '-' : '<div class="uncommitted-value"><strong>' + formatNumber(sumUncommitted.toFixed(2)) + '</strong></div>');
    committedCell.html(sumCommitted.toFixed(2) == 0.00 ? '-' : '<strong>' + formatNumber(sumCommitted.toFixed(2)) + '</strong>');
    c2cCell.html(sumC2C.toFixed(2) == 0.00 ? '-' : '<strong>' + formatNumber(sumC2C.toFixed(2)) + '</strong>');
    invoicedCell.html(sumInvoiced.toFixed(2) == 0.00 ? '-' : '<strong>' + formatNumber(sumInvoiced.toFixed(2)) + '</strong>');
    fixedOnSiteCell.html(sumFixedOnSite.toFixed(2) == 0.00 ? '-' : '<strong>' + formatNumber(sumFixedOnSite.toFixed(2)) + '</strong>');
  } else {
    contractBudgetCell.html(contractBudgetCell.data('original'));
    workingBudgetCell.html(workingBudgetCell.data('original'));
    uncommittedCell.html(uncommittedCell.data('original'));
    committedCell.html(committedCell.data('original'));
    c2cCell.html(c2cCell.data('original'));
    invoicedCell.html(invoicedCell.data('original'));
    fixedOnSiteCell.html(fixedOnSiteCell.data('original'));
  }
});

/**
 * Handle dropdown toggling for all dropdown types
 */
function toggleDropdown(cell, costingPk, type, event) {
  // Prevent event propagation to stop the document click handler from immediately closing the dropdown
  if (event) {
    event.stopPropagation();
    event.preventDefault();
  }
  type = type || 'invoiced';
  var idPrefix;
  
  // Set the correct prefix based on dropdown type
  if (type === 'contract') {
    idPrefix = 'contract-dropdown-';
  } else if (type === 'invoiced') {
    idPrefix = 'dropdown-';
  } else if (type === 'committed') {
    idPrefix = 'committed-dropdown-';
  } else { // working
    idPrefix = 'working-dropdown-';
  }
  
  var dropdown = document.getElementById(idPrefix + costingPk);
  if (!dropdown) {
    console.error("Dropdown element not found for", type, "with costingPk:", costingPk);
    return;
  }
  
  // Close all other dropdowns
  var allDropdowns = document.querySelectorAll('.dropdown-content');
  allDropdowns.forEach(function(el) {
    if (el !== dropdown) {
      el.style.display = 'none';
    }
  });
  
  // Toggle this dropdown
  if (dropdown.style.display === 'block') {
    dropdown.style.display = 'none';
    return;
  } else {
    // Force dropdown to be visible
    dropdown.style.position = 'absolute';
    dropdown.style.display = 'block';
    dropdown.style.zIndex = '9999';
    dropdown.style.backgroundColor = 'white';
  }
  
  // Ensure consistent dropdown content for all categories, including Margin categories (category_order_in_list = -1)
  // Remove any special handling based on category_order_in_list = -1
  // The costingPk will be the same regardless of category type
  
  // Special handling for contract budget dropdown
  if (type === 'contract') {
    // Get the original budget value
    const budgetElement = document.getElementById(`contract-budget-${costingPk}`);
    const originalBudget = parseFloat(budgetElement.getAttribute('data-original-budget') || 0);
    
    dropdown.innerHTML = `
      <div class="dropdown-header">
        <div><strong>Item</strong></div>
        <div><strong>Date</strong></div>
        <div><strong>Notes</strong></div>
        <div><strong>$</strong></div>
      </div>
      <div class="dropdown-body">
        <div class="dropdown-row">
          <div>Contract Budget</div>
          <div></div>
          <div></div>
          <div>$${originalBudget.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</div>
        </div>
      </div>
    `;
    
    // Add HC Variations section if there are variations for this costing
    if (typeof hc_variation_allocations !== 'undefined') {
      const variations = hc_variation_allocations.filter(v => v.costing_pk == costingPk);
      
      if (variations.length > 0) {
        const dropdownBody = dropdown.querySelector('.dropdown-body');
        
        // Add HC Variations section header
        const variationsHeader = document.createElement('div');
        variationsHeader.className = 'dropdown-row dropdown-section-header';
        variationsHeader.innerHTML = '<div><strong>HC Variations</strong></div><div></div><div></div><div></div>';
        dropdownBody.appendChild(variationsHeader);
        
        // Add rows for each variation allocation
        for (const variation of variations) {
          const row = document.createElement('div');
          row.className = 'dropdown-row';
          
          const itemCell = document.createElement('div');
          itemCell.textContent = 'HC Variation';
          
          const dateCell = document.createElement('div');
          dateCell.textContent = formatDropdownDate(variation.variation_date) || '-';
          
          const notesCell = document.createElement('div');
          notesCell.textContent = variation.notes || '-';
          
          const amountCell = document.createElement('div');
          const amount = parseFloat(variation.amount || 0);
          amountCell.textContent = '$' + amount.toLocaleString('en-US', {
            minimumFractionDigits: 2, 
            maximumFractionDigits: 2 
          });
          
          row.appendChild(itemCell);
          row.appendChild(dateCell);
          row.appendChild(notesCell);
          row.appendChild(amountCell);
          
          dropdownBody.appendChild(row);
        }
      }
    }
    
    return;
  }
  
  // Standard dropdown for other types
  let headerText = 'Inv #';
  
  // For working and committed types, show 'Quo/Inv #'
  if (type === 'working' || type === 'committed') {
    headerText = 'Quo/Inv #';
  }
  
  dropdown.innerHTML = `
    <div class="dropdown-header">
      <div><strong>Supplier</strong></div>
      <div><strong>Date</strong></div>
      <div><strong>${headerText}</strong></div>
      <div><strong>$</strong></div>
    </div>
  `;
  if (type === 'invoiced' || type === 'committed' || type === 'working') {
    try {
      var dropdownData;
      try {
        dropdownData = JSON.parse(base_table_dropdowns_json);
      } catch (parseError) {
        // Provide empty object as fallback
        dropdownData = {};
      }
      
      var costingData = dropdownData[costingPk];
      
      if (type === 'committed' || type === 'working') {
        // Add Quotes section header
        var quotesHeader = document.createElement('div');
        quotesHeader.className = 'dropdown-row dropdown-section-header';
        quotesHeader.innerHTML = '<div><strong>Quotes</strong></div><div></div><div></div><div></div>';
        dropdown.appendChild(quotesHeader);
        
        // Add quote data if exists
        if (costingData.committed && Array.isArray(costingData.committed)) {
          costingData.committed.forEach(function(quote) {
            var quoteRow = document.createElement('div');
            quoteRow.className = 'dropdown-row';
            
            // Special handling for Internal_Margin_Quote entries (contract budget)
            var supplierName = quote.supplier;
            var quoteNum = quote.quote_num;
            
            // If this is the Internal_Margin_Quote entry, display it as 'Contract Budget'
            if (quoteNum === 'Internal_Margin_Quote' || (supplierName === 'Unknown' && quoteNum === 'Internal_Margin_Quote')) {
              supplierName = 'Contract Budget';
              quoteNum = '';
            }
            // For all other entries with Margin as supplier name
            else if (supplierName === 'Margin' && quote.supplier_original) {
              supplierName = quote.supplier_original;
            }
            
            quoteRow.innerHTML = `
              <div>${supplierName || '-'}</div>
              <div>${formatDropdownContextDate(quote.date) || '-'}</div>
              <div>${quoteNum || ''}</div>
              <div>$${parseFloat(quote.amount || 0).toLocaleString('en-US', {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2
              })}</div>
            `;
            dropdown.appendChild(quoteRow);
          });
        }
        
        // Add Direct Costs section header
        var directCostsHeader = document.createElement('div');
        directCostsHeader.className = 'dropdown-row dropdown-section-header';
        directCostsHeader.innerHTML = '<div><strong>Invoices - Direct Costs</strong></div><div></div><div></div><div></div>';
        dropdown.appendChild(directCostsHeader);
        
        // Add direct costs data
        if (costingData.invoiced_direct && Array.isArray(costingData.invoiced_direct)) {
          costingData.invoiced_direct.forEach(function(invoice) {
            var row = document.createElement('div');
            row.className = 'dropdown-row';
            
            // Ensure we show the actual supplier name for all categories, including Margin (category_order_in_list = -1)
            // If invoice.supplier is 'Margin', try to use supplier_original if it exists
            var supplierName = invoice.supplier;
            if (supplierName === 'Margin' && invoice.supplier_original) {
              supplierName = invoice.supplier_original;
            }
            
            row.innerHTML = `
              <div>${supplierName || '-'}</div>
              <div>${formatDropdownContextDate(invoice.date)}</div>
              <div>${invoice.invoice_num || '-'}</div>
              <div>$${parseFloat(invoice.amount || 0).toLocaleString('en-US', {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2
              })}</div>
            `;
            dropdown.appendChild(row);
          });
        }

        // Add Uncommitted section for working budget type
        if (type === 'working') {
          var uncommittedHeader = document.createElement('div');
          uncommittedHeader.className = 'dropdown-row dropdown-section-header';
          uncommittedHeader.innerHTML = '<div><strong>Uncommitted</strong></div><div></div><div></div><div></div>';
          dropdown.appendChild(uncommittedHeader);
          
          var uncommittedRow = document.createElement('div');
          uncommittedRow.className = 'dropdown-row';
          var uncommittedCell = cell.closest('tr').querySelector('td:nth-child(5)');
          var uncommittedAmount = uncommittedCell.textContent.trim();
          uncommittedRow.innerHTML = `
            <div>Uncommitted Amount</div>
            <div>-</div>
            <div>-</div>
            <div>${uncommittedAmount}</div>
          `;
          dropdown.appendChild(uncommittedRow);
        }
      } else { // type === 'invoiced'
        const data = costingData.invoiced_all;
        if (data && Array.isArray(data)) {
          data.forEach(function(invoice) {
            var row = document.createElement('div');
            row.className = 'dropdown-row';
            row.innerHTML = `
              <div>${invoice.supplier || '-'}</div>
              <div>${formatDropdownContextDate(invoice.date)}</div>
              <div>${invoice.invoice_num || '-'}</div>
              <div>$${parseFloat(invoice.amount || 0).toLocaleString('en-US', {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2
              })}</div>
            `;
            dropdown.appendChild(row);
          });
        }
      }
    } catch (error) {
      console.error("Error processing invoiced dropdown data:", error);
    }
  } else { // working type
    try {
      var dropdownData = JSON.parse(base_table_dropdowns_json);
      var costingData = dropdownData[costingPk];
      
      // Add Quotes section header
      var quotesHeader = document.createElement('div');
      quotesHeader.className = 'dropdown-row dropdown-section-header';
      quotesHeader.innerHTML = '<div>Quotes</div><div></div><div></div><div></div>';
      dropdown.appendChild(quotesHeader);
      
      // Add quote data if exists
      if (costingData.committed && costingData.committed.supplier) {
        var quoteRow = document.createElement('div');
        quoteRow.className = 'dropdown-row';
        quoteRow.innerHTML = `
          <div>${costingData.committed.supplier || '-'}</div>
          <div>-</div>
          <div>${costingData.committed.quote_num || '-'}</div>
          <div>$${parseFloat(costingData.committed.amount || 0).toLocaleString('en-US', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
          })}</div>
        `;
        dropdown.appendChild(quoteRow);
      }
      
      // Add Direct Costs section header
      var directCostsHeader = document.createElement('div');
      directCostsHeader.className = 'dropdown-row dropdown-section-header';
      directCostsHeader.innerHTML = '<div>Invoices - Direct Costs</div><div></div><div></div><div></div>';
      dropdown.appendChild(directCostsHeader);
      
      // Add direct costs data
      if (costingData.invoiced_direct && Array.isArray(costingData.invoiced_direct)) {
        costingData.invoiced_direct.forEach(function(invoice) {
          var row = document.createElement('div');
          row.className = 'dropdown-row';
          row.innerHTML = `
            <div>${invoice.supplier || '-'}</div>
            <div>${formatDropdownContextDate(invoice.date)}</div>
            <div>${invoice.invoice_num || '-'}</div>
            <div>$${parseFloat(invoice.amount || 0).toLocaleString('en-US', {
              minimumFractionDigits: 2,
              maximumFractionDigits: 2
            })}</div>
          `;
          dropdown.appendChild(row);
        });
      }

      // Add Uncommitted section header
      var uncommittedHeader = document.createElement('div');
      uncommittedHeader.className = 'dropdown-row dropdown-section-header';
      uncommittedHeader.innerHTML = '<div><strong>Uncommitted</strong></div><div></div><div></div><div></div>';
      dropdown.appendChild(uncommittedHeader);
      
      // Add uncommitted amount
      var uncommittedRow = document.createElement('div');
      uncommittedRow.className = 'dropdown-row';
      var uncommittedCell = cell.closest('tr').querySelector('td:nth-child(5)');
      var uncommittedAmount = uncommittedCell.textContent.trim();
      uncommittedRow.innerHTML = `
        <div>Uncommitted Amount</div>
        <div>-</div>
        <div>-</div>
        <div>$${uncommittedAmount}</div>
      `;
      dropdown.appendChild(uncommittedRow);
    } catch (error) {
      console.error("Error processing working dropdown data:", error);
    }
  }
  // First display the dropdown so we can measure it
  dropdown.style.display = 'block';
  dropdown.style.visibility = 'hidden'; // Hide it while measuring

  // Get measurements after content is populated
  var cellRect = cell.getBoundingClientRect();
  var dropdownRect = dropdown.getBoundingClientRect();
  var viewportWidth = window.innerWidth;
  const borderWidth = 2;

  // Get table measurements
  var table = cell.closest('table');
  var tableRect = table.getBoundingClientRect();
  var tableBottom = tableRect.bottom;

  // Reset positioning
  dropdown.style.left = '';
  dropdown.style.right = '';
  dropdown.style.top = '';
  dropdown.style.bottom = '';

  // Handle vertical positioning
  if (cellRect.bottom + dropdownRect.height > tableBottom) {
    // Position from bottom of row if it would go below table bottom
    dropdown.style.bottom = (cellRect.height + borderWidth) + 'px';
    dropdown.style.top = 'auto';
  } else {
    // Position from top of row
    dropdown.style.top = (cellRect.height - borderWidth) + 'px';
    dropdown.style.bottom = 'auto';
  }

  // Handle horizontal positioning
  if (cellRect.left + dropdownRect.width > viewportWidth) {
    // Position from right edge if it would go beyond viewport
    dropdown.style.right = borderWidth + 'px';
    dropdown.style.left = 'auto';
  } else {
    // Position from left edge
    dropdown.style.left = -borderWidth + 'px';
    dropdown.style.right = 'auto';
  }

  // Make the dropdown visible again
  dropdown.style.visibility = 'visible';
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
