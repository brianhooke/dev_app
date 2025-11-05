// HC Variations JavaScript - Part 2
// For handling existing variations functionality

// Add event listener to the HC Variations dropdown
$(document).ready(function() {
    // Listen for changes on the HC Variations dropdown
    $(document).on('change', '#hcVariationsDropdown', function() {
        if ($(this).val() === 'existingClaims') {
            // Show the existing variations modal
            $('#existingVariationsModal').modal('show');
            
            // Reset dropdown after a short delay
            setTimeout(() => {
                $(this)[0].selectedIndex = 0;
            }, 100);
        }
    });
    
    // Add download button event listener for variations
    $('#downloadVariationSummary').on('click', function() {
        console.log('Download variation button clicked');
        // Get the iframe content
        const iframe = document.getElementById('variationDetailPanel');
        if (!iframe) {
            console.error('Variation detail panel not found');
            return;
        }
        
        const iframeContent = iframe.contentDocument.body;
        
        // Check if there are details to download
        if (iframeContent.querySelector('.variation-details').style.display === 'none') {
            alert('Please select a variation to download details');
            return;
        }
        
        // Show downloading message
        alert('Downloading variation details...');
        
        // PDF download options
        const options = {
            margin: 10,
            filename: `variation_details_${new Date().toISOString().split('T')[0]}.pdf`,
            image: { type: 'jpeg', quality: 0.98 },
            html2canvas: { scale: 2 },
            jsPDF: { unit: 'mm', format: 'a4', orientation: 'portrait' }
        };
        
        // Generate and download PDF
        console.log('Generating PDF for variation details...');
        html2pdf().set(options).from(iframeContent).save();
    });
});

// Add html2pdf library if it's not already loaded
if (!document.querySelector('script[src*="html2pdf.bundle.min.js"]')) {
    const html2pdfScript = document.createElement('script');
    html2pdfScript.src = 'https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js';
    document.head.appendChild(html2pdfScript);
}

// Get CSRF token for AJAX requests
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

// Format date to dd-MMM-yy format (e.g., 5-May-25)
function formatDateToDDMMMYY(dateString) {
    const date = new Date(dateString);
    const day = date.getDate();
    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    const month = months[date.getMonth()];
    const year = date.getFullYear().toString().substr(-2);
    return `${day}-${month}-${year}`;
}

// Format number to currency with 2 decimal places
function formatCurrency(amount) {
    return parseFloat(amount).toFixed(2).replace(/\d(?=(\d{3})+\.)/g, '$&,');
}

// Get variation status text
function getVariationStatusText(claimed) {
    return claimed === 0 ? "Not Claimed" : "Included in HC Claim";
}

// Inspect table and add debug row
function debugTableStructure() {
    // Get the table and add debug styling
    const table = document.getElementById('existingVariationsTable');
    if (!table) return 'Table element not found';
    
    // Get table headers
    const headers = Array.from(table.querySelectorAll('th')).map(th => th.textContent.trim());
    
    // Get table rows
    const rows = table.querySelectorAll('tbody tr');
    const rowData = [];
    rows.forEach(row => {
        const cells = Array.from(row.querySelectorAll('td')).map(td => td.innerHTML);
        rowData.push(cells);
    });
    
    return {
        headers: headers,
        rowCount: rows.length,
        firstRowCellCount: rows.length > 0 ? rows[0].querySelectorAll('td').length : 0,
        rowData: rowData
    };
}

