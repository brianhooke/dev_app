// Add html2pdf library
const html2pdfScript = document.createElement('script');
html2pdfScript.src = 'https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js';
document.head.appendChild(html2pdfScript);

document.addEventListener('DOMContentLoaded', () => {
    // Add download button event listener
    document.getElementById('downloadClaimSummary').addEventListener('click', () => {
        const iframe = document.getElementById('existingClaimsPdfViewer');
        const content = iframe.contentDocument.body;
        
        const opt = {
            margin: 10,
            filename: `claim_summary_${new Date().toISOString().split('T')[0]}.pdf`,
            image: { type: 'jpeg', quality: 0.98 },
            html2canvas: { scale: 2 },
            jsPDF: { unit: 'mm', format: 'a4', orientation: 'portrait' }
        };
        
        html2pdf().set(opt).from(content).save();
    });

    const hcDropdown = document.getElementById('hcDropdown');
    if (hcDropdown) {
        hcDropdown.addEventListener('change', (e) => {
            if (e.target.value === 'existingClaims') {
                $('#existingClaimsModal').modal('show');
                updateExistingClaimsTable();
            }
        });
    }

    // Reset dropdown when modals are closed
    $('#existingClaimsModal, #hcPrepSheetModal').on('hidden.bs.modal', function() {
        console.log('Modal closed, resetting hcDropdown to HCClaims');
        $('#hcDropdown').val('HCClaims');
    });
});

// Globals 
function formatNumber(num) {
    if (num === null || num === undefined) return '0.00';
    return parseFloat(num).toLocaleString('en-US', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    });
}

function formatDate(date) {
    if (!(date instanceof Date)) {
        date = new Date(date);
    }
    const day = date.getDate().toString().padStart(2, '0');
    const month = date.toLocaleString('en-US', { month: 'short' });
    const year = date.getFullYear().toString().slice(-2);
    return `${day}-${month}-${year}`;
}

function updateExistingClaimsTable() {
    const tableBody = $('#existingClaimsTable tbody');
    tableBody.empty();
    const claimsArray = Array.isArray(hc_claims) ? [...hc_claims] : [];
    claimsArray.sort((a, b) => parseInt(a.display_id) - parseInt(b.display_id));
    claimsArray.forEach((claim, index) => {
        const row = generateExitingClaimsModalData(claim);
        tableBody.append(row);
    });
}

function generateExitingClaimsModalData(claim) {
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
    row.append($('<td>').text(formatNumber(claim.sc_total || 0)).css('padding', '4px'));
    row.append($('<td>').text(formatNumber(claim.hc_total || 0)).css('padding', '4px'));
    row.append($('<td>').text(formatNumber(claim.qs_total || 0)).css('padding', '4px'));
    const hcClaimCell = $('<td>').css('padding', '4px');
    if (claim.status > 0) {
        const viewLink = $('<a>')
            .attr('href', '#')
            .addClass('view-table-link')
            .attr('data-hc-claim-sheet-view-claim-id', claim.display_id)
            .text('View HC Claim')
            .on('click', function(e) {
                e.preventDefault();
                generateClaimSheetTable(claim, claim.display_id, 'hc');
            });
        hcClaimCell.append(viewLink);
    }
    row.append(hcClaimCell);
    const qsClaimCell = $('<td>').css('padding', '4px');
    if (claim.status > 0) {
        const viewLink = $('<a>')
            .attr('href', '#')
            .addClass('view-table-link')
            .attr('data-qs-claim-sheet-view-claim-id', claim.display_id)
            .text('View QS Claim')
            .on('click', function(e) {
                e.preventDefault();
                generateClaimSheetTable(claim, claim.display_id, 'qs');
            });
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
        xeroCell.append($('<span>').css('color', 'green').html('✔'));
    }
    row.append(xeroCell);
    return row;
}

