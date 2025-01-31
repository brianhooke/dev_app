// HC Claim Prep Sheet

document.addEventListener('DOMContentLoaded', function() {

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
  
    function formatNumber(num) {
      // 2 decimal places + thousand separators
      return parseFloat(num).toLocaleString('en-US', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
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
  
    $('.save-hc-costs').click(function(event) {
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
          }
        },
        error: function(err) {
          console.error('Error saving uncommitted:', err);
        }
      });
    });
  
    //////////////////////////////////////////////////////
    // 3) Updating "Fixed on Site" => /update_fixedonsite/
    //////////////////////////////////////////////////////
  
    $('.save-hc-fixed-costs').click(function(event) {
      event.preventDefault();
      var costingId = $(this).data('id');
      var rawVal = $('#hc-claim-newFixedOnSite' + costingId).val();
      var newValue = parseFloat(rawVal.replace(/,/g, '')) || 0;
  
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
          }
        },
        error: function(err) {
          console.error('Error saving fixed on site:', err);
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
      let contractBudget = parseFloat($('#hc-contract-budget-' + costingId).text().replace(/,/g, '')) || 0;
      let committed = parseFloat($('#hc-claim-committed-' + costingId).text().replace(/,/g, '')) || 0;
      let uncommitted = parseFloat($('#hc-claim-uncommitted-' + costingId + ' a').text().replace(/,/g, '')) || 0;
      let hcPrevInvoiced = parseFloat($('#hc-prev-invoiced-' + costingId).text().replace(/,/g, '')) || 0;
      let hcThisClaimInvoices = parseFloat($('#hc-this-claim-invoices-' + costingId).text().replace(/,/g, '')) || 0;
      let hcPrevClaimed = parseFloat($('#hc-prev-claimed-' + costingId).text().replace(/,/g, '')) || 0;
      let fixedOnSite = parseFloat($('#fixed-on-site-display-' + costingId + ' a').text().replace(/,/g, '')) || 0;
      let qsClaimed = parseFloat($('#qs-claimed-' + costingId).text().replace(/,/g, '')) || 0;
      let adjustment = parseFloat($('#hc-adjustment-' + costingId).val()) || 0;
  
      // Calculate "hc-this-claim"
      let hcThisClaim = Math.min(
        contractBudget - hcPrevClaimed,
        Math.max(
          0,
          contractBudget - committed - uncommitted - hcPrevInvoiced + hcThisClaimInvoices - hcPrevClaimed + adjustment
        )
      );
      // Calculate "qs-this-claim"
      let qsThisClaim = Math.min(
        contractBudget - qsClaimed,
        Math.max(
          0,
          Math.min(
            contractBudget - (committed + uncommitted - (hcPrevInvoiced + hcThisClaimInvoices)),
            fixedOnSite
          ) - qsClaimed + adjustment
        )
      );
  
      $('#hc-this-claim-' + costingId).text(hcThisClaim > 0 ? formatNumber(hcThisClaim) : '-');
      $('#qs-this-claim-' + costingId).text(qsThisClaim > 0 ? formatNumber(qsThisClaim) : '-');
  
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
  
      // sum all 'collapse' rows in <tbody>
      $('tbody tr.collapse').each(function() {
        let cells = $(this).find('td');
        if (cells.length >= 16) {
          let cb = parseFloat(cells.eq(2).text().replace(/,/g, '')) || 0;  // contract
          let wb = parseFloat(cells.eq(3).text().replace(/,/g, '')) || 0;  // working
          let uncom = parseFloat(cells.eq(4).text().replace(/,/g, '')) || 0;
          let com = parseFloat(cells.eq(5).text().replace(/,/g, '')) || 0;
          let fosCur = parseFloat(cells.eq(6).text().replace(/,/g, '')) || 0;
          let fosPrev = parseFloat(cells.eq(7).text().replace(/,/g, '')) || 0;
          let fosThis = parseFloat(cells.eq(8).text().replace(/,/g, '')) || 0;
          let scPrev = parseFloat(cells.eq(9).text().replace(/,/g, '')) || 0;
          let scThis = parseFloat(cells.eq(10).text().replace(/,/g, '')) || 0;
          let adj = parseFloat(cells.eq(11).find('input').val()) || 0;
          let hcPrev = parseFloat(cells.eq(12).text().replace(/,/g, '')) || 0;
          let hcThis = parseFloat(cells.eq(13).text().replace(/,/g, '')) || 0;
          let qsPrev = parseFloat(cells.eq(14).text().replace(/,/g, '')) || 0;
          let qsThis = parseFloat(cells.eq(15).text().replace(/,/g, '')) || 0;
  
          totalContractBudget += cb;
          totalWorkingBudget += wb;
          totalUncommitted += uncom;
          totalCommitted += com;
          totalFOSCurrent += fosCur;
          totalFOSPrevious += fosPrev;
          totalFOSThis += fosThis;
          totalPrevSCInvoices += scPrev;
          totalThisSCInvoices += scThis;
          totalAdjustment += adj;
          totalPrevHCClaims += hcPrev;
          totalThisHCClaims += hcThis;
          totalPrevQSClaims += qsPrev;
          totalThisQSClaims += qsThis;
        }
      });
  
      // populate the bottom row (#hcPrepSheetTotalRow)
      function maybeDash(val) {
        return val === 0 ? '-' : formatNumber(val);
      }
  
      totalRow.find('td').eq(2).html(maybeDash(totalContractBudget));
      totalRow.find('td').eq(3).html(maybeDash(totalWorkingBudget));
      totalRow.find('td').eq(4).html(maybeDash(totalUncommitted));
      totalRow.find('td').eq(5).html(maybeDash(totalCommitted));
      totalRow.find('td').eq(6).html(maybeDash(totalFOSCurrent));
      totalRow.find('td').eq(7).html(maybeDash(totalFOSPrevious));
      totalRow.find('td').eq(8).html(maybeDash(totalFOSThis));
      totalRow.find('td').eq(9).html(maybeDash(totalPrevSCInvoices));
      totalRow.find('td').eq(10).html(maybeDash(totalThisSCInvoices));
      totalRow.find('td').eq(11).html(maybeDash(totalAdjustment));
      totalRow.find('td').eq(12).html(maybeDash(totalPrevHCClaims));
      totalRow.find('td').eq(13).html(maybeDash(totalThisHCClaims));
      totalRow.find('td').eq(14).html(maybeDash(totalPrevQSClaims));
      totalRow.find('td').eq(15).html(maybeDash(totalThisQSClaims));
  
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
          let cb = parseFloat(cc.eq(2).text().replace(/,/g, '')) || 0;
          let wb = parseFloat(cc.eq(3).text().replace(/,/g, '')) || 0;
          let u = parseFloat(cc.eq(4).text().replace(/,/g, '')) || 0;
          let c = parseFloat(cc.eq(5).text().replace(/,/g, '')) || 0;
          let fosC = parseFloat(cc.eq(6).text().replace(/,/g, '')) || 0;
          let fosP = parseFloat(cc.eq(7).text().replace(/,/g, '')) || 0;
          let fosT = parseFloat(cc.eq(8).text().replace(/,/g, '')) || 0;
          let scP = parseFloat(cc.eq(9).text().replace(/,/g, '')) || 0;
          let scT = parseFloat(cc.eq(10).text().replace(/,/g, '')) || 0;
          let adj = parseFloat(cc.eq(11).find('input').val()) || 0;
          let hcP = parseFloat(cc.eq(12).text().replace(/,/g, '')) || 0;
          let hcT = parseFloat(cc.eq(13).text().replace(/,/g, '')) || 0;
          let qsP = parseFloat(cc.eq(14).text().replace(/,/g, '')) || 0;
          let qsT = parseFloat(cc.eq(15).text().replace(/,/g, '')) || 0;
  
          gSumContract += cb;
          gSumWorking += wb;
          gSumUncom += u;
          gSumCom += c;
          gFOSCur += fosC;
          gFOSPrev += fosP;
          gFOSThis += fosT;
          gSCPrev += scP;
          gSCThis += scT;
          gAdj += adj;
          gHCPrev += hcP;
          gHCThis += hcT;
          gQSPrev += qsP;
          gQSThis += qsT;
        }
      });
  
      groupRow.find('td').eq(2).html(maybeDash(gSumContract));
      groupRow.find('td').eq(3).html(maybeDash(gSumWorking));
      groupRow.find('td').eq(4).html(maybeDash(gSumUncom));
      groupRow.find('td').eq(5).html(maybeDash(gSumCom));
      groupRow.find('td').eq(6).html(maybeDash(gFOSCur));
      groupRow.find('td').eq(7).html(maybeDash(gFOSPrev));
      groupRow.find('td').eq(8).html(maybeDash(gFOSThis));
      groupRow.find('td').eq(9).html(maybeDash(gSCPrev));
      groupRow.find('td').eq(10).html(maybeDash(gSCThis));
      groupRow.find('td').eq(11).html(maybeDash(gAdj));
      groupRow.find('td').eq(12).html(maybeDash(gHCPrev));
      groupRow.find('td').eq(13).html(maybeDash(gHCThis));
      groupRow.find('td').eq(14).html(maybeDash(gQSPrev));
      groupRow.find('td').eq(15).html(maybeDash(gQSThis));
    }
  
    //////////////////////////////////////////////////////
    // 6) “Save” + “Finalise” => gather the entire table and POST to server
    //////////////////////////////////////////////////////
  
    function gatherAndPostHCClaimData(currentHcClaimId) {
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
        let scThis = parseFloat(row.find('td').eq(10).text().replace(/,/g, '')) || 0;
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
          current_hc_claim_display_id: currentHcClaimId
        }),
        success: function(response) {
          alert('Data saved successfully!');
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
      gatherAndPostHCClaimData(0);  // pass 0 to indicate "not finalised"
    });
  
    $('#finalise_hc_claim_btn').on('click', function(event) {
      event.preventDefault();
      let claimId = $(this).data('claim-id');
      gatherAndPostHCClaimData(claimId);  // pass real ID => finalise
    });
  
  });
  