// Drastically simplified populate function with manual table building
function populateExistingVariationsTable() {
    console.log('=== SIMPLIFIED VARIATIONS TABLE FUNCTION ===');
    
    // Clear the table first
    const table = document.getElementById('existingVariationsTable');
    if (!table) {
        console.error('Table not found!');
        return;
    }
    
    // Get and verify tbody
    const tableBody = table.querySelector('tbody');
    if (!tableBody) {
        console.error('Table body not found!');
        return;
    }
    
    // Force clear the table by removing all child nodes - avoid innerHTML
    while (tableBody.firstChild) {
        tableBody.removeChild(tableBody.firstChild);
    }
    
    // Verify we have data
    if (typeof hc_variations === 'undefined') {
        console.error('No hc_variations data available');
        const emptyRow = document.createElement('tr');
        const emptyCell = document.createElement('td');
        emptyCell.setAttribute('colspan', '4');
        emptyCell.textContent = 'No variations data available';
        emptyRow.appendChild(emptyCell);
        tableBody.appendChild(emptyRow);
        return;
    }
    
    // Parse data if needed
    let variations;
    try {
        variations = typeof hc_variations === 'string' ? JSON.parse(hc_variations) : hc_variations;
    } catch (error) {
        console.error('Error parsing variations data:', error);
        return;
    }
    
    // Log data for debugging
    console.log('Data count:', variations.length);
    console.log('First item:', variations[0]);
    
    // Process each variation one by one
    variations.forEach(variation => {
        // 1. Create a row element
        const row = document.createElement('tr');
        
        // 2. Create date cell
        const dateCell = document.createElement('td');
        dateCell.style.padding = '4px';
        dateCell.textContent = formatDateToDDMMMYY(variation.date);
        row.appendChild(dateCell);
        
        // 3. Create amount cell
        const amountCell = document.createElement('td');
        amountCell.style.padding = '4px';
        amountCell.textContent = '$' + formatCurrency(variation.total_amount);
        row.appendChild(amountCell);
        
        // 4. Create view details cell
        const viewCell = document.createElement('td');
        viewCell.style.padding = '4px';
        const viewLink = document.createElement('a');
        viewLink.href = '#';
        viewLink.className = 'view-variation-details';
        viewLink.setAttribute('data-variation-pk', variation.hc_variation_pk);
        viewLink.textContent = 'View Details';
        viewCell.appendChild(viewLink);
        row.appendChild(viewCell);
        
        // 5. Create claimed status cell
        const claimedCell = document.createElement('td');
        claimedCell.style.padding = '4px';
        if (variation.claimed === 0) {
            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.className = 'include-in-hc-claim';
            checkbox.setAttribute('data-variation-pk', variation.hc_variation_pk);
            claimedCell.appendChild(checkbox);
        } else {
            claimedCell.textContent = 'Yes';
        }
        row.appendChild(claimedCell);
        
        // Add the complete row to the table
        tableBody.appendChild(row);
        
        // Log what we just added
        console.log('Added row with cells:', row.querySelectorAll('td').length);
    });
    
    // Set up event listeners
    document.querySelectorAll('.view-variation-details').forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            showVariationDetails(this.getAttribute('data-variation-pk'));
        });
    });
    
    document.querySelectorAll('.include-in-hc-claim').forEach(checkbox => {
        checkbox.addEventListener('change', updateIncludeInHCClaimButton);
    });
    
    // Final log of structure
    const firstRow = tableBody.querySelector('tr');
    if (firstRow) {
        console.log('FINAL ROW CELL COUNT:', firstRow.querySelectorAll('td').length);
        const cells = firstRow.querySelectorAll('td');
        for (let i = 0; i < cells.length; i++) {
            console.log(`Cell ${i} content:`, cells[i].textContent);
        }
    }
}

// Track click state for each variation
let clickedVariations = {};

