function formatNumber(num) {
    if (num === null || num === undefined) return '0.00';
    return parseFloat(num).toLocaleString('en-US', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    });
}

let clientContacts = [];

document.addEventListener('DOMContentLoaded', function() {
    const claim_category_totals = JSON.parse(document.getElementById('claim-category-totals').textContent);
    const category_summary = JSON.parse(document.getElementById('category_summary').textContent);
    function formatNumber(num) {
        if (typeof num !== 'number') {
            num = parseFloat(num) || 0;
        }
        return new Intl.NumberFormat('en-AU', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        }).format(num);
    }
    function formatDate(dateString) {
        const date = new Date(dateString);
        return date.toLocaleDateString('en-AU', { day: '2-digit', month: '2-digit', year: 'numeric' });
    }
    function processClaimView(claim, claimId) {
        const claimTotals = claim_category_totals.find(ct => ct.hc_claim_pk === claim.hc_claim_pk);
        const iframe = document.getElementById('existingClaimsPdfViewer');
        if (!iframe) {
            console.error("Iframe not found");
            return;
        }
        const thisClaimTotal = claimTotals?.categories?.reduce((sum, cat) => sum + (Number(cat.total_hc_claimed) || 0), 0) || 0;
        const claimDate = claim.date ? new Date(claim.date) : new Date();
        const contractBudgets = {};
        const uniqueCategories = new Set();
        const contractBudgetClaim = claim_category_totals.find(ct => ct.display_id === 'Contract Budget' && ct.hc_claim_pk === 0);
        if (contractBudgetClaim && contractBudgetClaim.categories) {
            contractBudgetClaim.categories.forEach(cat => {
                const value = Number(cat.total_hc_claimed);
                contractBudgets[cat.category] = value;
                uniqueCategories.add(cat.category);
            });
            if (claimTotals && claimTotals.categories) {
                claimTotals.categories.forEach(cat => {
                    if (!contractBudgets.hasOwnProperty(cat.category)) {
                        contractBudgets[cat.category] = 0;
                        uniqueCategories.add(cat.category);
                    }
                });
            }
        } else {
            console.warn("No contract budget claim found or no categories");
            if (claimTotals && claimTotals.categories) {
                claimTotals.categories.forEach(cat => {
                    contractBudgets[cat.category] = 0;
                    uniqueCategories.add(cat.category);
                });
            }
        }
        let categoryTotalsHtml = `
            <table style="width: 100%; border-collapse: collapse; font-size: 0.75rem; margin-top: 0.7rem;">
                <thead>
                    <tr style="background-color: #f8f9fa;">
                        <th style="padding: 0.15rem 0.3rem; text-align: left; border-bottom: 1px solid #dee2e6;">Category List</th>
                        <th style="padding: 0.15rem 0.3rem; text-align: right; border-bottom: 1px solid #dee2e6;">Contract Budget</th>
                        <th style="padding: 0.15rem 0.3rem; text-align: right; border-bottom: 1px solid #dee2e6;">This Claim</th>
                        <th style="padding: 0.15rem 0.3rem; text-align: right; border-bottom: 1px solid #dee2e6;">Total Claimed</th>
                        <th style="padding: 0.15rem 0.3rem; text-align: right; border-bottom: 1px solid #dee2e6;">Still to Claim</th>
                        ${hc_claims
                            .filter(c => parseInt(c.display_id) < parseInt(claim.display_id))
                            .sort((a, b) => parseInt(a.display_id) - parseInt(b.display_id))
                            .map(c => `<th style="padding: 0.15rem 0.3rem; text-align: right; border-bottom: 1px solid #dee2e6;">Claim #${c.display_id}</th>`)
                            .join('')}
                    </tr>
                </thead>
                <tbody>
        `;
        const columnTotals = {
            contractBudget: 0,
            thisClaim: 0,
            totalClaimed: 0,
            previousClaims: {}
        };
        Array.from(uniqueCategories).sort().forEach(categoryName => {
            const summary = category_summary[categoryName] || {};
            const categoryTotal = claimTotals?.categories?.find(cat => cat.category === categoryName)?.total_hc_claimed || 0;
            const contractBudgetTotal = contractBudgets[categoryName] || 0;
            columnTotals.contractBudget += Number(contractBudgetTotal);
            columnTotals.thisClaim += Number(categoryTotal);
            columnTotals.totalClaimed += Number(summary.total_claimed || 0);
            const previousClaimsHtml = hc_claims
                .filter(c => parseInt(c.display_id) < parseInt(claim.display_id))
                .sort((a, b) => parseInt(a.display_id) - parseInt(b.display_id))
                .map(c => {
                    const prevClaimTotal = claim_category_totals
                        .find(ct => ct.display_id === c.display_id)
                        ?.categories?.find(cat => cat.category === categoryName)
                        ?.total_hc_claimed || 0;
                    if (!columnTotals.previousClaims[c.display_id]) {
                        columnTotals.previousClaims[c.display_id] = 0;
                    }
                    columnTotals.previousClaims[c.display_id] += Number(prevClaimTotal);
                    return `<td style="padding: 0.15rem 0.3rem; text-align: right; border-bottom: 1px solid #eee;">$${formatNumber(prevClaimTotal)}</td>`;
                })
                .join('');
            categoryTotalsHtml += `
                <tr>
                    <td style="padding: 0.15rem 0.3rem; border-bottom: 1px solid #eee;">${categoryName}</td>
                    <td style="padding: 0.15rem 0.3rem; text-align: right; border-bottom: 1px solid #eee;">$${formatNumber(contractBudgetTotal)}</td>
                    <td style="padding: 0.15rem 0.3rem; text-align: right; border-bottom: 1px solid #eee;">$${formatNumber(categoryTotal)}</td>
                    <td style="padding: 0.15rem 0.3rem; text-align: right; border-bottom: 1px solid #eee;">$${formatNumber(summary.total_claimed || 0)}</td>
                    <td style="padding: 0.15rem 0.3rem; text-align: right; border-bottom: 1px solid #eee;">$${formatNumber(contractBudgetTotal - (summary.total_claimed || 0))}</td>
                    ${previousClaimsHtml}
                </tr>
            `;
        });
        categoryTotalsHtml += `
            <tr style="border-top: 2px solid #dee2e6; font-weight: bold; background-color: #f8f9fa;">
                <td style="padding: 0.15rem 0.3rem;">Total</td>
                <td style="padding: 0.15rem 0.3rem; text-align: right;">$${formatNumber(columnTotals.contractBudget)}</td>
                <td style="padding: 0.15rem 0.3rem; text-align: right;">$${formatNumber(columnTotals.thisClaim)}</td>
                <td style="padding: 0.15rem 0.3rem; text-align: right;">$${formatNumber(columnTotals.totalClaimed)}</td>
                <td style="padding: 0.15rem 0.3rem; text-align: right;">$${formatNumber(columnTotals.contractBudget - columnTotals.totalClaimed)}</td>
                ${Object.entries(columnTotals.previousClaims)
                    .sort(([idA], [idB]) => parseInt(idA) - parseInt(idB))
                    .map(([, total]) => `<td style="padding: 0.15rem 0.3rem; text-align: right;">$${formatNumber(total)}</td>`)
                    .join('')}
            </tr>
        `;
        categoryTotalsHtml += `</tbody></table>`;
        iframe.contentDocument.body.innerHTML = `
            <div style="font-size: 0.75rem; text-align: left; margin: 0.5rem; line-height: 1.1;">
                <div style="text-align: center; margin: 0 0 1rem 0; color: #2c3e50; font-size: 1.1rem; font-weight: bold;">HC Claim Summary #${claimId}</div>
                <div style="background: #f8f9fa; padding: 0.4rem; border-radius: 3px; box-shadow: 0 1px 2px rgba(0,0,0,0.05);">
                    <div style="margin-bottom: 0.7rem; border-bottom: 1px solid #dee2e6; padding-bottom: 0.4rem; font-size: 0.85rem;">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <span><strong>HC Total:</strong> $${formatNumber(thisClaimTotal)}</span>
                            <span style="margin-left: 2rem;"><strong>HC Date:</strong> ${formatDate(claimDate)}</span>
                        </div>
                    </div>
                    ${categoryTotalsHtml}
                </div>
            </div>`;
    }
    const hcDropdown = document.getElementById('hcDropdown');
    if (hcDropdown) {
        hcDropdown.addEventListener('change', function(e) {
            if (e.target.value === 'existingClaims') {
                $('#existingClaimsModal').modal('show');
                updateExistingClaimsTable();
            }
        });
    }
    const claimsDropdown = document.getElementById('claimsDropdownInvoices');
    if (claimsDropdown) {
        claimsDropdown.addEventListener('change', function(e) {
            if (e.target.value === 'existingClaims') {
                $('#unallocatedInvoicesModal').modal('show');
            }
        });
    }
    document.querySelectorAll('.view-table-link').forEach(function(element) {
        element.addEventListener('click', function(event) {
            event.preventDefault();
            const claimId = this.getAttribute('data-hc-claim-sheet-view-claim-id') || this.getAttribute('data-qs-claim-sheet-view-claim-id');
            if (claimId) {
                const displayId = parseInt(claimId);
                const claim = hc_claims.find(c => parseInt(c.display_id) === displayId);
                if (claim) {
                    processClaimView(claim, claimId);
                } else {
                    console.error("Claim not found for ID:", claimId);
                }
            }
        });
    });
});

function createClaimRow(claim) {
    const row = $('<tr>').css('line-height', '1');
    row.append($('<td>').text(claim.display_id).css('padding', '4px'));
    
    const clientCell = $('<td>').css('padding', '4px').css('width', '10%');
    if (claim.status >= 2) {
        const invoicee = claim.invoicee || '';
        const truncatedName = invoicee.substring(0, 30) + (invoicee.length > 30 ? '...' : '');
        clientCell.text(truncatedName);
    } else {
        const dropdown = $('<select>')
            .addClass('client-dropdown')
            .attr('data-claim-id', claim.hc_claim_pk)
            .css({
                'width': '100%',
                'white-space': 'nowrap',
                'overflow': 'hidden',
                'text-overflow': 'ellipsis'
            });
        dropdown.append($('<option>').val('').text('Select Client'));
        const clientContacts = contacts_unfiltered.filter(contact => contact.checked === 2 || contact.checked === 3);
        clientContacts.forEach(client => {
            dropdown.append($('<option>').val(client.contact_pk).text(client.contact_name));
        });
        clientCell.append(dropdown);
    }
    row.append(clientCell);
    
    row.append($('<td>').text(formatDate(claim.date)).css('padding', '4px'));
    row.append($('<td>').text(formatNumber(claim.sc_invoiced_total || 0)).css('padding', '4px'));
    row.append($('<td>').text(formatNumber(claim.hc_claimed_total || 0)).css('padding', '4px'));
    
    const hcClaimCell = $('<td>').css('padding', '4px');
    if (claim.status > 0) {
        const viewLink = $('<a>')
            .attr('href', '#')
            .addClass('view-table-link')
            .attr('data-hc-claim-sheet-view-claim-id', claim.display_id)
            .text('View HC Claim')
            .on('click', function(e) {
                e.preventDefault();
                const claimTotals = claim_category_totals.find(ct => ct.hc_claim_pk === claim.hc_claim_pk);
                const contractBudgetClaim = claim_category_totals.find(
                    ct => ct.hc_claim_pk === 0 && ct.display_id === 'Contract Budget'
                );
                
                let budgetDict = {};
                if (contractBudgetClaim && contractBudgetClaim.categories) {
                    contractBudgetClaim.categories.forEach(budgetCat => {
                        budgetDict[budgetCat.category] = parseFloat(budgetCat.total_hc_claimed) || 0;
                    });
                }
                
                if (claimTotals) {
                    // Sum of all category totals for THIS claim_pk
                    const thisClaimTotal = claimTotals.categories.reduce(
                        (sum, cat) => sum + (parseFloat(cat.total_hc_claimed) || 0),
                        0
                    );
                    
                    let tableHtml = `
                        <table style="width: 100%; border-collapse: collapse; font-size: 0.75rem; margin-top: 0.7rem;">
                            <thead>
                                <tr style="background-color: #f8f9fa;">
                                    <th style="padding: 0.15rem 0.3rem; text-align: left; border-bottom: 1px solid #dee2e6; white-space: nowrap;">Category List</th>
                                    <th style="padding: 0.15rem 0.3rem; text-align: right; border-bottom: 1px solid #dee2e6; white-space: nowrap;">Contract Budget</th>
                                    <th style="padding: 0.15rem 0.3rem; text-align: right; border-bottom: 1px solid #dee2e6; white-space: nowrap;">This Claim</th>
                                    <th style="padding: 0.15rem 0.3rem; text-align: right; border-bottom: 1px solid #dee2e6; white-space: nowrap;">Total Claimed</th>
                                    <th style="padding: 0.15rem 0.3rem; text-align: right; border-bottom: 1px solid #dee2e6; white-space: nowrap;">Still to Claim</th>
                                </tr>
                            </thead>
                            <tbody>
                    `;
                    
                    let totals = {
                        contractBudget: 0,
                        thisClaim: 0,
                        totalClaimed: 0,
                        stillToClaim: 0
                    };
                    
                    claimTotals.categories.forEach(cat => {
                        const catName = cat.category;
                        const contractBudget = budgetDict[catName] || 0;
                        const thisClaim = parseFloat(cat.total_hc_claimed || 0);
                        // Sum total_hc_claimed for hc_claim_pk <= the current claim's hc_claim_pk
                        const totalClaimed = claim_category_totals
                            .filter(ct => ct.hc_claim_pk > 0 && ct.hc_claim_pk <= claim.hc_claim_pk)
                            .reduce((sum, item) => {
                                const foundCat = item.categories.find(x => x.category === catName);
                                return sum + (foundCat ? parseFloat(foundCat.total_hc_claimed) || 0 : 0);
                            }, 0);
                        const stillToClaim = Math.max(0, contractBudget - totalClaimed);
                        totals.contractBudget += contractBudget;
                        totals.thisClaim += thisClaim;
                        totals.totalClaimed += totalClaimed;
                        totals.stillToClaim += stillToClaim;
                        tableHtml += `
                            <tr>
                                <td style="padding: 0.15rem 0.3rem; text-align: left;">${catName}</td>
                                <td style="padding: 0.15rem 0.3rem; text-align: right;">$${formatNumber(contractBudget)}</td>
                                <td style="padding: 0.15rem 0.3rem; text-align: right;">$${formatNumber(thisClaim)}</td>
                                <td style="padding: 0.15rem 0.3rem; text-align: right;">$${formatNumber(totalClaimed)}</td>
                                <td style="padding: 0.15rem 0.3rem; text-align: right;">$${formatNumber(stillToClaim)}</td>
                            </tr>
                        `;
                    });
                    
                    tableHtml += `
                        <tr style="border-top: 2px solid #dee2e6; font-weight: bold; background-color: #f8f9fa;">
                            <td style="padding: 0.15rem 0.3rem;">Total</td>
                            <td style="padding: 0.15rem 0.3rem; text-align: right;">$${formatNumber(totals.contractBudget)}</td>
                            <td style="padding: 0.15rem 0.3rem; text-align: right;">$${formatNumber(totals.thisClaim)}</td>
                            <td style="padding: 0.15rem 0.3rem; text-align: right;">$${formatNumber(totals.totalClaimed)}</td>
                            <td style="padding: 0.15rem 0.3rem; text-align: right;">$${formatNumber(totals.stillToClaim)}</td>
                        </tr>
                    `;
                    
                    tableHtml += '</tbody></table>';
                    
                    // Add a heading before the table
                    const headingHtml = `
                        <div style="text-align: center; margin-bottom: 1rem;">
                            <h3 style="margin: 0 0 0.5rem 0;">Claim Sheet: Claim #${claim.display_id}</h3>
                            <p style="margin: 0.3rem 0;">Claim Total: $${formatNumber(thisClaimTotal)}</p>
                            <p style="margin: 0.3rem 0;">Claim Date: ${formatDate(claim.date)}</p>
                        </div>
                    `;
                    
                    const htmlString = `
                        <html>
                            <head>
                                <style>
                                    body { font-family: Arial, sans-serif; }
                                    table { border-collapse: collapse; width: 100%; }
                                    th, td {
                                        padding: 0.15rem 0.3rem; 
                                        border-bottom: 1px solid #dee2e6;
                                    }
                                    th {
                                        text-align: left; 
                                        white-space: nowrap;
                                    }
                                    td {
                                        text-align: right;
                                    }
                                </style>
                            </head>
                            <body>
                                ${headingHtml}
                                ${tableHtml}
                            </body>
                        </html>
                    `;
                    
                    const iframe = document.getElementById('existingClaimsPdfViewer');
                    if (iframe) {
                        iframe.contentDocument.open();
                        iframe.contentDocument.write(htmlString);
                        iframe.contentDocument.close();
                    }
                }
            });
        hcClaimCell.append(viewLink);
    }
    row.append(hcClaimCell);
    
    row.append($('<td>').text(formatNumber(claim.qs_claimed_total || 0)).css('padding', '4px'));
    
    const qsClaimCell = $('<td>').css('padding', '4px');
    if (claim.status > 0) {
        const viewLink = $('<a>')
            .attr('href', '#')
            .addClass('view-table-link')
            .attr('data-qs-claim-sheet-view-claim-id', claim.display_id)
            .text('View QS Claim');
        qsClaimCell.append(viewLink);
    }
    row.append(qsClaimCell);
    
    const processCell = $('<td>').css('padding', '4px');
    if (claim.status === 0) {
        const processLink = $('<a>')
            .attr('href', '#')
            .attr('data-toggle', 'modal')
            .attr('data-target', '#hcPrepSheetModal')
            .text('Process')
            .on('click', function() {
                $('#existingClaimsModal').modal('hide');
            });
        processCell.append(processLink);
    }
    row.append(processCell);
    
    const xeroCell = $('<td>').css('padding', '4px');
    if (claim.status === 1) {
        const checkbox = $('<input>')
            .attr('type', 'checkbox')
            .addClass('send-to-xero-checkbox')
            .attr('data-claim-id', claim.hc_claim_pk);   // unify the attribute name
        xeroCell.append(checkbox);
    } else if (claim.status >= 2) {
        xeroCell.append($('<span>').css('color', 'green').html('&#10004;'));
    }
    row.append(xeroCell);
    
    return row;
}


function updateExistingClaimsTable() {
    const tableBody = $('#existingClaimsTable tbody');
    tableBody.empty();
    const claimsArray = Array.isArray(hc_claims) ? [...hc_claims] : [];
    claimsArray.sort((a, b) => parseInt(a.display_id) - parseInt(b.display_id));
    claimsArray.forEach((claim, index) => {
        const row = createClaimRow(claim);
        tableBody.append(row);
    });
}

$('#existingClaimsModal').on('shown.bs.modal', function () {});

$(document).ready(function() {
    const clientContacts = contacts_unfiltered.filter(contact => contact.checked === 2 || contact.checked === 3);
    $('.client-dropdown').each(function() {
        const dropdown = $(this);
        clientContacts.forEach(client => {
            dropdown.append(`<option value="${client.contact_pk}">${client.contact_name}</option>`);
        });
    });
    $(document).on('change', '.client-dropdown', function() {
        const claimId = $(this).data('claim-id');
        const selectedClientId = $(this).val();
        if (!selectedClientId) {
            return;
        }
        const selectedContact = contacts_unfiltered.find(contact => contact.contact_pk.toString() === selectedClientId);
        if (!selectedContact || !selectedContact.xero_contact_id) {
            alert('Selected client does not have a valid Xero contact ID');
            return;
        }
    });
});

$(document).on('change', '.send-to-xero-checkbox', function() {
    $('.send-to-xero-checkbox').not(this).prop('checked', false);
    const anyChecked = $('.send-to-xero-checkbox:checked').length > 0;
    $('#sendToXeroButton').prop('disabled', !anyChecked);
});

$('#sendToXeroButton').on('click', function() {
    const checkedBox = $('.send-to-xero-checkbox:checked');
    if (checkedBox.length === 0) {
        alert('Please select a claim to send to Xero');
        return;
    }
    const hc_claim_pk = parseInt(checkedBox.data('claim-id'));
    const dropdownSelector = `.client-dropdown[data-claim-id="${hc_claim_pk}"]`;
    const $dropdown = $(document).find(dropdownSelector);
    if (!$dropdown || $dropdown.length === 0) {
        alert('Could not find the client dropdown for this claim.');
        return;
    }
    const selectedClientId = $dropdown.val();
    if (!selectedClientId) {
        alert('Please select a client for this claim before sending to Xero');
        return;
    }
    const selectedContact = contacts_unfiltered.find(contact => contact.contact_pk.toString() === selectedClientId);
    if (!selectedContact || !selectedContact.xero_contact_id) {
        alert('Selected client does not have a valid Xero contact ID');
        return;
    }
    const claimTotalsObj = claim_category_totals.find(obj => obj.hc_claim_pk === hc_claim_pk);
    const categoryData = [];
    if (claimTotalsObj && claimTotalsObj.categories) {
        claimTotalsObj.categories.forEach(cat => {
            if (cat.total_hc_claimed && cat.total_hc_claimed > 0) {
                categoryData.push({
                    categories_pk: cat.categories_pk,  // PK is now available
                    amount: cat.total_hc_claimed
                });
            }
        });
    }
    fetch('/send_hc_claim_to_xero/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: JSON.stringify({
            hc_claim_pk: hc_claim_pk,
            xero_contact_id: selectedContact.xero_contact_id,
            contact_name: selectedContact.contact_name,
            categories: categoryData
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            checkedBox.closest('td').html('<span style="color: green;">&#10004;</span>');
            $('#sendToXeroButton').prop('disabled', true);
            alert('Successfully sent to Xero');
            location.reload();
        } else {
            alert('Error sending to Xero: ' + data.error);
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Error sending to Xero');
    });
});


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
