// HC Claim Prep Sheet

document.addEventListener('DOMContentLoaded', function() {
    // Initialize contract budgets with variations when modal is shown
    $('#hcPrepSheetModal').on('shown.bs.modal', function() {
        // Update all contract budget cells with variations
        updateAllContractBudgetsWithVariations();
        
        // Recalculate all totals
        calculateTotals();
    });
    

    //////////////////////////////////////////////////////
    // Utility functions (you can put these in a shared .js if desired)
    //////////////////////////////////////////////////////
  
    function getCookie(name) {
      // If you already have a global getCookie, remove this or unify it
      if (!document.cookie) {
        return null;
      }
      const cookies = document.cookie.split(';');
      for (let i = 0; i < cookies.length; i++) {
        const cookie = cookies[i].trim();
        // Does this cookie string begin with name=?
        if (cookie.substring(0, name.length + 1) === (name + '=')) {
          return decodeURIComponent(cookie.substring(name.length + 1));
        }
      }
      return null;
    }

    function colorCurrentCells() {
      $('tr.collapse').each(function() {
          var currentCell = $(this).find('td:nth-child(7)'); // 7th child for 'Current' column
          var fixedOnSite = parseFloat(currentCell.text().replace(/,/g, '').replace('-', '0')) || 0;
          var workingBudget = parseFloat($(this).find('td:nth-child(4)').text().replace(/,/g, '').replace('-', '0')) || 0; // 4th child for 'Working' column
    
          if (workingBudget > 0) {
              var percentage = Math.min((fixedOnSite / workingBudget) * 100, 100);
              if (percentage < 100) {
                  // Use blue from the gradient for less than 100%
                  currentCell.attr('style', 'background: linear-gradient(to right, #bcdcf5 ' + percentage + '%, transparent ' + percentage + '%);');
              } else {
                  // Use green for 100%
                  currentCell.attr('style', 'background: linear-gradient(to right, #BCF5C0 100%, transparent 100%);');
              }
          } else {
              currentCell.attr('style', '');
          }
      });
    }
  
    function formatNumber(num) {
      // 2 decimal places + thousand separators
      return parseFloat(num).toLocaleString('en-US', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
      });
    }
    
    /**
     * Calculate the contract budget with HC variations up to the HC claim date
     * @param {string} costingPk - The costing primary key
     * @param {boolean} [returnDetails=false] - Whether to return details including the variation amount
     * @returns {number|object} - Total budget or object with budget details
     */
    function calculateContractBudgetWithVariationsForHCClaim(costingPk, returnDetails = false) {
      console.log(`============= DETAILED BUDGET CALCULATION FOR COSTING ${costingPk} =============`);
      // Get the original contract budget
      const budgetElement = document.getElementById('hc-contract-budget-' + costingPk);
      if (!budgetElement) {
        console.log(`Budget element not found for costing ${costingPk}`);
        return returnDetails ? { total: 0, original: 0, variations: 0 } : 0;
      }
      
      // Get the original budget
      let originalBudget = 0;
      
      // Try to get the original budget from data-original-budget attribute first
      if (budgetElement.hasAttribute('data-original-budget')) {
        originalBudget = parseFloat(budgetElement.getAttribute('data-original-budget')) || 0;
        console.log(`Original budget from data attribute: ${originalBudget}`);
      } else {
        // If there's no data attribute, we need to be careful - we might be getting a value that already includes variations
        // In this case, let's try to get the original budget from another source if available
        const originalBudgetFromServer = budgetElement.getAttribute('data-server-original-budget');
        if (originalBudgetFromServer) {
          originalBudget = parseFloat(originalBudgetFromServer) || 0;
          console.log(`Original budget from server data: ${originalBudget}`);
        } else {
          // Last resort - use the text content, but be aware it might include variations
          originalBudget = parseFloat(budgetElement.textContent.replace(/,/g, '')) || 0;
          console.log(`WARNING: Using text content for original budget (may include variations): ${originalBudget}`);
          
          // If we have variation data and are using the text content, we need to be really careful
          // The text might already include variations, so we should adjust our calculations
          if (typeof hc_variation_allocations !== 'undefined') {
            const variationsForCosting = hc_variation_allocations.filter(v => 
              v.costing_pk == costingPk && v.variation_pk // Only count real variations with a PK
            );
            
            if (variationsForCosting.length > 0) {
              console.log(`WARNING: Found ${variationsForCosting.length} variations but no original budget attribute.`);
              console.log(`This could lead to double-counting variations.`);
            }
          }
        }
      }
      
      let totalVariations = 0;
      
      // Get the HC claim date from the modal data attribute
      const hcClaimDateStr = $('#hcPrepSheetModal').data('current-hc-claim-date');
      console.log(`HC claim date from modal: ${hcClaimDateStr}`);
      if (!hcClaimDateStr) {
        console.log('No HC claim date found, returning original budget only');
        return returnDetails ? { total: originalBudget, original: originalBudget, variations: 0 } : originalBudget;
      }
      
      const hcClaimDate = new Date(hcClaimDateStr);
      console.log(`Parsed HC claim date: ${hcClaimDate}`);
      
      
      // Find all variation allocations for this costing item up to the HC claim date
      if (typeof hc_variation_allocations !== 'undefined') {
        console.log(`Total hc_variation_allocations available: ${hc_variation_allocations.length}`);
        
        // Log all variations for this costing item
        console.log(`All variations for costing ${costingPk}:`);
        const costingVariations = hc_variation_allocations.filter(v => v.costing_pk == costingPk);
        costingVariations.forEach((v, index) => {
          console.log(`  [${index}] pk: ${v.variation_pk}, amount: ${v.amount}, date: ${v.variation_date}`);
        });
        
        // Check if there's a potential duplicate of the original budget in the variations array
        const potentialDuplicate = costingVariations.find(v => 
          Math.abs(parseFloat(v.amount || 0) - originalBudget) < 0.01 && !v.variation_pk
        );
        
        if (potentialDuplicate) {
          console.log(`WARNING: Found potential duplicate of original budget in variations array: ${JSON.stringify(potentialDuplicate)}`);
          console.log(`Will exclude this entry to avoid double-counting`);
        }
        
        const variations = hc_variation_allocations.filter(v => {
          // Only include variations for this costing item
          if (v.costing_pk != costingPk) return false;
          
          // Skip potential duplicates of the original budget
          if (Math.abs(parseFloat(v.amount || 0) - originalBudget) < 0.01 && !v.variation_pk) {
            console.log(`  Skipping potential duplicate of original budget: amount=${v.amount}`);
            return false;
          }
          
          // Check if variation date is on or before the HC claim date
          const variationDate = new Date(v.variation_date);
          const isIncluded = variationDate <= hcClaimDate;
          console.log(`  Variation ${v.variation_pk}: date=${v.variation_date} <= ${hcClaimDateStr}? ${isIncluded}`);
          return isIncluded;
        });
        
        console.log(`Applicable variations (${variations.length}):`); 
        // Sum up the applicable variation amounts
        for (const variation of variations) {
          const amount = parseFloat(variation.amount || 0);
          console.log(`  Adding variation ${variation.variation_pk}: ${amount}`);
          totalVariations += amount;
        }
      } else {
        console.log('hc_variation_allocations is undefined');
      }
      
      const totalBudget = originalBudget + totalVariations;
      
      // Return either just the total or the detailed object
      console.log(`Budget calculation summary:`);
      console.log(`  Original budget: ${originalBudget}`);
      console.log(`  Total variations: ${totalVariations}`);
      console.log(`  Total budget (original + variations): ${totalBudget}`);
      console.log(`============= END BUDGET CALCULATION =============`);
      
      return returnDetails ? {
        total: totalBudget,
        original: originalBudget,
        variations: totalVariations
      } : totalBudget;
    }
    
    /**
     * Update all contract budget cells in the HC Prep Sheet with variations
     */
    function updateAllContractBudgetsWithVariations() {
      console.log('Updating all contract budgets with variations');
      // Find all rows in the HC prep sheet
      $('table.myTable tbody tr.collapse').each(function() {
        const costingPk = $(this).find('td:eq(1)').data('item-id');
        if (!costingPk) return; // Skip if no costing PK
        
        // Get detailed budget information with variations
        const budgetDetails = calculateContractBudgetWithVariationsForHCClaim(costingPk, true);
        const originalBudget = budgetDetails.original;
        const variations = budgetDetails.variations;
        const totalBudget = budgetDetails.total;
        
        // Get the current value from the cell
        const contractBudgetCell = $('#hc-contract-budget-' + costingPk);
        const currentDisplayValue = parseFloat(contractBudgetCell.text().replace(/,/g, '')) || 0;
        
        console.log(`Costing ${costingPk} budget details:`);
        console.log(`- Original budget: ${originalBudget}`);
        console.log(`- Variations: ${variations}`);
        console.log(`- Total (original + variations): ${totalBudget}`);
        console.log(`- Current display value: ${currentDisplayValue}`);
        
        // Store the original budget as a data attribute
        // This is crucial to prevent double-counting on subsequent updates
        contractBudgetCell.attr('data-original-budget', originalBudget);
        
        // Update the cell content with the total (original + variations)
        contractBudgetCell.text(formatNumber(totalBudget));
        
        // Also store the total as a data attribute for recalculations
        contractBudgetCell.attr('data-including-variations', totalBudget);
        
        if (Math.abs(currentDisplayValue - totalBudget) > 0.01) {
          console.log(`Updated budget for costing ${costingPk}: ${currentDisplayValue} -> ${totalBudget}`);
        }
      });
    }
  
    // A simple "flash" effect for updated table cells
    function flashCell(selector) {
      $(selector).addClass('flash-update');
      setTimeout(function() {
        $(selector).removeClass('flash-update');
      }, 1500);
    }
  
    //////////////////////////////////////////////////////
    // 1) "HC Prep Sheet" modal: when shown => recalc totals
    //////////////////////////////////////////////////////
  
    $('#hcPrepSheetModal').on('shown.bs.modal', function() {
      // Each heading row uses data-toggle="unique-collapse" to group sub-rows
      $('[data-toggle="unique-collapse"]').each(function() {
        var groupNumber = $(this).data('target').replace('.unique-group', '');
        calculateTotals(groupNumber);
        updateArrowDirection($(this));
      });
          // New: Recalculate for each row with an adjustment input on modal open
      $('input[id^="hc-adjustment-"]').each(function() {
        var costingId = this.id.split('-')[2];
        recalcRow(costingId);
    });
    });
  
    // Toggle the arrow direction on expand/collapse
    function updateArrowDirection(element) {
      if (element.hasClass('unique-collapsed')) {
        element.find('.unique-dropdown-arrow').html('&#9654;'); // Right arrow
      } else {
        element.find('.unique-dropdown-arrow').html('&#9660;'); // Down arrow
      }
    }
  
    // Handle clicks on heading rows to expand/collapse subrows
    $('[data-toggle="unique-collapse"]').on('click', function() {
      $(this).toggleClass('unique-collapsed');
      var groupNumber = $(this).data('target').replace('.unique-group', '');
      $('.unique-group' + groupNumber).collapse('toggle');
      updateArrowDirection($(this));
    });
  
    //////////////////////////////////////////////////////
    // 2) Updating "Uncommitted" in sub-modal => /update_uncommitted/
    //////////////////////////////////////////////////////
  
    $('.save-hc-costs').on('click', function(event) {
      event.preventDefault();
      var costingId = $(this).data('id');
      var newUncommittedValue = $('#hc-claim-uncommittedInput' + costingId).val();
      newUncommittedValue = parseFloat(newUncommittedValue) || 0;
    
      $.ajax({
        url: '/update_uncommitted/',
        type: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({
          costing_pk: costingId,
          uncommitted: newUncommittedValue
        }),
        success: function(data) {
          if (data.status === 'success') {
            // Close the sub-modal, re-show main
            $('#hc-claim-editModal' + costingId).modal('hide');
            $('#hcPrepSheetModal').modal('show');
            $('body').addClass('modal-open');
    
            // Update main table cell
            $('#hc-claim-uncommitted-' + costingId + ' a').text(formatNumber(newUncommittedValue));
    
            // Recalc total for that row: uncommitted + committed
            var committedVal = parseFloat($('#hc-claim-committed-' + costingId).text().replace(/,/g, '')) || 0;
            var total = (newUncommittedValue + committedVal).toFixed(2);
            $('#hc-claim-total-' + costingId).text(formatNumber(total));
    
            // Possibly recalc "hc-this-claim" and "qs-this-claim"
            recalcRow(costingId);
    
            flashCell('#hc-claim-uncommitted-' + costingId);
            flashCell('#hc-claim-total-' + costingId);
    
            // Use setTimeout to delay the call until the DOM update is visible
            setTimeout(colorCurrentCells, 100); // Adjust delay if necessary
          }
        },
        error: function(err) {
          console.error('Error saving uncommitted:', err);
        }
      });
    });
    
    $('.save-hc-fixed-costs').on('click', function(event) {
      event.preventDefault();
      var costingId = $(this).data('id');
      var workingBudget = parseFloat($('#hc-claim-contractBudget' + costingId).text().replace(/,/g, '')) || 0;
      var rawVal = $('#hc-claim-newFixedOnSite' + costingId).val();
      var newValue = parseFloat(rawVal.replace(/,/g, '')) || 0;
    
      if (newValue > workingBudget) {
        alert('Cannot enter Fixed on Site values > Working Budget');
        // Optionally, focus back on the input for immediate correction
        $('#hc-claim-newFixedOnSite' + costingId).focus();
        return; // Prevent AJAX call
      }
    
      $.ajax({
        url: '/update_fixedonsite/',
        type: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({
          costing_pk: costingId,
          fixed_on_site: newValue
        }),
        success: function(data) {
          if (data.status === 'success') {
            // Close sub-modal, re-show main
            $('#hc-claim-fixedOnSiteModal' + costingId).modal('hide');
            $('#hcPrepSheetModal').modal('show');
    
            // Update main table cell
            $('#fixed-on-site-display-' + costingId + ' a').text(formatNumber(newValue));
    
            // Possibly recalc difference, "qs-this-claim," etc.
            recalcRow(costingId);
    
            flashCell('#fixed-on-site-display-' + costingId);
    
            // Use setTimeout to delay the call until the DOM update is visible
            setTimeout(colorCurrentCells, 100); // Adjust delay if necessary
          }
        },
        error: function(err) {
          console.error('Error saving fixed on site:', err);
        }
      });
    });
    
    // Handle margin item input changes
    $('#hcPrepSheetModal').on('input', '.margin-item-input', function() {
        const costingId = this.id.split('-')[4]; // Get ID from hc-this-claim-input-{id}
        recalcRow(costingId);
    });

    // Add event listener for real-time validation
    $('#hcPrepSheetModal').on('shown.bs.modal', function() {
      $('input[id^="hc-claim-newFixedOnSite"]').on('input', function() {
        var costingId = this.id.replace('hc-claim-newFixedOnSite', '');
        var workingBudget = parseFloat($('#hc-claim-contractBudget' + costingId).text().replace(/,/g, '')) || 0;
        var inputValue = parseFloat($(this).val().replace(/,/g, '')) || 0;
    
        if (inputValue > workingBudget) {
          $(this).val(workingBudget);
          // Show a temporary message in the modal
          $('#hc-claim-fixedOnSiteModal' + costingId + ' .modal-body').append('<div id="temp-alert" class="alert alert-warning" role="alert">Cannot enter Fixed on Site value > Working Budget</div>');
          setTimeout(function() {
            $('#temp-alert').remove();
          }, 3000); // Remove alert after 3 seconds
        }
      });
    });
  
    //////////////////////////////////////////////////////
    // 4) The "adjustment" input => recalc row
    //////////////////////////////////////////////////////
  
    $('input[id^="hc-adjustment-"]').on('input', function() {
      var costingId = this.id.split('-')[2];
      recalcRow(costingId);
    });
  
    // Helper that re-reads relevant fields for a row and updates "hc-this-claim" + "qs-this-claim"
    function recalcRow(costingId) {
      // Check if this is a margin item by looking for the margin-item-input
      const marginItemInput = $('#hc-this-claim-input-' + costingId);
      const isMarginItem = marginItemInput.length > 0;
      
      // For margin items, apply the constraint: min(This Claim input field, (contract_budget - hc/qsPrevClaimed))
      if (isMarginItem) {
        const marginValue = parseFloat(marginItemInput.val()) || 0;
        const contractBudget = parseFloat($('#hc-contract-budget-' + costingId).text().replace(/,/g, '')) || 0;
        const hcPrevClaimed = parseFloat($('#hc-prev-claimed-' + costingId).text().replace(/,/g, '')) || 0;
        const qsPrevClaimed = parseFloat($('#qs-claimed-' + costingId).text().replace(/,/g, '')) || 0;
        
        // Calculate the maximum allowed values based on remaining budget
        const maxHcValue = Math.max(0, contractBudget - hcPrevClaimed);
        const maxQsValue = Math.max(0, contractBudget - qsPrevClaimed);
        
        // Apply the constraint: min(marginValue, maxValue)
        const hcThisClaimValue = Math.min(marginValue, maxHcValue);
        const qsThisClaimValue = Math.min(marginValue, maxQsValue);
        
        // Set values in the display
        $('#hc-this-claim-' + costingId).text(hcThisClaimValue.toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ","));
        $('#qs-this-claim-' + costingId).text(qsThisClaimValue.toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ","));
        
        // Update any totals that depend on this value
        calculateTotals(marginItemInput.closest('tr').data('group'));
        return;
      }

      // Use the variation-aware contract budget function with details
      const budgetDetails = calculateContractBudgetWithVariationsForHCClaim(costingId, true);
      const contractBudget = budgetDetails.total;
      const X = budgetDetails.variations; // This is the sum of variations <= HC claim date
      let committed = parseFloat($('#hc-claim-committed-' + costingId).text().replace(/,/g, '')) || 0;
      let uncommitted = parseFloat($('#hc-claim-uncommitted-' + costingId + ' a').text().replace(/,/g, '')) || 0;
      let workingBudget = committed + uncommitted;
      let hcPrevInvoiced = parseFloat($('#hc-prev-invoiced-' + costingId).text().replace(/,/g, '')) || 0;
      let c2c = workingBudget - hcPrevInvoiced;
      let hcThisClaimInvoices = parseFloat($('#hc-this-claim-invoices-' + costingId).text().replace(/,/g, '')) || 0;
      let hcPrevClaimed = parseFloat($('#hc-prev-claimed-' + costingId).text().replace(/,/g, '')) || 0;
      let fixedOnSite = parseFloat($('#fixed-on-site-display-' + costingId + ' a').text().replace(/,/g, '')) || 0;
      let qsClaimed = parseFloat($('#qs-claimed-' + costingId).text().replace(/,/g, '')) || 0;
      let adjustment = parseFloat($('#hc-adjustment-' + costingId).val()) || 0;
  
      // Calculate "hc-this-claim"
      // Add debug logging to understand the values
      console.log(`Calculating HC This Claim for costing ${costingId}:`);
      console.log(`- contractBudget: ${contractBudget}`);
      console.log(`- hcPrevClaimed: ${hcPrevClaimed}`);
      console.log(`- c2c: ${c2c}`);
      console.log(`- hcThisClaimInvoices: ${hcThisClaimInvoices}`);
      console.log(`- adjustment: ${adjustment}`);
      
      // IMPORTANT FIX FOR DOUBLE-COUNTING:
      // If we don't have a data-original-budget attribute, we're likely reading a value that already includes variations
      // In this case, we should correct our calculations to avoid double-counting
      const hasDataAttribute = $('#hc-contract-budget-' + costingId).attr('data-original-budget') !== undefined;
      const potentialDoubleCounting = !hasDataAttribute && X > 0;
      
      console.log(`========== DETAILED HC THIS CLAIM CALCULATION ==========`);
      console.log(`All input values:`);
      console.log(`- contractBudget (display value): ${contractBudget}`);
      console.log(`- original budget (from calculation): ${budgetDetails.original}`);
      console.log(`- X (variation amount): ${X}`);
      console.log(`- Has data-original-budget attribute: ${hasDataAttribute}`);
      console.log(`- Potential double-counting detected: ${potentialDoubleCounting}`);
      console.log(`- workingBudget (committed + uncommitted): ${workingBudget} = ${committed} + ${uncommitted}`);
      console.log(`- hcThisClaimInvoices: ${hcThisClaimInvoices}`);
      console.log(`- hcPrevInvoiced: ${hcPrevInvoiced}`);
      console.log(`- hcPrevClaimed: ${hcPrevClaimed}`);
      console.log(`- adjustment: ${adjustment}`);
      
      // If we've detected potential double-counting, adjust contractBudget by subtracting X
      let adjustedContractBudget = contractBudget;
      if (potentialDoubleCounting) {
        // We're reading a value that already includes variations, but we're also adding X separately
        // So remove X to avoid double-counting
        adjustedContractBudget = contractBudget - X;
        console.log(`Adjusted contractBudget to avoid double-counting: ${contractBudget} - ${X} = ${adjustedContractBudget}`);
      }
      
      const remainingBudget = contractBudget - hcPrevClaimed;
      console.log(`Step 1: remainingBudget = contractBudget - hcPrevClaimed = ${contractBudget} - ${hcPrevClaimed} = ${remainingBudget}`);
      
      const invoicesTotalForThisClaim = hcThisClaimInvoices + hcPrevInvoiced;
      console.log(`Step 2: invoicesTotalForThisClaim = hcThisClaimInvoices + hcPrevInvoiced = ${hcThisClaimInvoices} + ${hcPrevInvoiced} = ${invoicesTotalForThisClaim}`);
      
      const workRemaining = workingBudget - invoicesTotalForThisClaim;
      console.log(`Step 3: workRemaining = workingBudget - invoicesTotalForThisClaim = ${workingBudget} - ${invoicesTotalForThisClaim} = ${workRemaining}`);
      
      // Use the adjusted contract budget for the formula if we detected double-counting
      const completedWork = (potentialDoubleCounting ? adjustedContractBudget : contractBudget) - 
                           workRemaining - hcPrevClaimed + adjustment;
      
      console.log(`Step 4: completedWork = ${potentialDoubleCounting ? 'adjustedContractBudget' : 'contractBudget'} - workRemaining - hcPrevClaimed + adjustment = ${potentialDoubleCounting ? adjustedContractBudget : contractBudget} - ${workRemaining} - ${hcPrevClaimed} + ${adjustment} = ${completedWork}`);
      
      const adjustedCompletedWork = Math.max(0, completedWork);
      console.log(`Step 5: adjustedCompletedWork = Math.max(0, completedWork) = Math.max(0, ${completedWork}) = ${adjustedCompletedWork}`);
      
      let hcThisClaim = Math.min(remainingBudget, adjustedCompletedWork);
      console.log(`Step 6: hcThisClaim = Math.min(remainingBudget, adjustedCompletedWork) = Math.min(${remainingBudget}, ${adjustedCompletedWork}) = ${hcThisClaim}`);
      console.log(`========== END HC THIS CLAIM CALCULATION ==========`);
      // Calculate "qs-this-claim"
      console.log(`========== DETAILED QS THIS CLAIM CALCULATION ==========`);
      console.log(`Input values for QS This Claim:`);
      console.log(`- contractBudget: ${contractBudget}`);
      console.log(`- workingBudget: ${workingBudget}`);
      console.log(`- fixedOnSite: ${fixedOnSite}`);
      console.log(`- c2c (workingBudget - hcPrevInvoiced): ${c2c}`);
      console.log(`- hcThisClaimInvoices: ${hcThisClaimInvoices}`);
      console.log(`- qsClaimed (previous): ${qsClaimed}`);
      console.log(`- adjustment: ${adjustment}`);
      
      let qsThisClaim;
      if (workingBudget === 0 || isNaN(workingBudget)) {
          // Handle division by zero
          console.log(`Step QS-1: Working budget is zero or invalid, using fixedOnSite directly`);
          qsThisClaim = fixedOnSite > 0 ? fixedOnSite : 0;
          console.log(`Step QS-2: Result = ${qsThisClaim}`);
      } else {
          // Formula part 1: (contract budget to working budget ratio * fixedOnSite) - qsClaimed + adjustment
          const contractToWorkingRatio = contractBudget / workingBudget;
          console.log(`Step QS-1: Calculate contract to working budget ratio = ${contractBudget} / ${workingBudget} = ${contractToWorkingRatio}`);
          
          const adjustedFixedOnSite = contractToWorkingRatio * fixedOnSite;
          console.log(`Step QS-2: Calculate adjusted fixedOnSite = ${contractToWorkingRatio} * ${fixedOnSite} = ${adjustedFixedOnSite}`);
          
          // Subtract previous QS claimed from adjusted fixed on site
          const baseFirstPart = adjustedFixedOnSite - qsClaimed;
          console.log(`Step QS-3: Base first part = adjustedFixedOnSite - qsClaimed = ${adjustedFixedOnSite} - ${qsClaimed} = ${baseFirstPart}`);
          
          // Add adjustment to this result
          const firstPart = baseFirstPart + adjustment;
          console.log(`Step QS-4: First part with adjustment = (adjustedFixedOnSite - qsClaimed) + adjustment = ${baseFirstPart} + ${adjustment} = ${firstPart}`);
          
          // Formula part 2: contract budget minus previous QS claimed
          const secondPart = contractBudget - qsClaimed;
          console.log(`Step QS-5: Second part = contractBudget - qsClaimed = ${contractBudget} - ${qsClaimed} = ${secondPart}`);
          
          // Take minimum of both parts
          qsThisClaim = Math.min(firstPart, secondPart);
          console.log(`Step QS-6: Final QS This Claim = Math.min(${firstPart}, ${secondPart}) = ${qsThisClaim}`);
      }
      console.log(`========== END QS THIS CLAIM CALCULATION ==========`);
  
      $('#hc-this-claim-' + costingId).text(formatNumber(hcThisClaim));
      $('#qs-this-claim-' + costingId).text(formatNumber(qsThisClaim));
  
      flashCell('#hc-this-claim-' + costingId);
      flashCell('#qs-this-claim-' + costingId);
  
      // Recalculate totals for the group
      var parentRow = $('#hc-adjustment-' + costingId).closest('tr').prevAll('tr[data-toggle="unique-collapse"]').first();
      if (parentRow.length > 0) {
        var groupNumber = parentRow.data('target').replace('.unique-group', '');
        calculateTotals(groupNumber);
      }
    }
  
    //////////////////////////////////////////////////////
    // 5) The "calculateTotals(groupNumber)" function
    //////////////////////////////////////////////////////
  
    function calculateTotals(groupNumber) {
      // Summation across the entire table
      let totalRow = $('#hcPrepSheetTotalRow');
      let totalContractBudget = 0,
          totalWorkingBudget = 0,
          totalUncommitted = 0,
          totalCommitted = 0,
          totalFOSCurrent = 0,
          totalFOSPrevious = 0,
          totalFOSThis = 0,
          totalPrevSCInvoices = 0,
          totalThisSCInvoices = 0,
          totalAdjustment = 0,
          totalPrevHCClaims = 0,
          totalThisHCClaims = 0,
          totalPrevQSClaims = 0,
          totalThisQSClaims = 0;
    
      // Sum all 'collapse' rows in <tbody>
      $('tbody tr.collapse').each(function() {
        let cells = $(this).find('td');
        if (cells.length >= 16) {
          // Use the displayed value which already includes variations
          // This avoids double-counting variations
          totalContractBudget += parseFloat(cells.eq(2).text().replace(/,/g, '').replace('-', '0')) || 0;
          totalWorkingBudget += parseFloat(cells.eq(3).text().replace(/,/g, '').replace('-', '0')) || 0;
          totalUncommitted += parseFloat(cells.eq(4).text().replace(/,/g, '').replace('-', '0')) || 0;
          totalCommitted += parseFloat(cells.eq(5).text().replace(/,/g, '').replace('-', '0')) || 0;
          totalFOSCurrent += parseFloat(cells.eq(6).text().replace(/,/g, '').replace('-', '0')) || 0;
          totalFOSPrevious += parseFloat(cells.eq(7).text().replace(/,/g, '').replace('-', '0')) || 0;
          totalFOSThis += parseFloat(cells.eq(8).text().replace(/,/g, '').replace('-', '0')) || 0;
          totalPrevSCInvoices += parseFloat(cells.eq(9).text().replace(/,/g, '').replace('-', '0')) || 0;
          totalThisSCInvoices += parseFloat(cells.eq(10).text().replace(/,/g, '').replace('-', '0')) || 0;
          totalAdjustment += parseFloat(cells.eq(11).find('input').val()) || 0;
          totalPrevHCClaims += parseFloat(cells.eq(12).text().replace(/,/g, '').replace('-', '0')) || 0;
          totalThisHCClaims += parseFloat(cells.eq(13).text().replace(/,/g, '').replace('-', '0')) || 0;
          totalPrevQSClaims += parseFloat(cells.eq(14).text().replace(/,/g, '').replace('-', '0')) || 0;
          totalThisQSClaims += parseFloat(cells.eq(15).text().replace(/,/g, '').replace('-', '0')) || 0;
        }
      });
    
      // Populate the bottom row (#hcPrepSheetTotalRow)
      function maybeDash(val) {
        return val === 0 ? '-' : formatNumber(val);
      }
    
      for (let i = 2; i <= 15; i++) {
        totalRow.find('td').eq(i).html(maybeDash(eval('total' + ['ContractBudget', 'WorkingBudget', 'Uncommitted', 'Committed', 'FOSCurrent', 'FOSPrevious', 'FOSThis', 'PrevSCInvoices', 'ThisSCInvoices', 'Adjustment', 'PrevHCClaims', 'ThisHCClaims', 'PrevQSClaims', 'ThisQSClaims'][i - 2]))).css('font-weight', 'bold');
      }
    
      // Now also do the sums for the specific group heading row
      let groupRow = $('[data-target=".unique-group' + groupNumber + '"]').closest('tr');
      let gSumContract = 0,
          gSumWorking = 0,
          gSumUncom = 0,
          gSumCom = 0,
          gFOSCur = 0,
          gFOSPrev = 0,
          gFOSThis = 0,
          gSCPrev = 0,
          gSCThis = 0,
          gAdj = 0,
          gHCPrev = 0,
          gHCThis = 0,
          gQSPrev = 0,
          gQSThis = 0;
    
      $('.unique-group' + groupNumber).each(function() {
        let cc = $(this).find('td');
        if (cc.length >= 16) {
          // Use the displayed value which already includes variations
          // This avoids double-counting variations
          gSumContract += parseFloat(cc.eq(2).text().replace(/,/g, '').replace('-', '0')) || 0;
          gSumWorking += parseFloat(cc.eq(3).text().replace(/,/g, '').replace('-', '0')) || 0;
          gSumUncom += parseFloat(cc.eq(4).text().replace(/,/g, '').replace('-', '0')) || 0;
          gSumCom += parseFloat(cc.eq(5).text().replace(/,/g, '').replace('-', '0')) || 0;
          gFOSCur += parseFloat(cc.eq(6).text().replace(/,/g, '').replace('-', '0')) || 0;
          gFOSPrev += parseFloat(cc.eq(7).text().replace(/,/g, '').replace('-', '0')) || 0;
          gFOSThis += parseFloat(cc.eq(8).text().replace(/,/g, '').replace('-', '0')) || 0;
          gSCPrev += parseFloat(cc.eq(9).text().replace(/,/g, '').replace('-', '0')) || 0;
          gSCThis += parseFloat(cc.eq(10).text().replace(/,/g, '').replace('-', '0')) || 0;
          gAdj += parseFloat(cc.eq(11).find('input').val()) || 0;
          gHCPrev += parseFloat(cc.eq(12).text().replace(/,/g, '').replace('-', '0')) || 0;
          gHCThis += parseFloat(cc.eq(13).text().replace(/,/g, '').replace('-', '0')) || 0;
          gQSPrev += parseFloat(cc.eq(14).text().replace(/,/g, '').replace('-', '0')) || 0;
          gQSThis += parseFloat(cc.eq(15).text().replace(/,/g, '').replace('-', '0')) || 0;
        }
      });
    
      // Populate the group heading row
      for (let i = 2; i <= 15; i++) {
        groupRow.find('td').eq(i).html(maybeDash(eval('g' + ['SumContract', 'SumWorking', 'SumUncom', 'SumCom', 'FOSCur', 'FOSPrev', 'FOSThis', 'SCPrev', 'SCThis', 'Adj', 'HCPrev', 'HCThis', 'QSPrev', 'QSThis'][i - 2]))).css('font-weight', 'bold');
      }
    
      // Apply color sliders to category total rows
      if (gSumWorking > 0) {
        let percentage = Math.min((gFOSCur / gSumWorking) * 100, 100);
        if (percentage < 100) {
          groupRow.find('td').eq(6).attr('style', 'background: linear-gradient(to right, #bcdcf5 ' + percentage + '%, transparent ' + percentage + '%); font-weight: bold;');
        } else {
          groupRow.find('td').eq(6).attr('style', 'background: linear-gradient(to right, #BCF5C0 100%, transparent 100%); font-weight: bold;');
        }
      } else {
        groupRow.find('td').eq(6).attr('style', 'font-weight: bold;');
      }
    }
  
    //////////////////////////////////////////////////////
    // 6) “Save” + “Finalise” => gather the entire table and POST to server
    //////////////////////////////////////////////////////
  
    function gatherAndPostHCClaimData(currentHcClaimId, save_or_final) {
      let data = [];
      // Loop over table rows
      $('table.myTable tbody tr:not(#hcPrepSheetTotalRow)').each(function() {
        let row = $(this);
        let category = row.find('td').eq(0).data('category');
        let itemId = row.find('td').eq(1).data('item-id');
        if (category === undefined || itemId === undefined) {
          return; // skip header or summary rows
        }
  
        let contractBudget = parseFloat(row.find('td').eq(2).text().replace(/,/g, '')) || 0;
        let workingBudget = parseFloat(row.find('td').eq(3).text().replace(/,/g, '')) || 0;
        let uncommitted = parseFloat(row.find('td').eq(4).text().replace(/,/g, '')) || 0;
        let committed = parseFloat(row.find('td').eq(5).text().replace(/,/g, '')) || 0;
        let fixedOnSiteCurrent = parseFloat(row.find('td').eq(6).text().replace(/,/g, '')) || 0;
        let fixedOnSitePrev = parseFloat(row.find('td').eq(7).text().replace(/,/g, '')) || 0;
        let fixedOnSiteThis = parseFloat(row.find('td').eq(8).text().replace(/,/g, '')) || 0;
        let scPrev = parseFloat(row.find('td').eq(9).text().replace(/,/g, '')) || 0;
        // For SC This, check if it's a margin item input first
        let scThis;
        const marginItemInput = row.find('td').eq(10).find('input.margin-item-input');
        if (marginItemInput.length > 0) {
            scThis = parseFloat(marginItemInput.val()) || 0;
        } else {
            scThis = parseFloat(row.find('td').eq(10).text().replace(/,/g, '')) || 0;
        }
        let adjustment = parseFloat(row.find('td').eq(11).find('input').val()) || 0;
        let hcPrev = parseFloat(row.find('td').eq(12).text().replace(/,/g, '')) || 0;
        let hcThis = parseFloat(row.find('td').eq(13).text().replace(/,/g, '')) || 0;
        let qsPrev = parseFloat(row.find('td').eq(14).text().replace(/,/g, '')) || 0;
        let qsThis = parseFloat(row.find('td').eq(15).text().replace(/,/g, '')) || 0;
  
        data.push({
          category: category,
          item_id: itemId,
          contract_budget: contractBudget,
          working_budget: workingBudget,
          uncommitted: uncommitted,
          committed: committed,
          fixed_on_site_current: fixedOnSiteCurrent,
          fixed_on_site_previous: fixedOnSitePrev,
          fixed_on_site_this: fixedOnSiteThis,
          sc_invoiced_previous: scPrev,
          sc_invoiced: scThis,
          adjustment: adjustment,
          hc_claimed_previous: hcPrev,
          hc_claimed: hcThis,
          qs_claimed_previous: qsPrev,
          qs_claimed: qsThis
        });
      });
  
      console.log("Final data gathered: ", data);
  
      $.ajax({
        url: "/update_hc_claim_data/",
        type: "POST",
        contentType: "application/json",
        data: JSON.stringify({
          hc_claim_data: data,
          current_hc_claim_display_id: currentHcClaimId,
          save_or_final: save_or_final
        }),
        success: function(response) {
          alert('Head Contract Claim Finalised. Data saved successfully.');
          location.reload();
        },
        error: function(xhr, status, error) {
          alert('An error occurred while saving data.');
          console.log(xhr.responseText);
        }
      });
    }
  
    // The two buttons in the modal
    $('#saveAdjustmentsButton').on('click', function(event) {
      event.preventDefault();
      const currentHcClaimId = $('#hcPrepSheetModal').data('current-hc-claim-id');
      gatherAndPostHCClaimData(currentHcClaimId || 0, 0);  // Save mode
    });
  
    $('#finalise_hc_claim_btn').on('click', function(event) {
      event.preventDefault();
      let claimId = $(this).data('claim-id');
      gatherAndPostHCClaimData(claimId, 1);  // Finalise mode
    });

    $('#hcPrepSheetModal').on('shown.bs.modal', function() {
      colorCurrentCells();
    });
  
  });
  