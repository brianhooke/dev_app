window.onload = function() {
  document.querySelectorAll('tr[data-toggle="collapse"]').forEach((row) => {
  row.click();
  });
};



document.querySelectorAll('.save-costs').forEach(function(button) {
  button.addEventListener('click', function() {
      var costing_pk = this.getAttribute('data-id');
      // Get the uncommitted value
      var uncommitted = document.getElementById('uncommittedInput' + costing_pk).value;
      // Get the notes value (including line breaks)
      var notes = document.getElementById('notesInput' + costing_pk).value;
      if (!costing_pk || !uncommitted) {
          alert('Costing ID or uncommitted value is missing');
          return;
      }
      // Prepare data object, now including 'notes'
      var data = { 
          'costing_pk': costing_pk, 
          'uncommitted': uncommitted,
          'notes': notes // Add notes to the data
      };
      if (!data) return;
      // Fetch API to send the data to the server
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

  // Get the group number
  var groupNumber = $(this).data('target').replace('.group', '');

  // Initialize the sums
  var sumContractBudget = 0;
  var sumWorkingBudget = 0;
  var sumUncommitted = 0;
  var sumCommitted = 0;
  var sumFixedOnSite = 0;
  var sumInvoiced = 0;

  // Calculate the sums
  $('.group' + groupNumber).each(function () {
    var contractBudget = $(this).find('td').eq(2).text().replace(/,/g, '').trim();
    var workingBudget = $(this).find('td').eq(3).text().replace(/,/g, '').trim();
    var uncommitted = $(this).find('td').eq(4).text().replace(/,/g, '').trim();
    var committed = $(this).find('td').eq(5).text().replace(/,/g, '').trim();
    var fixedOnSite = $(this).find('td').eq(7).text().replace(/,/g, '').trim();
    var invoicedText = $(this).find('td').eq(6).find('.invoiced-value').text().trim();
    // Extract only the numeric part from the text, removing currency symbols and commas
    var invoiced = invoicedText.replace(/[^0-9.-]+/g, '');

    // Check if the text is '-' and, if so, treat it as 0
    contractBudget = contractBudget === '-' || contractBudget === '' ? 0 : parseFloat(contractBudget);
    workingBudget = workingBudget === '-' || workingBudget === '' ? 0 : parseFloat(workingBudget);
    uncommitted = uncommitted === '-' || uncommitted === '' ? 0 : parseFloat(uncommitted);
    committed = committed === '-' || committed === '' ? 0 : parseFloat(committed);
    fixedOnSite = fixedOnSite === '-' || fixedOnSite === '' ? 0 : parseFloat(fixedOnSite);
    invoiced = invoiced === '-' || invoiced === '' ? 0 : parseFloat(invoiced || '0');


    sumContractBudget += parseFloat(contractBudget);
    sumWorkingBudget += parseFloat(workingBudget);
    sumUncommitted += parseFloat(uncommitted);
    sumCommitted += parseFloat(committed);
    sumFixedOnSite += parseFloat(fixedOnSite);
    sumInvoiced += parseFloat(invoiced);
  });

  // Helper function to format numbers with thousand comma separator
  function formatNumber(num) {
    return num.toString().replace(/(\d)(?=(\d{3})+(?!\d))/g, '$1,')
  }

  // Display the sums
  var row = $(this).closest('tr');
  var contractBudgetCell = row.find('td').eq(2);
  var workingBudgetCell = row.find('td').eq(3);
  var uncommittedCell = row.find('td').eq(4);
  var committedCell = row.find('td').eq(5);
  var invoicedCell = row.find('td').eq(6);
  var fixedOnSiteCell = row.find('td').eq(7);

  if ($(this).hasClass('collapsed')) {
    // Store the original values
    contractBudgetCell.data('original', contractBudgetCell.html());
    workingBudgetCell.data('original', workingBudgetCell.html());
    uncommittedCell.data('original', uncommittedCell.html());
    committedCell.data('original', committedCell.html());
    fixedOnSiteCell.data('original', fixedOnSiteCell.html());
    invoicedCell.data('original', invoicedCell.html());

    // Display the sums
    contractBudgetCell.html((sumContractBudget.toFixed(2) == 0.00 ? '-' : '<strong>' + formatNumber(sumContractBudget.toFixed(2)) + '</strong>'));
    workingBudgetCell.html((sumWorkingBudget.toFixed(2) == 0.00 ? '-' : '<strong>' + formatNumber(sumWorkingBudget.toFixed(2)) + '</strong>'));
    uncommittedCell.html((sumUncommitted.toFixed(2) == 0.00 ? '-' : '<strong>' + formatNumber(sumUncommitted.toFixed(2)) + '</strong>'));
    committedCell.html((sumCommitted.toFixed(2) == 0.00 ? '-' : '<strong>' + formatNumber(sumCommitted.toFixed(2)) + '</strong>'));
    fixedOnSiteCell.html((sumFixedOnSite.toFixed(2) == 0.00 ? '-' : '<strong>' + formatNumber(sumFixedOnSite.toFixed(2)) + '</strong>'));
    invoicedCell.html((sumInvoiced.toFixed(2) == 0.00 ? '-' : '<strong>' + formatNumber(sumInvoiced.toFixed(2)) + '</strong>'));
  } else {
    // Restore the original values
    contractBudgetCell.html(contractBudgetCell.data('original'));
    workingBudgetCell.html(workingBudgetCell.data('original'));
    uncommittedCell.html(uncommittedCell.data('original'));
    committedCell.html(committedCell.data('original'));
    fixedOnSiteCell.html(fixedOnSiteCell.data('original'));
    invoicedCell.html(invoicedCell.data('original'));
  }
});


function toggleInvoicedDropdown(cell, costingPk) {
    var dropdown = document.getElementById('dropdown-' + costingPk);

    // Hide any other open dropdowns
    document.querySelectorAll('.dropdown-content').forEach(function(content) {
        if (content !== dropdown) {
            content.style.display = 'none';
        }
    });

    // Toggle this dropdown
    if (dropdown.style.display === 'block') {
        dropdown.style.display = 'none';
    } else {
        // First display it to get its dimensions
        dropdown.style.display = 'block';

        // Clear any existing rows
        var existingRows = dropdown.querySelectorAll('.dropdown-row');
        existingRows.forEach(row => row.remove());

        // Get the data for this costing
        var dropdownData = JSON.parse(base_table_dropdowns_json);
        var costingData = dropdownData[costingPk];

        if (costingData && costingData.invoiced_direct) {
            costingData.invoiced_direct.forEach(function(invoice) {
                var row = document.createElement('div');
                row.className = 'dropdown-row';
                row.innerHTML = `
                    <div>${invoice.supplier || '-'}</div>
                    <div>${invoice.invoice_num || '-'}</div>
                    <div>$${parseFloat(invoice.amount || 0).toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})}</div>
                `;
                dropdown.appendChild(row);
            });
        }

        // Get dimensions and positions
        var cellRect = cell.getBoundingClientRect();
        var dropdownRect = dropdown.getBoundingClientRect();
        var viewportWidth = window.innerWidth;

        // Reset any previous positioning
        dropdown.style.left = '';
        dropdown.style.right = '';

        // Check if dropdown would overflow right side
        if (cellRect.left + dropdownRect.width > viewportWidth) {
            // Position from right edge of cell
            dropdown.style.right = '0';
            dropdown.style.left = 'auto';
        } else {
            // Position from left edge of cell
            dropdown.style.left = '0';
            dropdown.style.right = 'auto';
        }
    }
}
  