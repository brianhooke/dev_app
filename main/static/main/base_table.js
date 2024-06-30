window.onload = function() {
  document.querySelectorAll('tr[data-toggle="collapse"]').forEach((row) => {
  row.click();
  });
};

document.querySelectorAll('.save-costs').forEach(function(button) {
    button.addEventListener('click', function() {
      var costing_pk = this.getAttribute('data-id');
      console.log("costing ID is: "+costing_pk);
      var uncommitted = document.getElementById('uncommittedInput' + costing_pk).value;
      if (!costing_pk || !uncommitted) {
          alert('Costing ID or uncommitted value is missing');
          return;
      }
      var uncommitted_notes = document.getElementById('uncommittedNotes' + costing_pk).value;
      var data = { 'costing_pk': costing_pk, 'uncommitted': uncommitted };
        console.log(data);
        if (!data) return;
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
        });
    });
});

$('[data-toggle="collapse"]').on('click', function () {
  console.log("clicked");
  $(this).toggleClass('collapsed');

  // Get the group number
  var groupNumber = $(this).data('target').replace('.group', '');

  // Initialize the sums
  var sumContractBudget = 0;
  var sumWorkingBudget = 0;
  var sumUncommitted = 0;
  var sumCommitted = 0;
  var sumInvoiced = 0;
  var sumPaid = 0;

  // Calculate the sums
  $('.group' + groupNumber).each(function () {
    var contractBudget = $(this).find('td').eq(2).text().replace(',', '').trim();
    var workingBudget = $(this).find('td').eq(3).text().replace(',', '').trim();
    var uncommitted = $(this).find('td').eq(4).text().replace(',', '').trim();
    var committed = $(this).find('td').eq(5).text().replace(',', '').trim();
    var invoiced = $(this).find('td').eq(6).text().replace(',', '').trim();
    var paid = $(this).find('td').eq(7).text().replace(',', '').trim();

    // Check if the text is '-' and, if so, treat it as 0
    contractBudget = contractBudget === '-' ? 0 : contractBudget;
    workingBudget = workingBudget === '-' ? 0 : workingBudget;
    uncommitted = uncommitted === '-' ? 0 : uncommitted;
    committed = committed === '-' ? 0 : committed;
    invoiced = invoiced === '-' ? 0 : invoiced;
    paid = paid === '-' ? 0 : paid;

    sumContractBudget += parseFloat(contractBudget);
    sumWorkingBudget += parseFloat(workingBudget);
    sumUncommitted += parseFloat(uncommitted);
    sumCommitted += parseFloat(committed);
    sumInvoiced += parseFloat(invoiced);
    sumPaid += parseFloat(paid);
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
  var paidCell = row.find('td').eq(7);

  if ($(this).hasClass('collapsed')) {
    // Store the original values
    contractBudgetCell.data('original', contractBudgetCell.html());
    workingBudgetCell.data('original', workingBudgetCell.html());
    uncommittedCell.data('original', uncommittedCell.html());
    committedCell.data('original', committedCell.html());
    invoicedCell.data('original', invoicedCell.html());
    paidCell.data('original', paidCell.html());

    // Display the sums
    contractBudgetCell.html((sumContractBudget.toFixed(2) == 0.00 ? '-' : '<strong>' + formatNumber(sumContractBudget.toFixed(2)) + '</strong>'));
    workingBudgetCell.html((sumWorkingBudget.toFixed(2) == 0.00 ? '-' : '<strong>' + formatNumber(sumWorkingBudget.toFixed(2)) + '</strong>'));
    uncommittedCell.html((sumUncommitted.toFixed(2) == 0.00 ? '-' : '<strong>' + formatNumber(sumUncommitted.toFixed(2)) + '</strong>'));
    committedCell.html((sumCommitted.toFixed(2) == 0.00 ? '-' : '<strong>' + formatNumber(sumCommitted.toFixed(2)) + '</strong>'));
    invoicedCell.html((sumInvoiced.toFixed(2) == 0.00 ? '-' : '<strong>' + formatNumber(sumInvoiced.toFixed(2)) + '</strong>'));
    paidCell.html((sumPaid.toFixed(2) == 0.00 ? '-' : '<strong>' + formatNumber(sumPaid.toFixed(2)) + '</strong>'));
  } else {
    // Restore the original values
    contractBudgetCell.html(contractBudgetCell.data('original'));
    workingBudgetCell.html(workingBudgetCell.data('original'));
    uncommittedCell.html(uncommittedCell.data('original'));
    committedCell.html(committedCell.data('original'));
    invoicedCell.html(invoicedCell.data('original'));
    paidCell.html(paidCell.data('original'));
  }
});
