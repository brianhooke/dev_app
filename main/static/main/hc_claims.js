document.addEventListener('DOMContentLoaded', function() {
    // Handle "Create HC Claim" dropdown selection
    document.getElementById('hcDropdown').addEventListener('change', function(e) {
        if (e.target.value === 'makeClaim') {
            $('#hcSelectInvoicesModal').modal('show');
        }
    });

    // Handle "Create HC Claim" dropdown selection
    document.getElementById('hcDropdown').addEventListener('change', function(e) {
        if (e.target.value === 'existingClaims') {
            $('#existingClaimsModal').modal('show');
        }
    });

    // Handle "Existing Invoices" dropdown selection
    document.getElementById('claimsDropdownInvoices').addEventListener('change', function(e) {
        if (e.target.value === 'existingClaims') {
            $('#unallocatedInvoicesModal').modal('show');
        }
    });

    // Handle "View" link click in the SC Invoice selections modal
    document.querySelectorAll('.view-pdf-invoices').forEach(link => {
        link.addEventListener('click', function(event) {
            console.log("View PDF link clicked")
            event.preventDefault();
            const pdfUrl = this.getAttribute('data-url');
            fetch(pdfUrl, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/pdf'
                }
            })
            .then(response => response.blob())
            .then(blob => {
                const url = URL.createObjectURL(blob);
                const pdfViewer = document.getElementById('hcInvoicesPdfViewer');
                pdfViewer.src = url;
            })
            .catch(error => {
                console.error('Error fetching PDF:', error);
            });
        });
    });

    $(document).ready(function() {
        $('#hcSendInvoicesToXeroButton').click(function() {
            var selectedInvoices = [];
            $('input[type=checkbox]:checked').each(function() {
                var invoiceId = $(this).attr('id').replace('hcIncludeInClaim', '');
                selectedInvoices.push(invoiceId);
            });
            $.ajax({
                url: '/associate_sc_claims_with_hc_claim/',  // Update with your actual URL
                type: 'POST',
                data: {
                    'selectedInvoices': selectedInvoices
                },
                success: function(response) {
                    // Handle success response
                    alert('New HC Claim started. The selected invoices have been associated with the new HC Claim.');
                    location.reload();
                },
                error: function(response) {
                    // Handle error response
                    alert(response.responseJSON.error);
                }
            });
        });
    });
    
      
//Updated Uncommitted in HC Claim Prep Sheet with Ajax
$(document).ready(function() {
    // Add CSRF token to every jQuery AJAX request
    var csrftoken = getCookie('csrftoken');
    
    $.ajaxSetup({
        beforeSend: function(xhr, settings) {
            xhr.setRequestHeader('X-CSRFToken', csrftoken);
        }
    });
});

$(document).ready(function() {
    $('tr').each(function() {
        var fixedOnSiteCell = $(this).find('td[id^="fixed-on-site-display-"]');
        if (fixedOnSiteCell.length > 0) {
            var id = fixedOnSiteCell.attr('id');
            var costingId = id.split('-').pop();
            // Get the text values from both cells
            var fixedOnSiteText = $(this).find('td[id^="fixed-on-site-display-"]').text().trim();
            var prevFixedOnSiteText = $(this).find('td[id^="prev-fixed-on-site-display-"]').text().trim();
            // Convert text to numeric values or default to 0 if not a valid number
            var fixedOnSite = (fixedOnSiteText === '-' || fixedOnSiteText === '' || isNaN(parseFloat(fixedOnSiteText.replace(/,/g, '')))) ? 0 : parseFloat(fixedOnSiteText.replace(/,/g, ''));
            var prevFixedOnSite = (prevFixedOnSiteText === '-' || prevFixedOnSiteText === '' || isNaN(parseFloat(prevFixedOnSiteText.replace(/,/g, '')))) ? 0 : parseFloat(prevFixedOnSiteText.replace(/,/g, ''));
            // Calculate the difference
            var difference = fixedOnSite - prevFixedOnSite;
            // Format the result: Add thousand separators and 2 decimal places
            var differenceStr = difference !== 0 ? formatNumber(difference) : '-';
            // Update the difference cell
            $('#difference-' + costingId).text(differenceStr);
        }
    });
});


