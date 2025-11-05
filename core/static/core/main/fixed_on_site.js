// Function to deal with thousands separator
function toFixedWithoutComma(num, fixed) {
  var re = new RegExp('^-?\\d+(?:\.\\d{0,' + (fixed || -1) + '})?');
  return num.toString().match(re)[0];
}

// Event handler for the toggle percentage button
$('button[id^="fosPctFixedBtn"]').click(function() {
  console.log("Toggle Percentage Button Clicked");
  var id = this.id.replace('fosPctFixedBtn', '');
  var contractBudget = parseFloat($('#contractBudget' + id).text().replace(/,/g, ''));
  var $fixedOnSiteInput = $('#newFixedOnSite' + id);
  var $fixedOnSiteHeader = $('#newFixedOnSiteHeader' + id); // Assuming you have an id for the header
  var currentText = $fixedOnSiteInput.val();
  if ($fixedOnSiteHeader.text().includes('%')) {
    // If the header text is a percentage, switch back to the number view
    var fixedOnSitePct = Number($fixedOnSiteInput.data('percentage')); // Retrieve the 10 decimal places number
    var fixedOnSite = toFixedWithoutComma(fixedOnSitePct / 100 * contractBudget, 2);
    $fixedOnSiteInput.val(fixedOnSite.replace(/,/g, '')); // Remove commas before setting the value
    $fixedOnSiteHeader.text('New Fixed on Site ($)');
  } else {
    // If the header text is a number, switch to the percentage view
    var fixedOnSite = Number(currentText.replace(/,/g, '')); // Remove commas before using the value
    if (contractBudget == 0) {
      $fixedOnSiteInput.val('0');
    } else {
      var percentage = (fixedOnSite / contractBudget * 100);
      $fixedOnSiteInput.val(percentage.toFixed(3)); // Display 3 decimal places
      $fixedOnSiteInput.data('percentage', percentage.toFixed(10)); // Store 10 decimal places
    }
    $fixedOnSiteHeader.text('New Fixed on Site (%)');
  }
});

// Event handler for the input change
$('input[id^="newFixedOnSite"]').change(function() {
  var id = this.id.replace('newFixedOnSite', '');
  var $fixedOnSiteInput = $(this);
  var $fixedOnSiteHeader = $('#newFixedOnSiteHeader' + id); // Assuming you have an id for the header
  var contractBudget = parseFloat($('#contractBudget' + id).text().replace(/,/g, ''));
  var inputValue = parseFloat($fixedOnSiteInput.val().replace(/,/g, ''));
  
  if (inputValue < 0) {
    alert("Input cannot be negative");
    $fixedOnSiteInput.val('0');
  } else if ($fixedOnSiteHeader.text().includes('%')) {
    // If the header text is a percentage, update the stored percentage value
    if (inputValue > 100) {
      alert("Input cannot be greater than 100%");
      $fixedOnSiteInput.val('100');
    } else {
      var percentage = Number($fixedOnSiteInput.val());
      $fixedOnSiteInput.data('percentage', percentage.toFixed(10)); // Store 10 decimal places
    }
  } else {
    if (inputValue > contractBudget) {
      alert("Input cannot be greater than the contract budget");
      $fixedOnSiteInput.val(contractBudget);
    }
  }
});

// Event handler for the modal trigger
$(document).on('click', '.modal-trigger', function(){
  var costingId = $(this).data('id');
  var costingItem = $(this).data('item');
  var fixedOnSite = $(this).data('fixed-on-site');
  var contractBudget = $(this).data('contract-budget');
  var hcClaimed = hc_claim_lines_sums[costingId] || 0;
  showCosModal(costingId, costingItem, fixedOnSite, contractBudget, hcClaimed);
});

function updateFixedOnSite(costingPk, fixedOnSiteInputId) {
  var $fixedOnSiteInput = $('#' + fixedOnSiteInputId);
  var $fixedOnSiteHeader = $('#newFixedOnSiteHeader' + fixedOnSiteInputId.replace('newFixedOnSite', '')); // Assuming you have an id for the header
  var fixedOnSite;
  if ($fixedOnSiteHeader.text().includes('%')) {
    // If the header text is a percentage, convert to fixed
    var contractBudget = parseFloat($('#contractBudget' + fixedOnSiteInputId.replace('newFixedOnSite', '')).text().replace(/,/g, ''));
    var fixedOnSitePct = Number($fixedOnSiteInput.data('percentage')); // Retrieve the 10 decimal places number
    fixedOnSite = (fixedOnSitePct / 100 * contractBudget).toFixed(2);
  } else {
    // Else if number, use the current value
    fixedOnSite = $fixedOnSiteInput.val().replace(/,/g, ''); // Remove commas before using the value
  }
  $.ajax({
    url: '/update_fixedonsite/', // Assuming the URL of the server function is '/update_fixedonsite/'
    type: 'POST',
    data: JSON.stringify({
      'costing_pk': costingPk,
      'fixed_on_site': fixedOnSite
    }),
    contentType: 'application/json',
    success: function(response) {
      if (response.status === 'success') {
        console.log('Fixed on site updated successfully');
        location.reload();
      } else {
        console.log('Failed to update fixed on site');
      }
    }
  });
}

document.querySelectorAll('.save-fixed-costs').forEach(function(button) {
  button.addEventListener('click', function() {
    var costingPk = this.getAttribute('data-id');
    var fixedOnSiteInputId = 'newFixedOnSite' + costingPk;
    updateFixedOnSite(costingPk, fixedOnSiteInputId);
  });
});
