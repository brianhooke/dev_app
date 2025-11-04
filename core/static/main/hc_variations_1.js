// HC Variations JavaScript functions

// Helper function to get CSRF token
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

// Use DOMContentLoaded instead of window.onload to avoid conflicts
document.addEventListener('DOMContentLoaded', function() {
    // Make sure table categories collapse as they should (backup for base_table.js)
    setTimeout(function() {
        if (document.querySelectorAll('tr[data-toggle="collapse"].collapsed').length === 0) {
            document.querySelectorAll('tr[data-toggle="collapse"]').forEach(row => row.click());
        }
    }, 100);
    
    // Get the latest APPROVED HC claim date and display it in the correct format
    let latestDate = null;
    let minAllowedDate = null;
    
    // Debug to check what's happening with approved_claims
    console.log('approved_claims:', typeof approved_claims, approved_claims);
    console.log('hc_claims:', typeof hc_claims, hc_claims);
    
    // First try approved_claims, then fallback to filtering hc_claims if necessary
    if (typeof approved_claims !== 'undefined' && approved_claims.length > 0) {
        // Find the most recent approved HC claim by looking at the dates
        approved_claims.forEach(claim => {
            const claimDate = new Date(claim.date);
            if (!latestDate || claimDate > latestDate) {
                latestDate = claimDate;
            }
        });
    } else if (typeof hc_claims !== 'undefined' && hc_claims.length > 0) {
        // Fallback: Filter hc_claims to only include those with status > 0
        console.log('Using fallback: filtering hc_claims');
        
        // Filter claims with status > 0
        const approvedHcClaims = hc_claims.filter(claim => claim.status > 0);
        console.log('Filtered approved claims:', approvedHcClaims);
        
        // Find the most recent approved HC claim by looking at the dates
        approvedHcClaims.forEach(claim => {
            const claimDate = new Date(claim.date);
            if (!latestDate || claimDate > latestDate) {
                latestDate = claimDate;
            }
        });
    }
    
    // If we found a date, format it and display it
    if (latestDate) {
        const formattedDate = formatDateToDDMMMYY(latestDate);
        document.getElementById('latestHCClaimDate').textContent = formattedDate;
        
        // Set the min date attribute on the date input
        minAllowedDate = new Date(latestDate);
        minAllowedDate.setDate(minAllowedDate.getDate() + 1); // Set to day after latest claim
        document.getElementById('variationDate').min = minAllowedDate.toISOString().split('T')[0];
        
        // Add an error message div after the date input
        const dateInput = document.getElementById('variationDate');
        let errorDiv = document.getElementById('dateErrorMessage');
        if (!errorDiv) {
            errorDiv = document.createElement('div');
            errorDiv.id = 'dateErrorMessage';
            errorDiv.style.color = 'red';
            errorDiv.style.fontSize = '11px';
            errorDiv.style.display = 'none';
            errorDiv.textContent = 'Date must be after ' + formattedDate;
            dateInput.parentNode.insertBefore(errorDiv, dateInput.nextSibling);
        }
        
        // Add event listener to validate the date input
        dateInput.addEventListener('change', function() {
            validateVariationDate(this, minAllowedDate);
        });
    }
    
    // 1) If user chooses "makeClaim" in #hcVariationsDropdown => show #hcVariationNewModal
    const hcVariationsDropdown = document.getElementById('hcVariationsDropdown');
    if (hcVariationsDropdown) {
        hcVariationsDropdown.addEventListener('change', function(e) {
            if (e.target.value === 'makeClaim') {
                $('#hcVariationNewModal').modal('show');
            } else if (e.target.value === 'existingClaims') {
                // Show existing variations modal (to be implemented)
                console.log("Show existing variations");
                // $('#existingHcVariationsModal').modal('show');
            }
        });

        // Reset dropdown when modal is closed
        $('#hcVariationNewModal').on('hidden.bs.modal', function() {
            hcVariationsDropdown.selectedIndex = 0;
        });
    }
    
    // Function to validate the variation date
    function validateVariationDate(dateInput, minDate) {
        const errorDiv = document.getElementById('dateErrorMessage');
        const selectedDate = new Date(dateInput.value);
        selectedDate.setHours(0, 0, 0, 0); // Reset time part for comparison
        minDate.setHours(0, 0, 0, 0); // Reset time part for comparison
        
        // Check if the selected date is valid and after the minDate
        if (isNaN(selectedDate) || selectedDate <= minDate) {
            errorDiv.style.display = 'block';
            dateInput.setCustomValidity('Date must be after the most recent HC claim date');
            return false;
        } else {
            errorDiv.style.display = 'none';
            dateInput.setCustomValidity('');
            return true;
        }
    }
    
    // Handle adding new rows to the variation items table
    const addVariationRowBtn = document.getElementById('addVariationRow');
    if (addVariationRowBtn) {
        addVariationRowBtn.addEventListener('click', function() {
            const tbody = document.querySelector('#variationItemsTable tbody');
            if (tbody) {
                const firstRow = tbody.querySelector('tr');
                if (firstRow) {
                    // Clone the first row
                    const newRow = firstRow.cloneNode(true);
                    
                    // Clear the values in the cloned row
                    newRow.querySelector('.variation-item').value = '';
                    newRow.querySelector('.variation-amount').value = '';
                    newRow.querySelector('.variation-notes').value = '';
                    
                    // Add the new row
                    tbody.appendChild(newRow);
                    
                    // Set up the remove button event handler for the new row
                    setupRemoveRowHandlers();
                    
                    // Set up validation for the new amount field
                    setupAmountValidation();
                }
            }
        });
        
        // Set up initial row remove handlers
        setupRemoveRowHandlers();
    }
    
    // Function to validate amount field to ensure 2 decimal places only
    function validateAmount(amountInput) {
        const value = amountInput.value;
        const amountRegex = /^\d+(\.\d{1,2})?$/;
        
        if (value && !amountRegex.test(value)) {
            amountInput.setCustomValidity('Please enter a number with up to 2 decimal places');
            return false;
        } else {
            amountInput.setCustomValidity('');
            return true;
        }
    }
    
    // Add event listener to all amount fields for 2dp validation
    function setupAmountValidation() {
        document.querySelectorAll('.variation-amount').forEach(input => {
            // Remove existing event listener to avoid duplicates
            input.removeEventListener('input', amountInputHandler);
            // Add event listener
            input.addEventListener('input', amountInputHandler);
        });
    }
    
    // Handler function for amount input validation
    function amountInputHandler() {
        validateAmount(this);
        
        // Format the value to have exactly 2 decimal places when focus is lost
        this.addEventListener('blur', function() {
            if (this.value && !isNaN(parseFloat(this.value))) {
                this.value = parseFloat(this.value).toFixed(2);
            }
        });
    }
    
    // Set up initial amount validation
    setupAmountValidation();
    
    // Handle creating a new variation
    const createVariationBtn = document.getElementById('createVariationBtn');
    if (createVariationBtn) {
        createVariationBtn.addEventListener('click', function() {
            // Validate the form
            const dateInput = document.getElementById('variationDate');
            const variationDate = dateInput.value;
            
            // Check if date is present
            if (!variationDate) {
                alert('Please select a variation date');
                return;
            }
            
            // // Validate the date against the minimum allowed date
            // if (minAllowedDate && !validateVariationDate(dateInput, minAllowedDate)) {
            //     alert('Variation date must be after the most recent HC claim date (' + formatDateToDDMMMYY(latestDate) + ')');
            //     return;
            // }
            
            // Validate all amount fields
            let amountValidationPassed = true;
            document.querySelectorAll('.variation-amount').forEach(input => {
                if (!validateAmount(input)) {
                    amountValidationPassed = false;
                }
            });
            
            if (!amountValidationPassed) {
                alert('Please ensure all amounts have up to 2 decimal places');
                return;
            }
            
            // Get all rows
            const rows = document.querySelectorAll('#variationItemsTable tbody tr');
            const items = [];
            let isValid = true;
            
            for (let i = 0; i < rows.length; i++) {
                const row = rows[i];
                const item = row.querySelector('.variation-item').value;
                const amountInput = row.querySelector('.variation-amount');
                const amount = amountInput.value;
                const notes = row.querySelector('.variation-notes').value;
                
                if (!item || !amount) {
                    alert('Please fill in both item and amount for all rows');
                    return;
                }
                
                // Ensure the amount has exactly 2 decimal places for submission
                if (amount && !isNaN(parseFloat(amount))) {
                    amountInput.value = parseFloat(amount).toFixed(2);
                }
                
                items.push({
                    costing_pk: item,
                    amount: amount,
                    notes: notes
                });
            }
            
            if (items.length === 0) {
                alert('Please fill in all required fields for each item');
                return;
            }
            
            // Prepare data for AJAX request
            const formData = {
                variation_date: variationDate,
                items: items
            };
            
            // Send data to server
            $.ajax({
                url: '/create_variation/',
                type: 'POST',
                data: JSON.stringify(formData),
                contentType: 'application/json',
                headers: {
                    'X-CSRFToken': getCookie('csrftoken')
                },
                success: function(response) {
                    if (response.status === 'success') {
                        // Show success message
                        alert('Variation created successfully!');
                        // Close the modal
                        $('#hcVariationNewModal').modal('hide');
                        // Reload the page to show the new variation
                        location.reload();
                    } else {
                        // Show error message
                        alert('Error: ' + (response.message || 'Unknown error occurred'));
                    }
                },
                error: function(xhr, status, error) {
                    let errorMessage = 'An error occurred while creating the variation';
                    try {
                        const response = JSON.parse(xhr.responseText);
                        if (response.message) {
                            errorMessage = response.message;
                        }
                    } catch (e) {
                        console.error('Error parsing error response:', e);
                    }
                    alert('Error: ' + errorMessage);
                }
            });
            


        });
    }
});

// Function to set up remove row button handlers
function setupRemoveRowHandlers() {
    document.querySelectorAll('.remove-row').forEach(function(button) {
        // Remove existing handlers to avoid duplicates
        button.removeEventListener('click', handleRemoveRow);
        // Add the click handler
        button.addEventListener('click', handleRemoveRow);
    });
}

// Handler for removing a row
function handleRemoveRow(e) {
    const tbody = document.querySelector('#variationItemsTable tbody');
    if (tbody.querySelectorAll('tr').length > 1) {
        // Only remove if there's more than one row
        e.target.closest('tr').remove();
    } else {
        // If it's the last row, just clear the values
        const row = e.target.closest('tr');
        row.querySelector('.variation-item').value = '';
        row.querySelector('.variation-amount').value = '';
        row.querySelector('.variation-notes').value = '';
    }
}