// Populate the iframe template with initial content
function initializeVariationDetailPanel() {
    console.log('Initializing variation detail panel');
    const iframe = document.getElementById('variationDetailPanel');
    if (!iframe) return;
    
    // Get the iframe document
    const iframeDoc = iframe.contentDocument || iframe.contentWindow.document;
    if (!iframeDoc) return;
    
    // Set up base CSS and HTML structure
    iframeDoc.open();
    iframeDoc.write(`
        <html>
        <head>
            <style>
                body {
                    font-family: Arial, Helvetica, sans-serif;
                    margin: 0;
                    padding: 0;
                    font-size: 13px;
                    line-height: 1.3;
                }
                .no-variation-selected {
                    text-align: center;
                    padding-top: 50px;
                    color: #888;
                }
                .variation-details {
                    display: none;
                }
                .header {
                    background: linear-gradient(45deg, #f0f0f0, #ffffff);
                    padding: 15px 20px;
                    border-bottom: 1px solid #ddd;
                }
                h4 {
                    margin: 0 0 15px 0;
                    color: #333;
                    font-size: 16px;
                    font-weight: bold;
                }
                .label {
                    font-weight: bold;
                    margin-right: 5px;
                }
                .content-section {
                    padding: 15px 20px;
                }
                h5 {
                    margin: 0 0 15px 0;
                    color: #333;
                    font-size: 14px;
                    font-weight: bold;
                }
                table {
                    width: 100%;
                    border-collapse: collapse;
                    font-size: 12px;
                }
                th {
                    text-align: left;
                    padding: 8px 5px;
                    background: linear-gradient(45deg, #f0f0f0, #ffffff);
                    border-bottom: 1px solid #ddd;
                    font-weight: bold;
                }
                td {
                    padding: 6px 5px;
                    border-bottom: 1px solid #eee;
                }
                tr:nth-child(even) {
                    background-color: #f9f9f9;
                }
                .amount {
                    text-align: right;
                }
                .total-row {
                    font-weight: bold;
                    border-top: 2px solid #ddd;
                    background-color: #f0f0f0;
                }
            </style>
        </head>
        <body>
            <div class='no-variation-selected'>
                <i class='fas fa-file-alt' style='font-size: 48px;'></i>
                <p>Select a variation to view details</p>
            </div>
            <div class='variation-details'>
                <!-- Header with date and total amount -->
                <div class='header'>
                    <h4>Variation Details</h4>
                    <div>
                        <span class='label'>Date:</span>
                        <span id='iframe-detailVariationDate'></span>
                    </div>
                    <div>
                        <span class='label'>Total Amount:</span>
                        $<span id='iframe-detailVariationAmount'></span>
                    </div>
                </div>
                
                <!-- Items section -->
                <div class='content-section'>
                    <h5>Variation Items</h5>
                    <table>
                        <thead>
                            <tr>
                                <th width='45%'>Item</th>
                                <th width='15%'>Amount</th>
                                <th width='40%'>Notes</th>
                            </tr>
                        </thead>
                        <tbody id='iframe-detailVariationItems'>
                            <!-- Items will be added dynamically by JavaScript -->
                        </tbody>
                    </table>
                </div>
            </div>
        </body>
        </html>
    `);
    iframeDoc.close();
}

// Initialize the panel when the modal is shown
$('#existingVariationsModal').on('shown.bs.modal', function() {
    // Initialize the panel with the default message
    initializeVariationDetailPanel();
});