function generateClaimSheetTable(claim, claimId, claimType = 'hc') {
    console.log("Claim Type is", claimType);
    const claimField = claimType === 'hc' ? 'total_hc_claimed' : 'total_qs_claimed';
    const claimTotals = claim_category_totals.find(ct => ct.hc_claim_pk === claim.hc_claim_pk);
    const iframe = document.getElementById('existingClaimsPdfViewer');
    if (!iframe) {
        console.error("Iframe not found");
        return;
    }
    const thisClaimTotal = claimTotals?.categories?.reduce((sum, cat) => sum + (Number(cat.total_hc_claimed) || 0), 0) || 0;
    const claimDate = claim.date ? new Date(claim.date) : new Date();
    // Precompute arrays for the table columns
    const contractBudgetClaim = claim_category_totals.find(ct => ct.display_id === 'Contract Budget' && ct.hc_claim_pk === 0);
    let uniqueCategories = [];
    if (contractBudgetClaim && contractBudgetClaim.categories) {
        uniqueCategories = contractBudgetClaim.categories.map(cat => cat.category);
        if (claimTotals && claimTotals.categories) {
            claimTotals.categories.forEach(cat => {
                if (!uniqueCategories.includes(cat.category)) {
                    uniqueCategories.push(cat.category);
                }
            });
        }
    } else if (claimTotals && claimTotals.categories) {
        uniqueCategories = claimTotals.categories.map(cat => cat.category);
    }
    const categoriesList = uniqueCategories;
    const contractBudgetList = [];
    const thisClaimList = [];
    const totalClaimedList = [];

    categoriesList.forEach(categoryName => {
        // First try to get claim-specific contract_budget
        let cbValue = 0;
        const claimRecord = claim_category_totals.find(ct => ct.hc_claim_pk == claim.hc_claim_pk);
        if (claimRecord && claimRecord.categories) {
            const claimCbEntry = claimRecord.categories.find(cat => cat.category === categoryName);
            if (claimCbEntry && claimCbEntry.total_contract_budget !== undefined) {
                cbValue = Number(claimCbEntry.total_contract_budget);
            }
        }
        
        // Fallback to global contract budget if needed
        if (cbValue === 0) {
            const cbEntry = contractBudgetClaim && contractBudgetClaim.categories ? 
                contractBudgetClaim.categories.find(cat => cat.category === categoryName) : null;
            cbValue = cbEntry ? Number(cbEntry.total_hc_claimed) : 0;
        }
        
        contractBudgetList.push(cbValue);

        let thisValue = 0;
        claim_category_totals
            .filter(ct => ct.hc_claim_pk == claim.hc_claim_pk)
            .forEach(record => {
                if (record.categories) {
                    const entry = record.categories.find(cat => cat.category === categoryName);
                    if (entry) {
                        thisValue += Number(entry[claimField]) || 0;
                    }
                }
            });
        thisClaimList.push(thisValue);

        let totValue = 0;
        claim_category_totals
            .filter(ct => ct.display_id !== 'Contract Budget' && 
                   (ct.display_id === claim.display_id || 
                    (parseInt(ct.display_id) < parseInt(claim.display_id))))
            .forEach(record => {
                if (record.categories) {
                    const entry = record.categories.find(cat => cat.category === categoryName);
                    if (entry) {
                        totValue += Number(entry[claimField]) || 0;
                    }
                }
            });
        totalClaimedList.push(totValue);
    });

    let mainTableHtml = `
        <table style="width: 100%; border-collapse: collapse; font-size: 0.75rem; margin-top: 0.7rem;">
            <thead>
                <tr style="background-color: #f8f9fa;">
                    <th style="padding: 0.15rem 0.3rem; text-align: left; border-bottom: 1px solid #dee2e6;">Claim Category</th>
                    <th style="padding: 0.15rem 0.3rem; text-align: right; border-bottom: 1px solid #dee2e6;">Contract Budget</th>
                    <th style="padding: 0.15rem 0.3rem; text-align: right; border-bottom: 1px solid #dee2e6;">This Claim</th>
                    <th style="padding: 0.15rem 0.3rem; text-align: right; border-bottom: 1px solid #dee2e6;">Total Claimed</th>
                    <th style="padding: 0.15rem 0.3rem; text-align: right; border-bottom: 1px solid #dee2e6;">Still to Claim</th>
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
    // Generate main table rows
    categoriesList.forEach((categoryName, index) => {
        const cbValue = contractBudgetList[index];
        const thisValue = thisClaimList[index];
        const totValue = totalClaimedList[index];
        columnTotals.contractBudget += cbValue;
        columnTotals.thisClaim += thisValue;
        columnTotals.totalClaimed += totValue;

        mainTableHtml += `
            <tr>
                <td style="padding: 0.15rem 0.3rem; border-bottom: 1px solid #eee;">${categoryName}</td>
                <td style="padding: 0.15rem 0.3rem; text-align: right; border-bottom: 1px solid #eee;">$${formatNumber(cbValue)}</td>
                <td style="padding: 0.15rem 0.3rem; text-align: right; border-bottom: 1px solid #eee;">$${formatNumber(thisValue)}</td>
                <td style="padding: 0.15rem 0.3rem; text-align: right; border-bottom: 1px solid #eee;">$${formatNumber(totValue)}</td>
                <td style="padding: 0.15rem 0.3rem; text-align: right; border-bottom: 1px solid #eee;">$${formatNumber(cbValue - totValue)}</td>
            </tr>
        `;

        // Calculate previous claims totals
        hc_claims
            .filter(c => parseInt(c.display_id) < parseInt(claim.display_id))
            .sort((a, b) => parseInt(a.display_id) - parseInt(b.display_id))
            .forEach(c => {
                const prevClaimTotal = claim_category_totals
                    .find(ct => ct.display_id === c.display_id)
                    ?.categories
                    ?.find(cat => cat.category === categoryName)
                    ?.[claimType === 'qs' ? 'total_qs_claimed' : 'total_hc_claimed'] || 0;
                if (!columnTotals.previousClaims[c.display_id]) {
                    columnTotals.previousClaims[c.display_id] = 0;
                }
                columnTotals.previousClaims[c.display_id] += Number(prevClaimTotal);
            });
    });

    // Add totals row to main table
    mainTableHtml += `
        <tr style="border-top: 2px solid #dee2e6; font-weight: bold; background-color: #f8f9fa;">
            <td style="padding: 0.15rem 0.3rem;">Total</td>
            <td style="padding: 0.15rem 0.3rem; text-align: right;">$${formatNumber(columnTotals.contractBudget)}</td>
            <td style="padding: 0.15rem 0.3rem; text-align: right;">$${formatNumber(columnTotals.thisClaim)}</td>
            <td style="padding: 0.15rem 0.3rem; text-align: right;">$${formatNumber(columnTotals.totalClaimed)}</td>
            <td style="padding: 0.15rem 0.3rem; text-align: right;">$${formatNumber(columnTotals.contractBudget - columnTotals.totalClaimed)}</td>
        </tr>
    `;
    mainTableHtml += `</tbody></table>`;

    // Generate previous claims table
    const previousClaimsHtml = `
        <div style="margin-top: 2rem;"></div>
        <div style="text-align: center; margin: 0 0 1rem 0; color: #2c3e50; font-size: 1rem; font-weight: bold;">Prior Claims</div>
        <table style="width: 100%; border-collapse: collapse; font-size: 0.75rem; margin-top: 0.7rem;">
            <thead>
                <tr style="background-color: #f8f9fa;">
                    <th style="padding: 0.15rem 0.3rem; text-align: left; border-bottom: 1px solid #dee2e6;">Claim Category</th>
                    ${hc_claims
                        .filter(c => parseInt(c.display_id) < parseInt(claim.display_id))
                        .sort((a, b) => parseInt(a.display_id) - parseInt(b.display_id))
                        .map(c => `<th style="padding: 0.15rem 0.3rem; text-align: right; border-bottom: 1px solid #dee2e6;">Claim #${c.display_id}</th>`)
                        .join('')}
                </tr>
            </thead>
            <tbody>
                ${categoriesList.map(categoryName => `
                    <tr>
                        <td style="padding: 0.15rem 0.3rem; border-bottom: 1px solid #eee;">${categoryName}</td>
                        ${hc_claims
                            .filter(c => parseInt(c.display_id) < parseInt(claim.display_id))
                            .sort((a, b) => parseInt(a.display_id) - parseInt(b.display_id))
                            .map(c => {
                                const prevClaimTotal = claim_category_totals
                                    .find(ct => ct.display_id === c.display_id)
                                    ?.categories
                                    ?.find(cat => cat.category === categoryName)
                                    ?.[claimType === 'qs' ? 'total_qs_claimed' : 'total_hc_claimed'] || 0;
                                return `<td style="padding: 0.15rem 0.3rem; text-align: right; border-bottom: 1px solid #eee;">$${formatNumber(prevClaimTotal)}</td>`;
                            })
                            .join('')}
                    </tr>
                `).join('')}
                <tr style="border-top: 2px solid #dee2e6; font-weight: bold; background-color: #f8f9fa;">
                    <td style="padding: 0.15rem 0.3rem;">Total</td>
                    ${Object.entries(columnTotals.previousClaims)
                        .sort(([idA], [idB]) => parseInt(idA) - parseInt(idB))
                        .map(([, total]) => `<td style="padding: 0.15rem 0.3rem; text-align: right;">$${formatNumber(total)}</td>`)
                        .join('')}
                </tr>
            </tbody>
        </table>
    `;

    iframe.contentDocument.body.innerHTML = `
        <div style="font-size: 0.75rem; text-align: left; margin: 0.5rem; line-height: 1.1;">
            <div style="text-align: center; margin: 0 0 1rem 0; color: #2c3e50; font-size: 1.1rem; font-weight: bold;">${claimType === 'qs' ? 'QS' : 'HC'} Claim Summary #${claimId}</div>
            <div style="background: #f8f9fa; padding: 0.4rem; border-radius: 3px; box-shadow: 0 1px 2px rgba(0,0,0,0.05);">
                <div style="margin-bottom: 0.7rem; border-bottom: 1px solid #dee2e6; padding-bottom: 0.4rem; font-size: 0.85rem;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <span><strong>${claimType === 'qs' ? 'QS' : 'HC'} Total:</strong> $${formatNumber(thisClaimTotal)}</span>
                        <span style="margin-left: 2rem;"><strong>${claimType === 'qs' ? 'QS' : 'HC'} Date:</strong> ${formatDate(claimDate)}</span>
                    </div>
                </div>
                ${mainTableHtml}
                ${previousClaimsHtml}
            </div>
        </div>`;
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
            checkedBox.closest('td').html('<span style="color: green;">✔</span>');
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