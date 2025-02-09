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
  console.log("Formatted date:", formatted);
  return formatted;
}

window.onload = function() {
  document.querySelectorAll('tr[data-toggle="collapse"]').forEach(row => row.click());
};

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
      sumCommitted = 0, sumFixedOnSite = 0, sumInvoiced = 0;
  $('.group' + groupNumber).each(function () {
    var contractBudget = $(this).find('td').eq(2).text().replace(/,/g, '').trim();
    var workingBudget = $(this).find('td').eq(3).find('.working-budget-value').text().replace(/,/g, '').trim();
    var uncommitted = $(this).find('td').eq(4).text().replace(/,/g, '').trim();
    var committed = $(this).find('td').eq(5).text().replace(/,/g, '').trim();
    var fixedOnSite = $(this).find('td').eq(7).text().replace(/,/g, '').trim();
    var invoicedText = $(this).find('td').eq(6).find('.invoiced-value').text().trim();
    var invoiced = invoicedText.replace(/[^0-9.-]+/g, '');
    contractBudget = (contractBudget === '-' || contractBudget === '') ? 0 : parseFloat(contractBudget);
    workingBudget = (workingBudget === '-' || workingBudget === '') ? 0 : parseFloat(workingBudget);
    uncommitted = (uncommitted === '-' || uncommitted === '') ? 0 : parseFloat(uncommitted);
    committed = (committed === '-' || committed === '') ? 0 : parseFloat(committed);
    fixedOnSite = (fixedOnSite === '-' || fixedOnSite === '') ? 0 : parseFloat(fixedOnSite);
    invoiced = (invoiced === '-' || invoiced === '') ? 0 : parseFloat(invoiced || '0');
    sumContractBudget += contractBudget;
    sumWorkingBudget += workingBudget;
    sumUncommitted += uncommitted;
    sumCommitted += committed;
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
      invoicedCell = row.find('td').eq(6),
      fixedOnSiteCell = row.find('td').eq(7);
  if ($(this).hasClass('collapsed')) {
    contractBudgetCell.data('original', contractBudgetCell.html());
    workingBudgetCell.data('original', workingBudgetCell.html());
    uncommittedCell.data('original', uncommittedCell.html());
    committedCell.data('original', committedCell.html());
    fixedOnSiteCell.data('original', fixedOnSiteCell.html());
    invoicedCell.data('original', invoicedCell.html());
    contractBudgetCell.html(sumContractBudget.toFixed(2) == 0.00 ? '-' : '<strong>' + formatNumber(sumContractBudget.toFixed(2)) + '</strong>');
    workingBudgetCell.html(sumWorkingBudget.toFixed(2) == 0.00 ? '-' : '<strong>' + formatNumber(sumWorkingBudget.toFixed(2)) + '</strong>');
    uncommittedCell.html(sumUncommitted.toFixed(2) == 0.00 ? '-' : '<strong>' + formatNumber(sumUncommitted.toFixed(2)) + '</strong>');
    committedCell.html(sumCommitted.toFixed(2) == 0.00 ? '-' : '<strong>' + formatNumber(sumCommitted.toFixed(2)) + '</strong>');
    fixedOnSiteCell.html(sumFixedOnSite.toFixed(2) == 0.00 ? '-' : '<strong>' + formatNumber(sumFixedOnSite.toFixed(2)) + '</strong>');
    invoicedCell.html(sumInvoiced.toFixed(2) == 0.00 ? '-' : '<strong>' + formatNumber(sumInvoiced.toFixed(2)) + '</strong>');
  } else {
    contractBudgetCell.html(contractBudgetCell.data('original'));
    workingBudgetCell.html(workingBudgetCell.data('original'));
    uncommittedCell.html(uncommittedCell.data('original'));
    committedCell.html(committedCell.data('original'));
    fixedOnSiteCell.html(fixedOnSiteCell.data('original'));
    invoicedCell.html(invoicedCell.data('original'));
  }
});

function toggleDropdown(cell, costingPk, type) {
  type = type || 'invoiced';
  var idPrefix = type === 'invoiced' ? 'dropdown-' : (type === 'committed' ? 'committed-dropdown-' : 'working-dropdown-');
  var dropdown = document.getElementById(idPrefix + costingPk);
  if (!dropdown) {
    console.error("Dropdown element not found for", type, "with costingPk:", costingPk);
    return;
  }
  var cellStyle = window.getComputedStyle(cell);
  var allDropdowns = document.querySelectorAll('.dropdown-content');
  allDropdowns.forEach(function(el) {
    if (el !== dropdown) {
      el.style.display = 'none';
    }
  });
  if (dropdown.style.display === 'block') {
    dropdown.style.display = 'none';
    return;
  } else {
    dropdown.style.display = 'block';
  }
  dropdown.innerHTML = dropdown.querySelector('.dropdown-header').outerHTML;
  if (type === 'invoiced' || type === 'committed') {
    try {
      var dropdownData = JSON.parse(base_table_dropdowns_json);
      var costingData = dropdownData[costingPk];
      const data = type === 'invoiced' ? costingData.invoiced_all : costingData.invoiced_direct;
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
      } else {
      }
    } catch (error) {
      console.error("Error processing invoiced dropdown data:", error);
    }
  } else {
  }
  var cellRect = cell.getBoundingClientRect();
  var dropdownRect = dropdown.getBoundingClientRect();
  var viewportWidth = window.innerWidth;
  dropdown.style.left = '';
  dropdown.style.right = '';
  if (cellRect.left + dropdownRect.width > viewportWidth) {
    dropdown.style.right = '0';
    dropdown.style.left = 'auto';
  } else {
    dropdown.style.left = '0';
    dropdown.style.right = 'auto';
  }
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
