// Function to create and show the modal
function showCosModal(costingId, costingItem, completeOnSite, contractBudget, hcClaimed) {
    var modalHtml = `
    <div class="modal fade" id="cosModal" tabindex="-1" role="dialog" aria-labelledby="editModalLabel${costingId}" aria-hidden="true">
        <div class="modal-dialog" role="document">
            <div class="modal-content" style="border: 3px solid black;">
                <div class="modal-header" style="text-align: center; background: linear-gradient(45deg, #A090D0 0%, #B3E1DD 100%);">
                    <h5 class="modal-title">${costingItem} - Complete On Site</h5>
                    <p class="working-budget"></p>
                    <button type="button" class="close" data-dismiss="modal" aria-label="Close">
                        <span aria-hidden="true">&times;</span>
                    </button>
                </div>
                <div class="modal-body">
                    <table>
                        <tr>
                            <th>Contract Budget</th>
                            <th>HC Already Claimed</th>
                            <th>Current Value</th>
                            <th>New Value</th>
                        </tr>
                        <tr>
                            <td>${Number(contractBudget).toLocaleString()}</td>
                            <td>${Number(hcClaimed).toLocaleString('en', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
                            <td class="original-complete-on-site">${Number(completeOnSite).toLocaleString()}</td>                  
                            <td>
                                <input type="number" id="completeOnSiteInput" step="0.01" value="0.00" style="width: 100%; box-sizing: border-box;">
                                <input type="text" id="completeOnSiteInputPct" style="width: 100%; box-sizing: border-box; display: none;">
                          </td>
                        </tr>
                    </table>
                </div>
                <div class="modal-footer justify-content-between">
                    <button type="button" class="btn btn-primary" id="cosPctFixedBtn">Toggle Percentage</button>
                <div>
                  <button type="button" class="btn btn-secondary" data-dismiss="modal">Cancel</button>
                  <button type="button" class="btn btn-primary update-completed-values" id="saveButton">Save</button>
                </div>
              </div>
            </div>
        </div>
    </div>
  `;
  
    // Append the modal to the body
    $('body').append(modalHtml);
  
    // Show the modal
    $('#cosModal').modal('show');
  
    // Remove the modal when it's hidden
    $('#cosModal').on('hidden.bs.modal', function () {
      $(this).remove();
    });

    // Event handler for the save button
    $('#saveButton').click(function() {
    console.log("Save Button Clicked");
    var completeOnSiteInput = parseFloat($('#completeOnSiteInput').val());
    if (completeOnSiteInput > contractBudget) {
      alert("New Complete on Site value cannot be greater than Contract Budget");
      return;
    }
    if (completeOnSiteInput < completeOnSite) {
      alert("New Complete on Site value cannot be less than total already claimed");
      return;
    }
    updateCompleteOnSite(costingId, completeOnSiteInput);
});

// Event handler for the toggle percentage button
$('#cosPctFixedBtn').click(function() {
    var $completeOnSiteCell = $('.original-complete-on-site');
    var $completeOnSiteInput = $('#completeOnSiteInput');
    var $completeOnSiteInputPct = $('#completeOnSiteInputPct');
    var currentText = $completeOnSiteCell.text();
    if (currentText.includes('%')) {
      // If the current text is a percentage, switch back to the number view
      var completeOnSitePct = Number($completeOnSiteInputPct.val().replace('%', ''));
      var completeOnSite = completeOnSitePct / 100 * contractBudget;
      $completeOnSiteCell.text(completeOnSite.toLocaleString());
      $completeOnSiteInput.val(completeOnSite);
      $completeOnSiteInput.show();
      $completeOnSiteInputPct.hide();
    } else {
      // If the current text is a number, switch to the percentage view
      var completeOnSite = Number($completeOnSiteInput.val());
      if (contractBudget == 0) {
        $completeOnSiteCell.text('-%');
        $completeOnSiteInputPct.val('-%');
      } else {
        var percentage = (completeOnSite / contractBudget * 100).toFixed(2);
        $completeOnSiteCell.text(percentage + '%');
        var inputPercentage = ($completeOnSiteInput.val() / contractBudget * 100).toFixed(2);
        $completeOnSiteInputPct.val(inputPercentage + '%');
      }
      $completeOnSiteInput.hide();
      $completeOnSiteInputPct.show();
    }
  });
  }
  
  // Event handler for the modal trigger
  $(document).on('click', '.modal-trigger', function(){
    var costingId = $(this).data('id');
    var costingItem = $(this).data('item');
    var completeOnSite = $(this).data('complete-on-site');
    var contractBudget = $(this).data('contract-budget');
    var hcClaimed = hc_claim_lines_sums[costingId] || 0;
    showCosModal(costingId, costingItem, completeOnSite, contractBudget, hcClaimed);
});

function updateCompleteOnSite(costingId, completeOnSite) {
    console.log("Starting POST function");
    $.ajax({
        url: '/update_complete_on_site/',  // Update this to the correct URL
        type: 'POST',
        data: JSON.stringify({
        id: costingId,
        complete_on_site: completeOnSite
        }),
        contentType: 'application/json',
        success: function(response) {
        // Handle the response from the server
        if (response.status === 'success') {
            alert('Data saved successfully');
            $('#cosModal').modal('hide');  // Close the modal
            location.reload();
        } else {
            alert('Error: ' + response.message);
        }
        },
        error: function(error) {
        // Handle any errors
        alert('Error: ' + error.statusText);
        }
    });
}

