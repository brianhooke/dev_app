/**
 * Quote Entry Module
 * Reusable quote entry functionality for any app
 * 
 * Dependencies:
 * - jQuery
 * - window.projectContacts (array of supplier contacts)
 * - window.itemsItems (array of project items/costings)
 * - window.currentTenderProject or equivalent project context
 */

var QuotesEntry = (function() {
    'use strict';
    
    // Private variables
    var currentPdfUrl = null;
    var currentPdfDataUrl = null;
    var containerSelector = '#quoteEntryContainer';
    var onSaveCallback = null;
    var onCancelCallback = null;
    var projectPk = null;
    var projectType = null;  // NEW: Track project type
    var isUpdateMode = false;
    var quoteId = null;
    var existingData = null;
    var isConstructionProject = false;  // NEW: Flag for construction-specific behavior
    
    /**
     * Initialize quote entry form
     * @param {Object} options - Configuration options
     * @param {string} options.pdfUrl - URL for PDF display
     * @param {string} options.pdfDataUrl - Data URL for PDF upload
     * @param {string} options.containerSelector - CSS selector for container
     * @param {Function} options.onSave - Callback when quote is saved
     * @param {Function} options.onCancel - Callback when cancelled
     * @param {Array} options.suppliers - Array of supplier contacts
     * @param {Array} options.items - Array of project items
     * @param {number} options.projectPk - Project primary key for loading items if needed
     * @param {string} options.projectType - Project type (NEW: for construction-specific behavior)
     */
    function init(options) {
        currentPdfUrl = options.pdfUrl;
        currentPdfDataUrl = options.pdfDataUrl;
        containerSelector = options.containerSelector || '#quoteEntryContainer';
        onSaveCallback = options.onSave || null;
        onCancelCallback = options.onCancel || null;
        projectPk = options.projectPk || null;
        projectType = options.projectType || null;  // NEW
        isConstructionProject = (projectType === 'construction');  // NEW
        isUpdateMode = options.isUpdate || false;
        quoteId = options.quoteId || null;
        existingData = options.existingData || null;
        
        console.log('QuotesEntry init - Project Type:', projectType);
        console.log('QuotesEntry init - Is Construction:', isConstructionProject);
        console.log('QuotesEntry init - Update mode:', isUpdateMode);
        if (isUpdateMode) {
            console.log('Existing data:', existingData);
        }
        
        // Store suppliers and items globally if provided
        if (options.suppliers) {
            window.projectContacts = options.suppliers;
        }
        if (options.items) {
            window.itemsItems = options.items;
        }
        
        // Check if items need to be loaded
        if (!window.itemsItems || window.itemsItems.length === 0) {
            if (options.projectPk) {
                console.log('Items not loaded, loading for project:', options.projectPk);
                loadItemsForProject(options.projectPk, function() {
                    renderQuoteForm();
                });
            } else {
                console.error('No items available and no projectPk provided');
                renderQuoteForm(); // Render anyway, will show empty dropdown
            }
        } else {
            renderQuoteForm();
        }
    }
    
    /**
     * Load items for a project via AJAX
     */
    function loadItemsForProject(projectPk, callback) {
        $.ajax({
            url: '/get_project_items/' + projectPk + '/',
            type: 'GET',
            success: function(response) {
                if (response.status === 'success') {
                    window.itemsItems = response.items;
                    console.log('Items loaded for quote form:', window.itemsItems);
                    if (callback) callback();
                } else {
                    console.error('Error loading items:', response.message);
                    alert('Unable to load project items. Please try again.');
                }
            },
            error: function(xhr, status, error) {
                console.error('Error loading items:', error);
                alert('Unable to load project items. Please try again.');
            }
        });
    }
    
    /**
     * Render the quote entry form
     */
    function renderQuoteForm() {
        console.log('renderQuoteForm - isConstructionProject:', isConstructionProject);
        console.log('renderQuoteForm - projectType:', projectType);
        
        // Generate supplier dropdown options
        var selectHTML = '<select id="quoteSupplier" class="form-control">';
        if (typeof window.projectContacts !== 'undefined' && window.projectContacts.length > 0) {
            window.projectContacts.forEach(function(contact) {
                selectHTML += '<option value="' + contact.contact_pk + '">' + contact.name + '</option>';
            });
        } else {
            selectHTML += '<option value="">No contacts available - Project may not have a Xero instance</option>';
        }
        selectHTML += '</select>';
        
        // Build the quote entry form HTML
        var formHTML = `
            <div style="display: flex; height: 100%; gap: 15px;">
                <!-- Left side: Quote Entry Form (60%) -->
                <div style="width: 60%; height: 100%; overflow-y: auto; padding: 20px; border: 1px solid #ddd;">
                    <h5 style="margin-bottom: 15px;">Enter Quote</h5>
                    
                    <div class="form-group" style="margin-bottom: 8px; display: flex; align-items: center; gap: 10px;">
                        <label for="quoteSupplier" style="font-size: 13px; margin: 0; min-width: 80px;">Supplier:</label>
                        ${selectHTML}
                    </div>
                    
                    <div class="form-group" style="margin-bottom: 8px; display: flex; align-items: center; gap: 10px;">
                        <label for="quoteTotalCost" style="font-size: 13px; margin: 0; min-width: 80px;">Total Cost:</label>
                        <input type="number" id="quoteTotalCost" class="form-control form-control-sm" step="0.01" min="0" placeholder="0.00" value="0.00">
                    </div>
                    
                    <div class="form-group" style="margin-bottom: 8px; display: flex; align-items: center; gap: 10px;">
                        <label for="quoteNumber" style="font-size: 13px; margin: 0; min-width: 80px;">Quote #:</label>
                        <input type="text" id="quoteNumber" class="form-control form-control-sm" maxlength="255">
                    </div>
                    
                    <h6 style="margin-top: 15px; margin-bottom: 10px;">Line Items</h6>
                    <div style="overflow-x: auto;">
                        <table id="quoteLineItemsTable" class="reusable-table" style="font-size: 12px;">
                            <thead>
                                <tr>
                                    <th style="width: ${isConstructionProject ? '30%' : '40%'};">Item</th>
                                    ${isConstructionProject ? `
                                        <th style="width: 8%;">Unit</th>
                                        <th style="width: 12%;">Qty</th>
                                        <th style="width: 12%;">Rate</th>
                                        <th style="width: 12%;">Amount</th>
                                    ` : `
                                        <th style="width: 20%;">Amount</th>
                                    `}
                                    <th style="width: ${isConstructionProject ? '21%' : '35%'};">Notes</th>
                                    <th style="width: 5%;"></th>
                                </tr>
                            </thead>
                            <tbody>
                                <!-- Line items will be added here -->
                            </tbody>
                        </table>
                    </div>
                    
                    <div style="margin-top: 10px; margin-bottom: 10px; padding: 8px; background-color: #f8f9fa; border: 1px solid #dee2e6; border-radius: 4px;">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <strong style="font-size: 13px;">Still to Allocate:</strong>
                            <span id="quoteStillToAllocate" style="font-weight: bold; font-size: 14px;">$0.00</span>
                        </div>
                    </div>
                    
                    <button id="quoteAddLineItemBtn" class="btn btn-secondary btn-sm" style="margin-bottom: 10px;">
                        <i class="fas fa-plus"></i> Add Line Item
                    </button>
                    
                    <div style="margin-top: 15px; display: flex; gap: 10px; justify-content: flex-end;">
                        <button id="quoteCancelBtn" class="btn btn-secondary btn-sm">Cancel</button>
                        <button id="quoteSaveBtn" class="btn ${isUpdateMode ? 'btn-warning' : 'btn-secondary'} btn-sm" disabled>${isUpdateMode ? 'Update Quote' : 'Save Quote'}</button>
                    </div>
                </div>
                
                <!-- Right side: PDF Viewer (40%) -->
                <div style="width: 40%; height: 100%; position: relative;">
                    <object id="quotePdfObject" data="${currentPdfUrl}" type="application/pdf" style="width: 100%; height: 100%; border: 1px solid #ddd;">
                        <div style="padding: 20px; text-align: center;">
                            <p style="color: #6c757d; margin-bottom: 15px;">PDF preview not available in this browser</p>
                            <a href="${currentPdfUrl}" download="quote.pdf" class="btn btn-primary" target="_blank">
                                <i class="fas fa-download"></i> Download PDF
                            </a>
                        </div>
                    </object>
                </div>
            </div>
        `;
        
        // Inject form into container
        $(containerSelector).html(formHTML).show();
        
        // Attach event handlers
        attachEventHandlers();
        
        // Pre-populate fields if in update mode
        if (isUpdateMode && existingData) {
            console.log('Pre-populating form with existing data');
            console.log('Setting supplier to:', existingData.supplier);
            
            // Use setTimeout to ensure DOM is fully ready
            setTimeout(function() {
                var supplierDropdown = $('#quoteSupplier');
                console.log('Supplier dropdown found:', supplierDropdown.length > 0);
                console.log('Available options:', supplierDropdown.find('option').length);
                
                // Log all available option values
                supplierDropdown.find('option').each(function() {
                    console.log('Option value:', $(this).val(), 'text:', $(this).text());
                });
                
                supplierDropdown.val(existingData.supplier);
                console.log('Trying to set supplier to:', existingData.supplier);
                console.log('Supplier dropdown value after setting:', supplierDropdown.val());
                
                // Force the dropdown to show the value if it didn't work
                if (supplierDropdown.val() != existingData.supplier) {
                    console.warn('Supplier value did not set correctly, trying string conversion');
                    supplierDropdown.val(String(existingData.supplier));
                    console.log('After string conversion:', supplierDropdown.val());
                }
                
                $('#quoteTotalCost').val(existingData.totalCost);
                $('#quoteNumber').val(existingData.quoteNumber);
                
                // Add line items
                if (existingData.allocations && existingData.allocations.length > 0) {
                    existingData.allocations.forEach(function(alloc) {
                        if (isConstructionProject) {
                            addLineItem(alloc.item, alloc.qty || '', alloc.unit || '', alloc.rate || '', alloc.notes || '');
                        } else {
                            addLineItem(alloc.item, alloc.amount, alloc.notes || '');
                        }
                    });
                }
                
                // Trigger validation after everything is populated
                updateStillToAllocate();
                validateQuote();
            }, 100);
        }
        
        // Initialize validation
        updateStillToAllocate();
        validateQuote();
        
        console.log('Quote entry form rendered');
    }
    
    /**
     * Attach all event handlers
     */
    function attachEventHandlers() {
        // Attach change event to total cost to update still to allocate
        $(document).off('input', '#quoteTotalCost').on('input', '#quoteTotalCost', function() {
            // Just update calculations, don't format on input
            updateStillToAllocate();
            validateQuote();
        });
        
        // Format to 2 decimal places on blur
        $(document).off('blur', '#quoteTotalCost').on('blur', '#quoteTotalCost', function() {
            var value = parseFloat($(this).val());
            if (!isNaN(value) && value > 0) {
                $(this).val(value.toFixed(2));
            } else if (value === 0) {
                $(this).val('0.00');
            } else {
                $(this).val('');
            }
        });
        
        // Supplier change
        $('#quoteSupplier').on('change', validateQuote);
        
        // Quote number input
        $('#quoteNumber').on('input', validateQuote);
        
        // Add line item button
        $('#quoteAddLineItemBtn').on('click', function() {
            addLineItem();
        });
        
        // Cancel button
        $('#quoteCancelBtn').on('click', function() {
            close();
            if (onCancelCallback) onCancelCallback();
        });
        
        // Save button
        $('#quoteSaveBtn').on('click', function() {
            saveQuote();
        });
    }
    
    /**
     * Add a new line item row
     * For construction projects: addLineItem(item, qty, unit, rate, notes)
     * For other projects: addLineItem(item, amount, notes)
     * Note: unit is auto-populated from Costing.unit and displayed as read-only
     */
    function addLineItem(item = '', arg2 = '', arg3 = '', arg4 = '', arg5 = '') {
        var tableBody = $('#quoteLineItemsTable tbody');
        var newRow = $('<tr></tr>');
        
        // Parse arguments based on project type
        var qty, unit, rate, amount, notes;
        if (isConstructionProject) {
            qty = arg2;
            unit = arg3;  // Stored hidden, auto-populated from item selection
            rate = arg4;
            notes = arg5;
        } else {
            amount = arg2;
            notes = arg3;
        }
        
        // Cell 0: Item dropdown
        var itemCell = $('<td></td>');
        var itemSelect = $('<select></select>')
            .addClass('form-control form-control-sm')
            .css('width', '100%');
        
        itemSelect.append('<option value="">Select an item</option>');
        
        // Populate items dropdown
        if (window.itemsItems && window.itemsItems.length > 0) {
            window.itemsItems.forEach(function(costing) {
                var selected = item === costing.item ? 'selected' : '';
                var unitAttr = costing.unit ? 'data-unit="' + costing.unit + '"' : '';
                itemSelect.append(
                    '<option value="' + costing.item + '" data-costing-id="' + costing.costing_pk + '" ' + unitAttr + ' ' + selected + '>' + costing.item + '</option>'
                );
            });
        }
        
        // Auto-populate unit on item selection (construction only)
        if (isConstructionProject) {
            itemSelect.on('change', function() {
                var selectedOption = $(this).find('option:selected');
                var costingUnit = selectedOption.attr('data-unit') || '';
                var row = $(this).closest('tr');
                
                // Update both hidden input and visible display
                row.find('.unit-input').val(costingUnit);
                row.find('.unit-display').text(costingUnit || '-');
                
                validateQuote();
            });
        } else {
            itemSelect.on('change', validateQuote);
        }
        
        itemCell.append(itemSelect);
        newRow.append(itemCell);
        
        if (isConstructionProject) {
            // CONSTRUCTION: Unit, Qty, Rate, Amount columns
            
            // Cell 1: Unit (read-only display)
            var unitCell = $('<td></td>');
            var unitDisplay = $('<span></span>')
                .addClass('unit-display')
                .css({'font-size': '13px', 'color': '#495057'})
                .text(unit || '-');
            unitCell.append(unitDisplay);
            
            // Hidden unit input (stores unit from Costing for backend)
            var unitInput = $('<input>')
                .attr('type', 'hidden')
                .addClass('unit-input')
                .val(unit || '');
            unitCell.append(unitInput);
            newRow.append(unitCell);
            
            // Cell 2: Qty input
            var qtyCell = $('<td></td>');
            var qtyInput = $('<input>')
                .attr('type', 'number')
                .attr('step', '0.01')
                .attr('placeholder', '0.00')
                .addClass('form-control form-control-sm qty-input')
                .css('width', '100%')
                .val(qty ? parseFloat(qty).toFixed(2) : '');
            qtyInput.on('input', function() {
                updateRowAmount($(this).closest('tr'));
                updateStillToAllocate();
                validateQuote();
            });
            qtyCell.append(qtyInput);
            newRow.append(qtyCell);
            
            // Cell 3: Rate input
            var rateCell = $('<td></td>');
            var rateInput = $('<input>')
                .attr('type', 'number')
                .attr('step', '0.01')
                .attr('placeholder', '0.00')
                .addClass('form-control form-control-sm rate-input')
                .css('width', '100%')
                .val(rate ? parseFloat(rate).toFixed(2) : '');
            rateInput.on('input', function() {
                updateRowAmount($(this).closest('tr'));
                updateStillToAllocate();
                validateQuote();
            });
            rateCell.append(rateInput);
            newRow.append(rateCell);
            
            // Cell 4: Amount (calculated, read-only)
            var amountCell = $('<td></td>');
            var amountDisplay = $('<input>')
                .attr('type', 'text')
                .attr('readonly', 'readonly')
                .addClass('form-control form-control-sm amount-display')
                .css({'width': '100%', 'background-color': '#e9ecef', 'cursor': 'not-allowed'})
                .val('0.00');
            amountCell.append(amountDisplay);
            newRow.append(amountCell);
            
        } else {
            // NON-CONSTRUCTION: Amount column only
            
            // Cell 1: Amount input with 2dp validation
            var amountCell = $('<td></td>');
            var amountInput = $('<input>')
                .attr('type', 'number')
                .attr('step', '0.01')
                .attr('placeholder', '0.00')
                .addClass('form-control form-control-sm amount-input')
                .css('width', '100%')
                .val(amount ? parseFloat(amount).toFixed(2) : '');
            
            amountInput.on('input', function(e) {
                var value = e.target.value;
                if (value.includes('.')) {
                    var parts = value.split('.');
                    if (parts[1].length > 2) {
                        e.target.value = parseFloat(value).toFixed(2);
                    }
                }
                updateStillToAllocate();
                validateQuote();
            });
            amountCell.append(amountInput);
            newRow.append(amountCell);
        }
        
        // Notes cell (all project types)
        var notesCell = $('<td></td>');
        var notesInput = $('<input>')
            .attr('type', 'text')
            .attr('maxlength', '100')
            .attr('placeholder', 'Notes (max 100 chars)')
            .addClass('form-control form-control-sm notes-input')
            .css('width', '100%')
            .val(notes || '');
        notesCell.append(notesInput);
        newRow.append(notesCell);
        
        // Delete button cell (all project types)
        var deleteCell = $('<td></td>').css('text-align', 'center');
        var deleteButton = $('<button></button>')
            .addClass('btn btn-sm btn-danger')
            .text('x')
            .on('click', function() {
                newRow.remove();
                updateStillToAllocate();
                validateQuote();
            });
        deleteCell.append(deleteButton);
        newRow.append(deleteCell);
        
        tableBody.append(newRow);
        
        // Calculate initial amount for construction projects
        if (isConstructionProject) {
            updateRowAmount(newRow);
        }
        
        updateStillToAllocate();
        validateQuote();
    }
    
    /**
     * Update calculated amount for a construction project line item
     */
    function updateRowAmount(row) {
        var qty = parseFloat(row.find('.qty-input').val()) || 0;
        var rate = parseFloat(row.find('.rate-input').val()) || 0;
        var amount = qty * rate;
        var formattedAmount = amount.toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
        row.find('.amount-display').val(formattedAmount);
    }
    
    function updateStillToAllocate() {
        var totalCost = parseFloat($('#quoteTotalCost').val()) || 0;
        var allocated = 0;
        
        $('#quoteLineItemsTable tbody tr').each(function() {
            if (isConstructionProject) {
                // For construction: use calculated amount (qty * rate)
                var amountDisplay = $(this).find('.amount-display');
                var amount = parseFloat(amountDisplay.val().replace(/,/g, '')) || 0;
                allocated += amount;
            } else {
                // For non-construction: use entered amount
                var amountInput = $(this).find('.amount-input');
                var amount = parseFloat(amountInput.val()) || 0;
                allocated += amount;
            }
        });
        
        var stillToAllocate = totalCost - allocated;
        var displayValue = '$' + stillToAllocate.toFixed(2).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
        var element = $('#quoteStillToAllocate');
        element.text(displayValue);
        
        // Color code based on value
        if (Math.abs(stillToAllocate) < 0.01) {
            element.css('color', 'green');
        } else if (stillToAllocate > 0) {
            element.css('color', 'orange');
        } else {
            element.css('color', 'red');
        }
    }
    
    /**
     * Validate quote form and update save button state
     */
    function validateQuote() {
        var isValid = true;
        var errors = [];
        
        // Check supplier selected
        var supplier = $('#quoteSupplier').val();
        if (!supplier || supplier === '') {
            isValid = false;
            errors.push('Supplier not selected');
        }
        
        // Check total cost > 0
        var totalCost = parseFloat($('#quoteTotalCost').val()) || 0;
        if (totalCost <= 0) {
            isValid = false;
            errors.push('Total cost must be greater than 0');
        }
        
        // Check quote # has at least one character
        var quoteNumber = $('#quoteNumber').val().trim();
        if (quoteNumber.length === 0) {
            isValid = false;
            errors.push('Quote # is required');
        }
        
        // Check line items exist
        var lineItemCount = $('#quoteLineItemsTable tbody tr').length;
        if (lineItemCount === 0) {
            isValid = false;
            errors.push('At least one line item required');
        }
        
        // Check each line item
        var selectedItems = [];
        var lineItemsValid = true;
        $('#quoteLineItemsTable tbody tr').each(function() {
            var itemSelect = $(this).find('td:eq(0) select');
            var selectedOption = itemSelect.find('option:selected');
            var costingId = selectedOption.attr('data-costing-id');
            
            // Check item selected
            if (!costingId || costingId === '') {
                lineItemsValid = false;
                errors.push('All line items must have an item selected');
            }
            
            // Check amount based on project type
            var amount = 0;
            if (isConstructionProject) {
                var qty = parseFloat($(this).find('.qty-input').val()) || 0;
                var rate = parseFloat($(this).find('.rate-input').val()) || 0;
                amount = qty * rate;
                
                // Check qty > 0 and rate > 0
                if (qty <= 0 || rate <= 0) {
                    lineItemsValid = false;
                    errors.push('All line items must have qty > 0 and rate > 0');
                }
            } else {
                amount = parseFloat($(this).find('.amount-input').val()) || 0;
                
                // Check amount > 0
                if (amount <= 0) {
                    lineItemsValid = false;
                    errors.push('All line items must have amount > 0');
                }
            }
            
            // Track for duplicate check
            if (costingId) {
                selectedItems.push(costingId);
            }
        });
        
        if (!lineItemsValid) {
            isValid = false;
        }
        
        // Check for duplicate items
        var uniqueItems = [...new Set(selectedItems)];
        if (selectedItems.length !== uniqueItems.length) {
            isValid = false;
            errors.push('Duplicate items detected - each item can only appear once');
        }
        
        // Check still to allocate = 0
        var allocated = 0;
        $('#quoteLineItemsTable tbody tr').each(function() {
            if (isConstructionProject) {
                var amount = parseFloat($(this).find('.amount-display').val()) || 0;
                allocated += amount;
            } else {
                var amount = parseFloat($(this).find('.amount-input').val()) || 0;
                allocated += amount;
            }
        });
        var stillToAllocate = totalCost - allocated;
        if (Math.abs(stillToAllocate) >= 0.01) {
            isValid = false;
            errors.push('Still to allocate must be exactly $0.00');
        }
        
        // Update button state
        var saveButton = $('#quoteSaveBtn');
        if (isValid) {
            saveButton.prop('disabled', false)
                .removeClass('btn-secondary')
                .addClass('btn-success');
        } else {
            saveButton.prop('disabled', true)
                .removeClass('btn-success')
                .addClass('btn-secondary');
        }
        
        // Log validation status for debugging
        if (!isValid && errors.length > 0) {
            console.log('Validation failed:', errors);
        }
        
        return isValid;
    }
    
    /**
     * Save the quote
     */
    function saveQuote() {
        if (!validateQuote()) {
            alert('Please fix validation errors before saving');
            return;
        }
        
        if (!projectPk) {
            alert('Error: No project specified');
            return;
        }
        
        var totalCost = parseFloat($('#quoteTotalCost').val()) || 0;
        var supplier = $('#quoteSupplier').val();
        var quoteNumber = $('#quoteNumber').val().trim();
        
        // Gather line items
        var lineItems = [];
        $('#quoteLineItemsTable tbody tr').each(function() {
            var itemSelect = $(this).find('td:eq(0) select');
            var selectedOption = itemSelect.find('option:selected');
            var costingId = selectedOption.attr('data-costing-id');
            var notesInput = $(this).find('.notes-input');
            var notes = notesInput.val();
            
            if (costingId) {
                var lineItem = {
                    item: parseInt(costingId),
                    notes: notes
                };
                
                if (isConstructionProject) {
                    // For construction: send qty, unit, rate
                    lineItem.qty = parseFloat($(this).find('.qty-input').val()) || 0;
                    lineItem.unit = $(this).find('.unit-input').val() || '';
                    lineItem.rate = parseFloat($(this).find('.rate-input').val()) || 0;
                    // Amount will be calculated on backend as qty * rate
                } else {
                    // For non-construction: send amount
                    lineItem.amount = parseFloat($(this).find('.amount-input').val()) || 0;
                }
                
                lineItems.push(lineItem);
            }
        });
        
        // Prepare data for backend
        var postData = {
            project_pk: projectPk,
            supplier: parseInt(supplier),
            total_cost: totalCost,
            quote_number: quoteNumber,
            line_items: lineItems,
            pdf_data_url: currentPdfDataUrl
        };
        
        // Add quote_id for update mode
        if (isUpdateMode && quoteId) {
            postData.quote_id = quoteId;
        }
        
        console.log(isUpdateMode ? 'Updating quote:' : 'Saving quote:', postData);
        
        // Disable save button while saving
        var saveButton = $('#quoteSaveBtn');
        saveButton.prop('disabled', true).text(isUpdateMode ? 'Updating...' : 'Saving...');
        
        // Send to backend - use appropriate endpoint
        var url = isUpdateMode ? '/core/update_quote/' : '/core/save_project_quote/';
        
        $.ajax({
            url: url,
            type: 'POST',
            contentType: 'application/json',
            headers: {
                'X-CSRFToken': getCookie('csrftoken')
            },
            data: JSON.stringify(postData),
            success: function(response) {
                if (response.status === 'success') {
                    console.log('Quote ' + (isUpdateMode ? 'updated' : 'saved') + ' successfully:', response);
                    alert('Quote ' + (isUpdateMode ? 'updated' : 'saved') + ' successfully!');
                    
                    // Close form
                    close();
                    
                    // Call save callback if provided
                    if (onSaveCallback) {
                        onSaveCallback(response);
                    }
                } else {
                    console.error('Error ' + (isUpdateMode ? 'updating' : 'saving') + ' quote:', response.message);
                    alert('Error ' + (isUpdateMode ? 'updating' : 'saving') + ' quote: ' + response.message);
                    saveButton.prop('disabled', false).text(isUpdateMode ? 'Update Quote' : 'Save Quote');
                }
            },
            error: function(xhr, status, error) {
                console.error('AJAX error ' + (isUpdateMode ? 'updating' : 'saving') + ' quote:', error);
                var errorMessage = 'Error ' + (isUpdateMode ? 'updating' : 'saving') + ' quote';
                if (xhr.responseJSON && xhr.responseJSON.message) {
                    errorMessage = xhr.responseJSON.message;
                }
                alert(errorMessage);
                saveButton.prop('disabled', false).text(isUpdateMode ? 'Update Quote' : 'Save Quote');
            }
        });
    }
    
    /**
     * Close the quote entry form
     */
    function close() {
        $(containerSelector).empty().show();  // Don't hide, just empty and ensure visible
        currentPdfUrl = null;
        currentPdfDataUrl = null;
    }
    
    /**
     * Get CSRF token from cookies
     */
    function getCookie(name) {
        var cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            var cookies = document.cookie.split(';');
            for (var i = 0; i < cookies.length; i++) {
                var cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }
    
    // Public API
    return {
        init: init,
        close: close,
        addLineItem: addLineItem,
        validateQuote: validateQuote
    };
})();

// Make available globally
window.QuotesEntry = QuotesEntry;
