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
});


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

// Populate the existing variations table
function populateExistingVariationsTable() {
    console.log('populateExistingVariationsTable called');
    const tableBody = document.getElementById('existingVariationsTable').querySelector('tbody');
    if (!tableBody) {
        console.error('Could not find table body element');
        return;
    }
    
    tableBody.innerHTML = ''; // Clear existing rows
    
    // Check for the hc_variations global variable
    console.log('hc_variations exists:', typeof hc_variations !== 'undefined');
    
    if (typeof hc_variations !== 'undefined') {
        // Log for debugging
        console.log('HC Variations data type:', typeof hc_variations);
        console.log('HC Variations data:', hc_variations);
        
        // Make sure we handle both string and object formats
        let variations;
        try {
            variations = typeof hc_variations === 'string' ? JSON.parse(hc_variations) : hc_variations;
            console.log('Parsed variations:', variations);
            console.log('Variations count:', variations.length);
        } catch (error) {
            console.error('Error parsing variations:', error);
            tableBody.innerHTML = '<tr><td colspan="5" style="text-align: center;">Error loading variations data</td></tr>';
            return;
        }
        
        variations.forEach(variation => {
            const row = document.createElement('tr');
            
            // Format date
            const formattedDate = formatDateToDDMMMYY(variation.date);
            
            // Format status
            const statusText = getVariationStatusText(variation.claimed);
            
            // Create row content
            row.innerHTML = `
                <td style="padding: 4px;">${variation.number}</td>
                <td style="padding: 4px;">${formattedDate}</td>
                <td style="padding: 4px;">$${formatCurrency(variation.total_amount)}</td>
                <td style="padding: 4px;"><a href="#" class="view-variation-details" data-variation-pk="${variation.hc_variation_pk}">View Details</a></td>
                <td style="padding: 4px;">${variation.claimed === 0 ? 
                    '<input type="checkbox" class="include-in-hc-claim" data-variation-pk="' + variation.hc_variation_pk + '">' : 
                    'Yes'}</td>
            `;
            
            tableBody.appendChild(row);
        });
        
        // Add event listeners to the view links
        document.querySelectorAll('.view-variation-details').forEach(link => {
            link.addEventListener('click', function(e) {
                e.preventDefault();
                const variationPk = this.getAttribute('data-variation-pk');
                showVariationDetails(variationPk);
            });
        });
        
        // Add event listeners to checkboxes
        document.querySelectorAll('.include-in-hc-claim').forEach(checkbox => {
            checkbox.addEventListener('change', updateIncludeInHCClaimButton);
        });
    } else if (variations && variations.length === 0) {
        console.log('No variations found in the data');
        const row = document.createElement('tr');
        row.innerHTML = '<td colspan="5" style="text-align: center;">No variations found</td>';
        tableBody.appendChild(row);
    } else {
        console.log('hc_variations is undefined or invalid');
        const row = document.createElement('tr');
        row.innerHTML = '<td colspan="5" style="text-align: center;">No variations data available</td>';
        tableBody.appendChild(row);
    }
}

// Show variation details in the left panel
function showVariationDetails(variationPk) {
    // Make sure we handle both string and object formats
    const variations = typeof hc_variations === 'string' ? JSON.parse(hc_variations) : hc_variations;
    const variation = variations.find(v => v.hc_variation_pk == variationPk);
    
    if (variation) {
        // Hide the placeholder and show the details
        document.querySelector('.no-variation-selected').style.display = 'none';
        document.querySelector('.variation-details').style.display = 'block';
        
        // Fill in the details
        document.getElementById('detailVariationNumber').textContent = variation.number;
        document.getElementById('detailVariationDate').textContent = formatDateToDDMMMYY(variation.date);
        document.getElementById('detailVariationAmount').textContent = formatCurrency(variation.total_amount);
        document.getElementById('detailVariationStatus').textContent = getVariationStatusText(variation.claimed);
        
        // Populate items table
        const itemsTableBody = document.getElementById('detailVariationItems');
        itemsTableBody.innerHTML = ''; // Clear existing rows
        
        variation.items.forEach(item => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${item.item}</td>
                <td>$${formatCurrency(item.amount)}</td>
                <td>${item.notes || ''}</td>
            `;
            itemsTableBody.appendChild(row);
        });
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
    
    // Populate the variations table when the modal is shown
    $('#existingVariationsModal').on('show.bs.modal', function() {
        console.log('Modal showing - About to populate table');
        setTimeout(function() {
            populateExistingVariationsTable();
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
    
    // Handle the Include in HC Claim button
    const includeInHCClaimButton = document.getElementById('includeInHCClaimButton');
    if (includeInHCClaimButton) {
        includeInHCClaimButton.addEventListener('click', includeInHCClaim);
    }
    
    // Handle download button (placeholder)
    const downloadButton = document.getElementById('downloadVariationSummary');
    if (downloadButton) {
        downloadButton.addEventListener('click', function() {
            alert('Download functionality would be implemented here');
        });
    }
});
