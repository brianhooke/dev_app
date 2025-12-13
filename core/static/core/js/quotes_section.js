/**
 * Quotes Section Configuration
 * ============================
 * Uses AllocationsManager for the standalone quotes page (/quotes/)
 * 
 * This is a PROOF OF CONCEPT for migrating to the unified AllocationsManager.
 * 
 * Dependencies:
 * - jQuery
 * - allocations_manager.js (must be loaded before this file)
 * - utils.js (for getCookie)
 */

$(document).ready(function() {
    // Only initialize if we're on a page with the quote section
    if ($('#quoteMainTableBody').length === 0) {
        return;
    }
    
    console.log('Initializing quotes section with AllocationsManager...');
    
    // Get project PK from page context, current project, or URL
    var projectPk = window.projectPk || 
                    (window.currentQuotesProject && window.currentQuotesProject.pk) ||
                    (window.currentConstructionProject && window.currentConstructionProject.pk) ||
                    (window.currentProject && window.currentProject.pk) ||
                    getProjectPkFromUrl();
    
    AllocationsManager.init({
        sectionId: 'quote',
        
        mainTable: {
            emptyMessage: 'No quotes found. Click "Add Quote" to create one.',
            showFooter: true,
            footerTotals: [
                { colIndex: 2, valueKey: 'total_cost' }
            ],
            
            /**
             * Render a main table row for a quote
             */
            renderRow: function(quote, index, cfg) {
                var row = $('<tr>')
                    .attr('data-pk', quote.quotes_pk)
                    .attr('data-pdf-url', quote.pdf_url || quote.pdf || '');
                
                // Supplier name
                row.append($('<td>').text(quote.supplier_name || quote.contact_pk__contact_name || '-'));
                
                // Net amount
                var netAmount = parseFloat(quote.total_cost) || 0;
                var formattedNet = '$' + netAmount.toLocaleString('en-AU', {minimumFractionDigits: 2, maximumFractionDigits: 2});
                row.append($('<td>').text(formattedNet));
                
                // Quote number
                row.append($('<td>').text(quote.supplier_quote_number || '-'));
                
                // Save button
                var saveBtn = $('<button>')
                    .addClass('btn btn-sm btn-success')
                    .html('<i class="fas fa-save"></i>')
                    .on('click', function(e) {
                        e.stopPropagation();
                        saveQuote(quote.quotes_pk);
                    });
                row.append($('<td>').addClass('text-center').append(saveBtn));
                
                // Delete button
                var deleteBtn = $('<button>')
                    .addClass('btn btn-sm btn-danger')
                    .html('<i class="fas fa-trash"></i>')
                    .on('click', function(e) {
                        e.stopPropagation();
                        deleteQuote(quote.quotes_pk, quote.supplier_quote_number);
                    });
                row.append($('<td>').addClass('text-center').append(deleteBtn));
                
                return row;
            },
            
            /**
             * Called when a row is selected
             */
            onRowSelect: function(row, pk, cfg) {
                console.log('Quote selected:', pk);
                // Enable edit mode for this quote's allocations
                AllocationsManager.setEditMode('quote', true);
            }
        },
        
        allocations: {
            emptyMessage: 'No allocations. Click "+ Add Row" to allocate costs.',
            editable: true,
            
            /**
             * Render an editable allocation row
             */
            renderEditableRow: function(allocation, cfg, onChange) {
                var row = $('<tr>');
                
                if (allocation) {
                    row.attr('data-allocation-pk', allocation.quote_allocations_pk || allocation.pk);
                }
                
                // Item dropdown
                var itemSelect = $('<select>').addClass('form-control form-control-sm quote-allocation-item-select');
                itemSelect.append($('<option>').val('').text('Select Item...'));
                
                var costingItems = cfg.data.costingItems || window.quoteCostingItems || window.costings || [];
                costingItems.forEach(function(item) {
                    var option = $('<option>')
                        .val(item.costing_pk || item.pk)
                        .attr('data-costing-id', item.costing_pk || item.pk)
                        .text(item.item || item.name);
                    if (allocation && allocation.item_pk == (item.costing_pk || item.pk)) {
                        option.prop('selected', true);
                    }
                    itemSelect.append(option);
                });
                itemSelect.on('change', onChange);
                row.append($('<td>').append(itemSelect));
                
                // Amount input
                var amountInput = $('<input>')
                    .attr('type', 'number')
                    .attr('step', '0.01')
                    .addClass('form-control form-control-sm quote-allocation-amount-input')
                    .val(allocation ? parseFloat(allocation.amount).toFixed(2) : '')
                    .on('change input', onChange);
                row.append($('<td>').append(amountInput));
                
                // Notes input
                var notesInput = $('<input>')
                    .attr('type', 'text')
                    .addClass('form-control form-control-sm quote-allocation-notes-input')
                    .val(allocation ? allocation.notes || '' : '');
                row.append($('<td>').append(notesInput));
                
                // Delete button
                var deleteBtn = $('<button>')
                    .addClass('btn btn-sm btn-danger')
                    .html('<i class="fas fa-times"></i>')
                    .on('click', function() {
                        row.remove();
                        onChange();
                        if (window.adjustAllocationsHeight && window.adjustAllocationsHeight['quote']) {
                            window.adjustAllocationsHeight['quote']();
                        }
                    });
                row.append($('<td>').css('text-align', 'center').append(deleteBtn));
                
                return row;
            },
            
            /**
             * Called when allocations are updated
             */
            onUpdate: function(sectionId, totals) {
                console.log('Quote allocations updated:', totals);
                // Could update save button state here
            }
        },
        
        api: {
            loadData: '/get_project_quotes/{pk}/',
            loadAllocations: function(quotePk) {
                return '/get_allocations_for_quote/' + quotePk + '/';
            }
        }
    });
    
    // Load initial data if we have a project PK
    if (projectPk) {
        AllocationsManager.loadData('quote', { projectPk: projectPk });
    }
    
    /**
     * Helper: Get project PK from URL
     */
    function getProjectPkFromUrl() {
        var match = window.location.pathname.match(/\/project\/(\d+)/);
        return match ? match[1] : null;
    }
    
    /**
     * Save quote allocations
     */
    function saveQuote(quotePk) {
        var allocations = AllocationsManager.getAllocations('quote');
        var cfg = AllocationsManager.getConfig('quote');
        
        if (!allocations || allocations.length === 0) {
            alert('Please add at least one allocation.');
            return;
        }
        
        var data = {
            quote_id: quotePk,
            allocations: allocations.map(function(a) {
                return {
                    item: a.item_pk,
                    amount: a.amount,
                    notes: a.notes
                };
            })
        };
        
        $.ajax({
            url: '/update_quote/',
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            data: JSON.stringify(data),
            success: function(response) {
                if (response.status === 'success') {
                    alert('Quote saved successfully!');
                } else {
                    alert('Error: ' + (response.message || 'Unknown error'));
                }
            },
            error: function(xhr, status, error) {
                alert('Failed to save quote: ' + error);
            }
        });
    }
    
    /**
     * Delete a quote
     */
    function deleteQuote(quotePk, quoteNumber) {
        if (!confirm('Are you sure you want to delete quote "' + quoteNumber + '"?')) {
            return;
        }
        
        $.ajax({
            url: '/delete_quote/',
            method: 'DELETE',
            headers: {
                'Content-Type': 'application/json'
            },
            data: JSON.stringify({ supplier_quote_number: quoteNumber }),
            success: function(response) {
                if (response.status === 'success') {
                    // Reload the data
                    var projectPk = window.projectPk || getProjectPkFromUrl();
                    if (projectPk) {
                        AllocationsManager.loadData('quote', { projectPk: projectPk });
                    }
                } else {
                    alert('Error: ' + (response.message || 'Failed to delete quote'));
                }
            },
            error: function(xhr, status, error) {
                alert('Failed to delete quote: ' + error);
            }
        });
    }
});