// Show variation details in the left panel - now with two-click behavior
function showVariationDetails(variationPk) {
    console.log('Processing click for variation:', variationPk);
    
    // Get the iframe and its document
    const iframe = document.getElementById('variationDetailPanel');
    if (!iframe) return;
    
    let iframeDoc = iframe.contentDocument || iframe.contentWindow.document;
    if (!iframeDoc) return;
    
    // Initialize iframe if needed
    if (!iframeDoc.querySelector('.no-variation-selected')) {
        initializeVariationDetailPanel();
        iframeDoc = iframe.contentDocument || iframe.contentWindow.document;
        if (!iframeDoc) return;
    }
    
    // Initialize the click state if not already tracked
    if (typeof clickedVariations[variationPk] === 'undefined') {
        clickedVariations[variationPk] = 0;
    }
    
    // Increment the click count for this variation
    clickedVariations[variationPk]++;
    console.log(`Click count for variation ${variationPk}: ${clickedVariations[variationPk]}`);
    
    // On first click, just show the placeholder
    if (clickedVariations[variationPk] === 1) {
        // Reset all click states except the current one
        Object.keys(clickedVariations).forEach(key => {
            if (key !== variationPk.toString()) {
                clickedVariations[key] = 0;
            }
        });
        
        // Make sure the placeholder is showing
        iframeDoc.querySelector('.no-variation-selected').style.display = 'block';
        iframeDoc.querySelector('.variation-details').style.display = 'none';
        return;
    }
    
    // On second click, actually show the data
    if (clickedVariations[variationPk] >= 2) {
        // Make sure we handle both string and object formats
        const variations = typeof hc_variations === 'string' ? JSON.parse(hc_variations) : hc_variations;
        const variation = variations.find(v => v.hc_variation_pk == variationPk);
        
        if (variation) {
            // Hide the placeholder and show the details
            iframeDoc.querySelector('.no-variation-selected').style.display = 'none';
            iframeDoc.querySelector('.variation-details').style.display = 'block';
            
            // Fill in the details
            iframeDoc.getElementById('iframe-detailVariationDate').textContent = formatDateToDDMMMYY(variation.date);
            iframeDoc.getElementById('iframe-detailVariationAmount').textContent = formatCurrency(variation.total_amount);
            
            // Populate items table
            const itemsTableBody = iframeDoc.getElementById('iframe-detailVariationItems');
            itemsTableBody.innerHTML = ''; // Clear existing rows
            
            // Calculate total for footer
            let totalAmount = 0;
        
        // Add each item row with enhanced styling
        variation.items.forEach((item, index) => {
            totalAmount += parseFloat(item.amount);
            
            // Create row with zebra striping
            const row = iframeDoc.createElement('tr');
            if (index % 2 === 1) {
                row.style.backgroundColor = '#f9f9f9';
            }
            
            // Check if this is a margin item (based on your system's convention)
            const isMarginItem = item.category_order_in_list === -1;
            if (isMarginItem) {
                row.style.backgroundColor = '#e9ecef';
                row.style.fontStyle = 'italic';
            }
            
            // Create each cell
            const itemCell = iframeDoc.createElement('td');
            itemCell.textContent = item.item;
            
            const amountCell = iframeDoc.createElement('td');
            amountCell.textContent = '$' + formatCurrency(item.amount);
            amountCell.className = 'amount'; // Use CSS class for right alignment
            
            const notesCell = iframeDoc.createElement('td');
            notesCell.textContent = item.notes || '';
            
            row.appendChild(itemCell);
            row.appendChild(amountCell);
            row.appendChild(notesCell);
            itemsTableBody.appendChild(row);
        });
        
        // Add a total row at the bottom
        const totalRow = iframeDoc.createElement('tr');
        totalRow.className = 'total-row';
        
        const totalLabelCell = iframeDoc.createElement('td');
        totalLabelCell.textContent = 'Total';
        
        const totalAmountCell = iframeDoc.createElement('td');
        totalAmountCell.textContent = '$' + formatCurrency(totalAmount);
        totalAmountCell.className = 'amount';
        
        const emptyCell = iframeDoc.createElement('td');
        
        totalRow.appendChild(totalLabelCell);
        totalRow.appendChild(totalAmountCell);
        totalRow.appendChild(emptyCell);
        itemsTableBody.appendChild(totalRow);
    }
}

// Update the Include in HC Claim button based on checkbox selections
function updateIncludeInHCClaimButton() {
    const checkboxes = document.querySelectorAll('.include-in-hc-claim:checked');
    const button = document.getElementById('includeInHCClaimButton');
    
    if (checkboxes.length > 0) {
        button.disabled = false;
    } else {
        button.disabled = true;
    }
}

// Handle including selected variations in HC claim
function includeInHCClaim() {
    const checkedVariations = document.querySelectorAll('.include-in-hc-claim:checked');
    const variationPks = Array.from(checkedVariations).map(cb => cb.getAttribute('data-variation-pk'));
    
    // This would typically be an AJAX call to a backend endpoint
    alert(`Including variations in HC Claim: ${variationPks.join(', ')}`);
}

// Document ready function
document.addEventListener('DOMContentLoaded', function() {
    // The modal showing is handled in hc_variations_1.js
    // Here we just need to populate the data when it opens
    
    // Populate the existing variations table when the modal is shown
    $('#existingVariationsModal').on('show.bs.modal', function() {
        console.log('Modal showing - About to populate table');
        
        // Check table structure BEFORE we do anything
        const table = document.getElementById('existingVariationsTable');
        const headers = Array.from(table.querySelectorAll('th')).map(th => th.textContent);
        console.log('TABLE HEADERS BEFORE:', headers);
        console.log('HEADER COUNT:', headers.length);
        
        setTimeout(function() {
            populateExistingVariationsTable();
            
            // Check table structure AFTER population
            const tableAfter = document.getElementById('existingVariationsTable');
            const firstRow = tableAfter.querySelector('tbody tr');
            if (firstRow) {
                const cells = Array.from(firstRow.querySelectorAll('td'));
                console.log('FIRST ROW CELL COUNT:', cells.length);
                cells.forEach((cell, index) => {
                    console.log(`CELL ${index} HTML:`, cell.innerHTML);
                    console.log(`CELL ${index} TEXT:`, cell.textContent);
                });
            }
        }, 100); // Small delay to ensure DOM is ready
    });
    
    // Also add a direct call to populate when document is ready
    // This ensures the table is populated even if the event doesn't fire correctly
    setTimeout(function() {
        if ($('#existingVariationsModal').is(':visible')) {
            console.log('Modal is visible on page load - populating table');
            populateExistingVariationsTable();
        }
    }, 500);
    
    // Reset dropdown when modal is closed
    $('#existingVariationsModal').on('hidden.bs.modal', function() {
        const hcVariationsDropdown = document.getElementById('hcVariationsDropdown');
        if (hcVariationsDropdown) {
            hcVariationsDropdown.selectedIndex = 0;
        }
    });
    
});