// Update Uncommitted Modal
$('.save-hc-costs').click(function(event) {
    event.preventDefault();  // Prevent default behavior
    var costingId = $(this).data('id');
    var newUncommittedValue = $('#hc-claim-uncommittedInput' + costingId).val();
    // Convert uncommitted value to float
    newUncommittedValue = parseFloat(newUncommittedValue) || 0;
    // AJAX request to update the database
    $.ajax({
        url: '/update_uncommitted/',
        type: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({
            'costing_pk': costingId,
            'uncommitted': newUncommittedValue,
        }),
        success: function(data) {
            if (data.status == 'success') {
                // Hide the inner modal after saving
                $('#hc-claim-editModal' + costingId).modal('hide');
                // Ensure the focus remains on the hcPrepSheetModal
                $('#hcPrepSheetModal').modal('show');
                $('body').addClass('modal-open');  // Lock body scrolling
                // Update the uncommitted value in the main table
                var formattedUncommitted = formatNumber(newUncommittedValue);
                $('#hc-claim-uncommitted-' + costingId + ' a').text(formattedUncommitted);
                // Update total value
                var committedValue = parseFloat($('#hc-claim-committed-' + costingId).text().replace(/,/g, '')) || 0;
                var total = (newUncommittedValue + committedValue).toFixed(2);
                $('#hc-claim-total-' + costingId).text(formatNumber(total));
                // Get the values from the corresponding cells
                var contractBudget = parseFloat($('#hc-contract-budget-' + costingId).text().replace(/,/g, '')) || 0;
                var committed = parseFloat($('#hc-claim-committed-' + costingId).text().replace(/,/g, '')) || 0;
                var hcPrevInvoiced = parseFloat($('#hc-prev-invoiced-' + costingId).text().replace(/,/g, '')) || 0;
                var hcThisClaimInvoices = parseFloat($('#hc-this-claim-invoices-' + costingId).text().replace(/,/g, '')) || 0;
                var hcPrevClaimed = parseFloat($('#hc-prev-claimed-' + costingId).text().replace(/,/g, '')) || 0;
                var fixedOnSite = parseFloat($('#fixed-on-site-display-' + costingId + ' a').text().replace(/,/g, '')) || 0;
                var qsClaimed = parseFloat($('#qs-claimed-' + costingId).text().replace(/,/g, '')) || 0;
                var adjustment = parseFloat($('#hc-adjustment-' + costingId).val().replace(/,/g, '')) || 0;                
                console.log("Adjustment 1 is: "+adjustment);
                var thisQsClaim = Math.min(contractBudget - qsClaimed, Math.max(0,Math.min(contractBudget - (committed + newUncommittedValue - (hcPrevInvoiced + hcThisClaimInvoices)), fixedOnSite) - qsClaimed + adjustment)).toFixed(2);
                // Calculate the new value
                var result = Math.min(contractBudget - hcPrevClaimed, Math.max(0,contractBudget - committed - newUncommittedValue - hcPrevInvoiced + hcThisClaimInvoices - hcPrevClaimed + adjustment)).toFixed(2);
                // Update the hc-this-claim & qs-this-claim cells
                $('#hc-this-claim-' + costingId).text(formatNumber(result));
                $('#qs-this-claim-' + costingId).text(formatNumber(thisQsClaim));
                // Add flash effect
                flashCell('#hc-claim-uncommitted-' + costingId);
                flashCell('#hc-claim-total-' + costingId);
                flashCell('#hc-this-claim-' + costingId);
                flashCell('#qs-this-claim-' + costingId);
                // Recalculate totals for the group
                var parentRow = $('#hc-claim-uncommitted-' + costingId).closest('tr').prevAll('tr[data-toggle="unique-collapse"]').first();
                if (parentRow.length > 0) {
                    var groupNumber = parentRow.data('target').replace('.unique-group', '');
                    calculateTotals(groupNumber);
                }
                }
        },
        error: function(xhr, errmsg, err) {
            console.error('AJAX Error:', errmsg);
        }
    });
});

    // Save HC Fixed Costs Function
    $('.save-hc-fixed-costs').click(function(event) {
        event.preventDefault();  // Prevent default behavior
        var costingId = $(this).data('id');
        var newFixedOnSiteValue = $('#hc-claim-newFixedOnSite' + costingId).val();
        // Convert fixed on site value to float
        newFixedOnSiteValue = parseFloat(newFixedOnSiteValue.replace(/,/g, '')) || 0;
        // AJAX request to update the database
        $.ajax({
            url: '/update_fixedonsite/',
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({
                'costing_pk': costingId,
                'fixed_on_site': newFixedOnSiteValue,
            }),
            success: function(data) {
                if (data.status == 'success') {
                    // Hide the inner modal after saving
                    $('#hc-claim-fixedOnSiteModal' + costingId).modal('hide');
                    // Ensure the focus remains on the hcPrepSheetModal
                    $('#hcPrepSheetModal').modal('show');
                    $('body').addClass('modal-open');  // Lock body scrolling
                    // Update the fixed on site value in the table
                    var formattedFixedOnSite = formatNumber(newFixedOnSiteValue);
                    $('#fixed-on-site-display-' + costingId + ' a').text(formattedFixedOnSite);
                    // Update the difference value
                    var prevFixedOnSite = parseFloat($('#prev-fixed-on-site-display-' + costingId).text().replace(/,/g, '')) || 0;
                    var difference = (newFixedOnSiteValue - prevFixedOnSite).toFixed(2);
                    var contractBudget = parseFloat($('#hc-contract-budget-' + costingId).text().replace(/,/g, '')) || 0;
                    var committed = parseFloat($('#hc-claim-committed-' + costingId).text().replace(/,/g, '')) || 0;
                    var uncommitted = parseFloat($('#hc-claim-uncommitted-' + costingId + ' a').text().replace(/,/g, '')) || 0;
                    var hcPrevInvoiced = parseFloat($('#hc-prev-invoiced-' + costingId).text().replace(/,/g, '')) || 0;
                    var hcThisClaimInvoices = parseFloat($('#hc-this-claim-invoices-' + costingId).text().replace(/,/g, '')) || 0;
                    var adjustment = parseFloat($('#hc-adjustment-' + costingId).val().replace(/,/g, '')) || 0;                    console.log("Adjustment 2 is: "+adjustment);
                    var qsClaimed = parseFloat($('#qs-claimed-' + costingId).text().replace(/,/g, '')) || 0;
                    var thisQsClaim = Math.min(contractBudget - qsClaimed, Math.max(0,Math.min(contractBudget - (committed + uncommitted - (hcPrevInvoiced + hcThisClaimInvoices)), newFixedOnSiteValue) - qsClaimed + adjustment)).toFixed(2);
                    $('#difference-' + costingId).text(difference !== 0 ? formatNumber(difference) : '-');
                    $('#qs-this-claim-' + costingId).text(formatNumber(thisQsClaim));
                    // Add flash effect
                    flashCell('#fixed-on-site-display-' + costingId);
                    flashCell('#difference-' + costingId);
                    flashCell('#qs-this-claim-' + costingId);
                    // Recalculate totals for the group
                    var parentRow = $('#fixed-on-site-display-' + costingId).closest('tr').prevAll('tr[data-toggle="unique-collapse"]').first();
                    if (parentRow.length > 0) {
                        var groupNumber = parentRow.data('target').replace('.unique-group', '');
                        calculateTotals(groupNumber);
                    }
                }
            },
            error: function(xhr, errmsg, err) {
                console.error('AJAX Error:', errmsg);
            }
        });
    });

    // Get all input elements with id starting with 'hc-adjustment-'
    let inputs = $('input[id^="hc-adjustment-"]');
    inputs.on('input', function() {
        let id = this.id.split('-')[2]; // Get the id part from 'hc-adjustment-{{costing.costing_pk}}'
        // Get all the necessary values
        let contractBudget = parseFloat($('#hc-contract-budget-' + id).text().replace(/,/g, '')) || 0;
        console.log("Contract Budget is: "+contractBudget);
        let committed = parseFloat($('#hc-claim-committed-' + id).text().replace(/,/g, '')) || 0;
        console.log("Committed is: "+committed);
        let uncommitted = parseFloat($('#hc-claim-uncommitted-' + id).text().replace(/,/g, '')) || 0;
        console.log("Uncommitted is: "+uncommitted);
        let hcPrevInvoiced = parseFloat($('#hc-prev-invoiced-' + id).text().replace(/,/g, '')) || 0;
        console.log("HC Prev Invoiced is: "+hcPrevInvoiced);
        let hcThisClaimInvoices = parseFloat($('#hc-this-claim-invoices-' + id).text().replace(/,/g, '')) || 0;
        console.log("HC This Claim Invoices is: "+hcThisClaimInvoices);
        let hcPrevClaimed = parseFloat($('#hc-prev-claimed-' + id).text().replace(/,/g, '')) || 0;
        console.log("HC Prev Claimed is: "+hcPrevClaimed);
        let fixed_on_site = parseFloat($('#fixed-on-site-display-' + id).text().replace(/,/g, '')) || 0;
        console.log("Fixed on Site is: "+fixed_on_site);
        let qsClaimed = parseFloat($('#qs-claimed-' + id).text().replace(/,/g, '')) || 0;
        console.log("QS Claimed is: "+qsClaimed);
        let adjustment = parseFloat($('#hc-adjustment-' + id).val()) || 0; // Get the value of the input field
        console.log("Adjustment is: "+adjustment);
        // Calculate hc-this-claim
        let hcThisClaim = Math.min(contractBudget - hcPrevClaimed, Math.max(0,(contractBudget - committed - uncommitted - hcPrevInvoiced + hcThisClaimInvoices - hcPrevClaimed + adjustment))).toFixed(2);
        console.log("HC This Claim is: "+hcThisClaim);
        $('#hc-this-claim-' + id).text(formatNumber(hcThisClaim));
        // Calculate qs-this-claim
        let qsThisClaim = Math.min(contractBudget - qsClaimed, (Math.max(0,Math.min(contractBudget - (committed + uncommitted - (hcPrevInvoiced + hcThisClaimInvoices)), fixed_on_site) - qsClaimed + adjustment))).toFixed(2);
        console.log("QS This Claim is: "+qsThisClaim);
        $('#qs-this-claim-' + id).text(formatNumber(qsThisClaim));
        flashCell('#qs-this-claim-' + id);
        flashCell('#hc-this-claim-' + id);
        // Recalculate totals for the group
        var parentRow = $('#hc-adjustment-' + id).closest('tr').prevAll('tr[data-toggle="unique-collapse"]').first();
        if (parentRow.length > 0) {
            var groupNumber = parentRow.data('target').replace('.unique-group', '');
            calculateTotals(groupNumber);
        } else {
            console.error('Could not find the parent row with data-target for adjustment input:', id);
        }
    });

    // Function to add flash effect
    function flashCell(selector) {
        $(selector).addClass('flash-update');
        setTimeout(function() {
            $(selector).removeClass('flash-update');
        }, 5000);
    }

    
    // Helper function to format numbers with commas and 2 decimal places
    function formatNumber(num) {
        return parseFloat(num).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }

    // Manually force focus back to the main modal after inner modals close
    $('.modal').on('hidden.bs.modal', function() {
        if ($('#hcPrepSheetModal').hasClass('show')) {
            $('body').addClass('modal-open');  // Ensure scrolling remains locked to the modal
        }
    });

        // Function to update the arrow direction
        function updateArrowDirection(element) {
            if (element.hasClass('unique-collapsed')) {
                element.find('.unique-dropdown-arrow').html('&#9654;'); // Right arrow (collapsed)
            } else {
                element.find('.unique-dropdown-arrow').html('&#9660;'); // Down arrow (expanded)
            }
        }

// Function to calculate totals for all rows in the table (ignores groupNumber)
function calculateTotals(groupNumber) {
    var totalContractBudget = 0;
    var totalWorkingBudget = 0;
    var totalUncommitted = 0;
    var totalCommitted = 0;
    var totalFixedOnSiteCurrent = 0;
    var totalFixedOnSitePrevious = 0;
    var totalFixedOnSiteThis = 0;
    var totalPrevSCInvoices = 0;
    var totalThisSCInvoices = 0;
    var totalPrevHCClaims = 0;
    var totalThisHCClaims = 0;
    var totalPrevQSClaims = 0;
    var totalThisQSClaims = 0;
    var totalAdjustment = 0;

    // Loop through all rows in the table to accumulate totals
    $('tbody tr.collapse').each(function () {
        var cells = $(this).find('td');
        // Ensure there are enough cells in the row to avoid errors
        if (cells.length >= 16) {
            var contractBudget = parseFloat(cells.eq(2).text().replace(/,/g, '').trim()) || 0;
            var workingBudget = parseFloat(cells.eq(3).text().replace(/,/g, '').trim()) || 0;
            var uncommitted = parseFloat(cells.eq(4).text().replace(/,/g, '').trim()) || 0;
            var committed = parseFloat(cells.eq(5).text().replace(/,/g, '').trim()) || 0;
            var fixedOnSiteCurrent = parseFloat(cells.eq(6).text().replace(/,/g, '').trim()) || 0;
            var fixedOnSitePrevious = parseFloat(cells.eq(7).text().replace(/,/g, '').trim()) || 0;
            var fixedOnSiteThis = parseFloat(cells.eq(8).text().replace(/,/g, '').trim()) || 0;
            var prevSCInvoices = parseFloat(cells.eq(9).text().replace(/,/g, '').trim()) || 0;
            var thisSCInvoices = parseFloat(cells.eq(10).text().replace(/,/g, '').trim()) || 0;
            var prevHCClaims = parseFloat(cells.eq(12).text().replace(/,/g, '').trim()) || 0;
            var thisHCClaims = parseFloat(cells.eq(13).text().replace(/,/g, '').trim()) || 0;
            var prevQSClaims = parseFloat(cells.eq(14).text().replace(/,/g, '').trim()) || 0;
            var thisQSClaims = parseFloat(cells.eq(15).text().replace(/,/g, '').trim()) || 0;
            var adjustment = parseFloat(cells.eq(11).find('input').val().replace(/,/g, '').trim()) || 0;

            // Accumulate totals
            totalContractBudget += contractBudget;
            totalWorkingBudget += workingBudget;
            totalUncommitted += uncommitted;
            totalCommitted += committed;
            totalFixedOnSiteCurrent += fixedOnSiteCurrent;
            totalFixedOnSitePrevious += fixedOnSitePrevious;
            totalFixedOnSiteThis += fixedOnSiteThis;
            totalPrevSCInvoices += prevSCInvoices;
            totalThisSCInvoices += thisSCInvoices;
            totalPrevHCClaims += prevHCClaims;
            totalThisHCClaims += thisHCClaims;
            totalPrevQSClaims += prevQSClaims;
            totalThisQSClaims += thisQSClaims;
            totalAdjustment += adjustment;
        }
    });

    // Function to format numbers with commas
    function formatNumber(num) {
        return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
    }

    // Update the total row at the bottom of the table
    var hcPrepSheetTotalRow = $('#hcPrepSheetTotalRow');
    hcPrepSheetTotalRow.find('td').eq(2).html(totalContractBudget.toFixed(2) == 0.00 ? '-' : '<strong>' + formatNumber(totalContractBudget.toFixed(2)) + '</strong>');
    hcPrepSheetTotalRow.find('td').eq(3).html(totalWorkingBudget.toFixed(2) == 0.00 ? '-' : '<strong>' + formatNumber(totalWorkingBudget.toFixed(2)) + '</strong>');
    hcPrepSheetTotalRow.find('td').eq(4).html(totalUncommitted.toFixed(2) == 0.00 ? '-' : '<strong>' + formatNumber(totalUncommitted.toFixed(2)) + '</strong>');
    hcPrepSheetTotalRow.find('td').eq(5).html(totalCommitted.toFixed(2) == 0.00 ? '-' : '<strong>' + formatNumber(totalCommitted.toFixed(2)) + '</strong>');
    hcPrepSheetTotalRow.find('td').eq(6).html(totalFixedOnSiteCurrent.toFixed(2) == 0.00 ? '-' : '<strong>' + formatNumber(totalFixedOnSiteCurrent.toFixed(2)) + '</strong>');
    hcPrepSheetTotalRow.find('td').eq(7).html(totalFixedOnSitePrevious.toFixed(2) == 0.00 ? '-' : '<strong>' + formatNumber(totalFixedOnSitePrevious.toFixed(2)) + '</strong>');
    hcPrepSheetTotalRow.find('td').eq(8).html(totalFixedOnSiteThis.toFixed(2) == 0.00 ? '-' : '<strong>' + formatNumber(totalFixedOnSiteThis.toFixed(2)) + '</strong>');
    hcPrepSheetTotalRow.find('td').eq(9).html(totalPrevSCInvoices.toFixed(2) == 0.00 ? '-' : '<strong>' + formatNumber(totalPrevSCInvoices.toFixed(2)) + '</strong>');
    hcPrepSheetTotalRow.find('td').eq(10).html(totalThisSCInvoices.toFixed(2) == 0.00 ? '-' : '<strong>' + formatNumber(totalThisSCInvoices.toFixed(2)) + '</strong>');
    hcPrepSheetTotalRow.find('td').eq(12).html(totalPrevHCClaims.toFixed(2) == 0.00 ? '-' : '<strong>' + formatNumber(totalPrevHCClaims.toFixed(2)) + '</strong>');
    hcPrepSheetTotalRow.find('td').eq(13).html(totalThisHCClaims.toFixed(2) == 0.00 ? '-' : '<strong>' + formatNumber(totalThisHCClaims.toFixed(2)) + '</strong>');
    hcPrepSheetTotalRow.find('td').eq(14).html(totalPrevQSClaims.toFixed(2) == 0.00 ? '-' : '<strong>' + formatNumber(totalPrevQSClaims.toFixed(2)) + '</strong>');
    hcPrepSheetTotalRow.find('td').eq(15).html(totalThisQSClaims.toFixed(2) == 0.00 ? '-' : '<strong>' + formatNumber(totalThisQSClaims.toFixed(2)) + '</strong>');
    hcPrepSheetTotalRow.find('td').eq(11).html(totalAdjustment.toFixed(2) == 0.00 ? '-' : '<strong>' + formatNumber(totalAdjustment.toFixed(2)) + '</strong>');

    // Summarize totals for each group
    var sumContractBudget = 0;
    var sumWorkingBudget = 0;
    var sumUncommitted = 0;
    var sumCommitted = 0;
    var sumFixedOnSiteCurrent = 0;
    var sumFixedOnSitePrevious = 0;
    var sumFixedOnSiteThis = 0;
    var sumPrevSCInvoices = 0;
    var sumThisSCInvoices = 0;
    var sumPrevHCClaims = 0;
    var sumThisHCClaims = 0;
    var sumPrevQSClaims = 0;
    var sumThisQSClaims = 0;
    var sumAdjustment = 0;

    // Loop through all rows in the group and calculate sums
    $('.unique-group' + groupNumber).each(function () {
        var cells = $(this).find('td');
        if (cells.length >= 16) {
            var contractBudget = parseFloat(cells.eq(2).text().replace(/,/g, '').trim()) || 0;
            var workingBudget = parseFloat(cells.eq(3).text().replace(/,/g, '').trim()) || 0;
            var uncommitted = parseFloat(cells.eq(4).text().replace(/,/g, '').trim()) || 0;
            var committed = parseFloat(cells.eq(5).text().replace(/,/g, '').trim()) || 0;
            var fixedOnSiteCurrent = parseFloat(cells.eq(6).text().replace(/,/g, '').trim()) || 0;
            var fixedOnSitePrevious = parseFloat(cells.eq(7).text().replace(/,/g, '').trim()) || 0;
            var fixedOnSiteThis = parseFloat(cells.eq(8).text().replace(/,/g, '').trim()) || 0;
            var prevSCInvoices = parseFloat(cells.eq(9).text().replace(/,/g, '').trim()) || 0;
            var thisSCInvoices = parseFloat(cells.eq(10).text().replace(/,/g, '').trim()) || 0;
            var prevHCClaims = parseFloat(cells.eq(12).text().replace(/,/g, '').trim()) || 0;
            var thisHCClaims = parseFloat(cells.eq(13).text().replace(/,/g, '').trim()) || 0;
            var prevQSClaims = parseFloat(cells.eq(14).text().replace(/,/g, '').trim()) || 0;
            var thisQSClaims = parseFloat(cells.eq(15).text().replace(/,/g, '').trim()) || 0;
            var adjustment = parseFloat(cells.eq(11).find('input').val().replace(/,/g, '').trim()) || 0;

            // Accumulate group sums
            sumContractBudget += contractBudget;
            sumWorkingBudget += workingBudget;
            sumUncommitted += uncommitted;
            sumCommitted += committed;
            sumFixedOnSiteCurrent += fixedOnSiteCurrent;
            sumFixedOnSitePrevious += fixedOnSitePrevious;
            sumFixedOnSiteThis += fixedOnSiteThis;
            sumPrevSCInvoices += prevSCInvoices;
            sumThisSCInvoices += thisSCInvoices;
            sumPrevHCClaims += prevHCClaims;
            sumThisHCClaims += thisHCClaims;
            sumPrevQSClaims += prevQSClaims;
            sumThisQSClaims += thisQSClaims;
            sumAdjustment += adjustment;
        }
    });

    // Update the header row with the calculated sums for the group
    var row = $('[data-target=".unique-group' + groupNumber + '"]').closest('tr');
    row.find('td').eq(2).html(sumContractBudget.toFixed(2) == 0.00 ? '-' : '<strong>' + formatNumber(sumContractBudget.toFixed(2)) + '</strong>');
    row.find('td').eq(3).html(sumWorkingBudget.toFixed(2) == 0.00 ? '-' : '<strong>' + formatNumber(sumWorkingBudget.toFixed(2)) + '</strong>');
    row.find('td').eq(4).html(sumUncommitted.toFixed(2) == 0.00 ? '-' : '<strong>' + formatNumber(sumUncommitted.toFixed(2)) + '</strong>');
    row.find('td').eq(5).html(sumCommitted.toFixed(2) == 0.00 ? '-' : '<strong>' + formatNumber(sumCommitted.toFixed(2)) + '</strong>');
    row.find('td').eq(6).html(sumFixedOnSiteCurrent.toFixed(2) == 0.00 ? '-' : '<strong>' + formatNumber(sumFixedOnSiteCurrent.toFixed(2)) + '</strong>');
    row.find('td').eq(7).html(sumFixedOnSitePrevious.toFixed(2) == 0.00 ? '-' : '<strong>' + formatNumber(sumFixedOnSitePrevious.toFixed(2)) + '</strong>');
    row.find('td').eq(8).html(sumFixedOnSiteThis.toFixed(2) == 0.00 ? '-' : '<strong>' + formatNumber(sumFixedOnSiteThis.toFixed(2)) + '</strong>');
    row.find('td').eq(9).html(sumPrevSCInvoices.toFixed(2) == 0.00 ? '-' : '<strong>' + formatNumber(sumPrevSCInvoices.toFixed(2)) + '</strong>');
    row.find('td').eq(10).html(sumThisSCInvoices.toFixed(2) == 0.00 ? '-' : '<strong>' + formatNumber(sumThisSCInvoices.toFixed(2)) + '</strong>');
    row.find('td').eq(12).html(sumPrevHCClaims.toFixed(2) == 0.00 ? '-' : '<strong>' + formatNumber(sumPrevHCClaims.toFixed(2)) + '</strong>');
    row.find('td').eq(13).html(sumThisHCClaims.toFixed(2) == 0.00 ? '-' : '<strong>' + formatNumber(sumThisHCClaims.toFixed(2)) + '</strong>');
    row.find('td').eq(14).html(sumPrevQSClaims.toFixed(2) == 0.00 ? '-' : '<strong>' + formatNumber(sumPrevQSClaims.toFixed(2)) + '</strong>');
    row.find('td').eq(15).html(sumThisQSClaims.toFixed(2) == 0.00 ? '-' : '<strong>' + formatNumber(sumThisQSClaims.toFixed(2)) + '</strong>');
    row.find('td').eq(11).html(sumAdjustment.toFixed(2) == 0.00 ? '-' : '<strong>' + formatNumber(sumAdjustment.toFixed(2)) + '</strong>');
}

        // Event handler for the collapse/expand functionality
        $('[data-toggle="unique-collapse"]').on('click', function() {
            // Toggle the collapsed state
            $(this).toggleClass('unique-collapsed');
    
            // Get the group number
            var groupNumber = $(this).data('target').replace('.unique-group', '');
    
            // Toggle the visibility of the child rows
            $('.unique-group' + groupNumber).collapse('toggle');
    
            // Update the arrow direction
            updateArrowDirection($(this));
    
            // Calculate totals when expanded
            if (!$(this).hasClass('unique-collapsed')) {
                // calculateTotals(groupNumber);
            }
        });
    
        // Calculate totals and update arrow direction when modal loads
        $('#hcPrepSheetModal').on('shown.bs.modal', function() {
            $('[data-toggle="unique-collapse"]').each(function() {
                var groupNumber = $(this).data('target').replace('.unique-group', '');
                calculateTotals(groupNumber);
                updateArrowDirection($(this));
            });
        }); 

        
        function gatherAndPostHCClaimData(currentHcClaimId) {
            let data = [];
            // Loop through each row in the table body (except the total row)
            $('table.myTable tbody tr:not(#hcPrepSheetTotalRow)').each(function () {
                let row = $(this);
                // Retrieve the category name (grouper) and item primary keys from data attributes
                let category = row.find('td').eq(0).data('category');  // Use category.grouper now
                let itemId = row.find('td').eq(1).data('item-id');
                // Skip rows where category or item_id is undefined (these are the summary rows)
                if (category === undefined || itemId === undefined) {
                    return;  // Skip to the next row
                }
                // Continue collecting other values
                let contractBudget = parseFloat(row.find('td').eq(2).text().replace(/,/g, '')) || 0;
                let workingBudget = parseFloat(row.find('td').eq(3).text().replace(/,/g, '')) || 0;
                let uncommitted = parseFloat(row.find('td').eq(4).text().replace(/,/g, '')) || 0;
                let committed = parseFloat(row.find('td').eq(5).text().replace(/,/g, '')) || 0;
                let fixedOnSiteCurrent = parseFloat(row.find('td').eq(6).text().replace(/,/g, '')) || 0;
                let fixedOnSitePrev = parseFloat(row.find('td').eq(7).text().replace(/,/g, '')) || 0;
                let fixedOnSiteThis = parseFloat(row.find('td').eq(8).text().replace(/,/g, '')) || 0;
                let scPrevClaims = parseFloat(row.find('td').eq(9).text().replace(/,/g, '')) || 0;
                let scThisClaim = parseFloat(row.find('td').eq(10).text().replace(/,/g, '')) || 0;
                let adjustment = parseFloat(row.find('td').eq(11).find('input').val()) || 0;
                let hcPrevClaims = parseFloat(row.find('td').eq(12).text().replace(/,/g, '')) || 0;
                let hcThisClaim = parseFloat(row.find('td').eq(13).text().replace(/,/g, '')) || 0;
                let qsPrevClaims = parseFloat(row.find('td').eq(14).text().replace(/,/g, '')) || 0;
                let qsThisClaim = parseFloat(row.find('td').eq(15).text().replace(/,/g, '')) || 0;
        
                // Push data to array
                data.push({
                    'category': category,  // Store the category name instead of the ID
                    'item_id': itemId,
                    'contract_budget': contractBudget,
                    'working_budget': workingBudget,
                    'uncommitted': uncommitted,
                    'committed': committed,
                    'fixed_on_site_current': fixedOnSiteCurrent,
                    'fixed_on_site_previous': fixedOnSitePrev,
                    'fixed_on_site_this': fixedOnSiteThis,
                    'sc_invoiced_previous': scPrevClaims,
                    'sc_invoiced': scThisClaim,
                    'adjustment': adjustment,
                    'hc_claimed_previous': hcPrevClaims,
                    'hc_claimed': hcThisClaim,
                    'qs_claimed_previous': qsPrevClaims,
                    'qs_claimed': qsThisClaim,
                });
            });
            // Console log the entire data object before sending it
            console.log("Final data gathered: ", data);
            $.ajax({
                type: "POST",
                url: "/update_hc_claim_data/",
                data: JSON.stringify({ // Convert the data to JSON
                    'csrfmiddlewaretoken': $('input[name="csrfmiddlewaretoken"]').val(),
                    'hc_claim_data': data,
                    'current_hc_claim_display_id': currentHcClaimId
                }),
                contentType: "application/json", // Ensure it's sent as JSON
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
        
        $(document).ready(function() {
            $('#saveAdjustmentsButton').on('click', function(event) {
                event.preventDefault();  // Prevent form submission/page reload
                gatherAndPostHCClaimData(0);  // Pass 0 for save adjustments
            });
            $('#finalise_hc_claim_btn').on('click', function(event) {
                event.preventDefault();  // Prevent form submission/page reload
                let claimId = $(this).data('claim-id');  // Get the claim ID from the data attribute
                gatherAndPostHCClaimData(claimId);  // Pass the actual claim ID for finalisation
            });
        });
        
    // Make sure this script runs after the DOM is fully loaded
    document.addEventListener('DOMContentLoaded', function() {
        // Select all elements with the class or attribute that corresponds to the 'View' link
        var links = document.querySelectorAll('.view-pdf-link'); // Replace with the appropriate class/attribute
        // Add an event listener to each link
        links.forEach(function(link) {
            link.addEventListener('click', function(event) {
                event.preventDefault();
                var claimId = this.getAttribute('data-claim-id');
                if (claimId) {
                    // Set the iframe source to point to the correct endpoint with claimId as part of the URL
                    document.getElementById('existingClaimsPdfViewer').src = '/get_claim_table/' + claimId + '/';

                    // Show the modal
                    $('#existingClaimsModal').modal('show');
                } else {
                    alert('Invalid claim ID.');
                }
            });
        });
    });

    document.querySelectorAll('.preview-table-link').forEach(function(element) {
        console.log('Adding event listener to:', element);
        element.addEventListener('click', function(event) {
            event.preventDefault();
            console.log('Preview link clicked');
            var claimId = this.getAttribute('data-preview-claim-id');
            console.log('Claim ID:', claimId);
            var iframe = document.getElementById('existingClaimsPdfViewer');
            if (iframe) {
                console.log('Iframe found');
                iframe.contentDocument.body.innerHTML = '<div style="font-size: medium; text-align: center;">You have clicked HC claim # ' + claimId + '</div>';
            } else {
                console.log('Iframe not found');
            }
        });
    });     

});
