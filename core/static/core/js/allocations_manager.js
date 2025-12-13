/**
 * Allocations Manager Module
 * ==========================
 * Reusable JavaScript module for sections with:
 * - Main data table (top-left)
 * - Allocations table (bottom-left)
 * - PDF/Document viewer (right side)
 * 
 * Used by: Quotes, Invoices (unallocated), Bills (direct)
 * 
 * Configuration:
 * - sectionId: Prefix for all element IDs (e.g., 'quote', 'invoice', 'bill')
 * - mainTable: { renderRow, onRowSelect, emptyMessage }
 * - allocations: { renderRow, renderEditableRow, columns, validate }
 * - api: { loadData, loadAllocations, saveAllocation, deleteAllocation }
 */

// Prevent re-initialization when loaded via AJAX (preserves existing configs)
if (typeof window.AllocationsManager !== 'undefined' && window.AllocationsManager._initialized) {
    console.log('AllocationsManager: Already initialized, skipping re-init');
} else {

var AllocationsManager = (function() {
    'use strict';
    
    // Store configurations for each section
    var configs = {};
    
    // Store current state for each section
    var state = {};
    
    /**
     * Initialize a section
     * @param {Object} config - Section configuration
     */
    function init(config) {
        var sectionId = config.sectionId;
        if (!sectionId) {
            console.error('AllocationsManager: sectionId is required');
            return;
        }
        
        // Store configuration
        configs[sectionId] = $.extend(true, {
            // Default configuration
            sectionId: sectionId,
            mainTable: {
                emptyMessage: 'No items found.',
                showFooter: true,
                footerTotals: []  // Array of {colIndex, valueKey} for calculating totals
            },
            allocations: {
                emptyMessage: 'No allocations.',
                editable: false,
                showStillToAllocate: true
            },
            api: {},
            data: {
                items: [],
                currentItem: null,
                currentAllocations: []
            }
        }, config);
        
        // Initialize state
        state[sectionId] = {
            selectedRowPk: null,
            isNewMode: false,
            editMode: false
        };
        
        // Bind event handlers
        bindEventHandlers(sectionId);
        
        console.log('AllocationsManager initialized for section:', sectionId);
        return configs[sectionId];
    }
    
    /**
     * Bind event handlers for a section
     */
    function bindEventHandlers(sectionId) {
        var cfg = configs[sectionId];
        
        // Add allocation button
        $(document).off('click', '#' + sectionId + 'AddAllocationBtn')
            .on('click', '#' + sectionId + 'AddAllocationBtn', function() {
                addAllocationRow(sectionId);
            });
        
        // Main table row click - use event delegation
        $(document).off('click', '#' + sectionId + 'MainTableBody tr')
            .on('click', '#' + sectionId + 'MainTableBody tr', function(e) {
                // Don't trigger on buttons
                if ($(e.target).closest('button, a').length) return;
                selectRow(sectionId, $(this));
            });
    }
    
    /**
     * Load data and populate main table
     * @param {string} sectionId - Section identifier
     * @param {Object} params - API parameters (e.g., projectPk)
     * @param {Function} callback - Optional callback after load
     */
    function loadData(sectionId, params, callback) {
        var cfg = configs[sectionId];
        if (!cfg) {
            console.error('AllocationsManager: Section not initialized:', sectionId);
            return;
        }
        
        var url = cfg.api.loadData;
        if (typeof url === 'function') {
            url = url(params);
        } else if (params.projectPk) {
            url = url.replace('{pk}', params.projectPk);
        }
        
        $.ajax({
            url: url,
            type: 'GET',
            data: params.queryParams || {},
            success: function(response) {
                if (response.status === 'success' || response.items || response.quotes || response.invoices || response.bills) {
                    // Normalize response data
                    var items = response.items || response.quotes || response.invoices || response.bills || [];
                    cfg.data.items = items;
                    cfg.data.suppliers = response.suppliers || response.contacts || [];
                    cfg.data.costingItems = response.costing_items || response.items || window.itemsItems || [];
                    
                    // Store globally for allocation dropdowns
                    window[sectionId + 'CostingItems'] = cfg.data.costingItems;
                    window[sectionId + 'Suppliers'] = cfg.data.suppliers;
                    
                    populateMainTable(sectionId, items);
                    
                    if (callback) callback(response);
                } else {
                    console.error('AllocationsManager: Error loading data:', response.message);
                }
            },
            error: function(xhr, status, error) {
                console.error('AllocationsManager: Failed to load data:', error);
                var tbody = $('#' + sectionId + 'MainTableBody');
                tbody.html('<tr><td colspan="10" style="text-align: center; color: #dc3545;">Failed to load data</td></tr>');
            }
        });
    }
    
    /**
     * Populate main table with items
     */
    function populateMainTable(sectionId, items) {
        var cfg = configs[sectionId];
        var tbody = $('#' + sectionId + 'MainTableBody');
        tbody.empty();
        tbody.removeClass('has-selection');
        
        if (!items || items.length === 0) {
            var colCount = $('#' + sectionId + 'MainTable thead th').length || 5;
            tbody.html('<tr><td colspan="' + colCount + '" style="text-align: center; padding: 40px; color: #6c757d;">' + 
                cfg.mainTable.emptyMessage + '</td></tr>');
            $('#' + sectionId + 'MainTableFooter').hide();
            return;
        }
        
        var totals = {};
        
        items.forEach(function(item, index) {
            var row;
            if (cfg.mainTable.renderRow) {
                row = cfg.mainTable.renderRow(item, index, cfg);
            } else {
                row = renderDefaultMainRow(item, sectionId);
            }
            
            if (row) {
                tbody.append(row);
                
                // Calculate totals
                if (cfg.mainTable.footerTotals) {
                    cfg.mainTable.footerTotals.forEach(function(ft) {
                        var value = parseFloat(item[ft.valueKey]) || 0;
                        totals[ft.colIndex] = (totals[ft.colIndex] || 0) + value;
                    });
                }
            }
        });
        
        // Update footer totals
        if (cfg.mainTable.showFooter && cfg.mainTable.footerTotals) {
            cfg.mainTable.footerTotals.forEach(function(ft) {
                var value = totals[ft.colIndex] || 0;
                var formatted = '$' + value.toLocaleString('en-AU', {minimumFractionDigits: 2, maximumFractionDigits: 2});
                $('#' + sectionId + 'FooterCol' + ft.colIndex).text(formatted);
            });
            $('#' + sectionId + 'MainTableFooter').show();
        }
        
        // Auto-select first row
        setTimeout(function() {
            var firstRow = tbody.find('tr').first();
            if (firstRow.length && firstRow.attr('data-pk')) {
                selectRow(sectionId, firstRow);
            }
        }, 100);
    }
    
    /**
     * Default row renderer (override with config.mainTable.renderRow)
     */
    function renderDefaultMainRow(item, sectionId) {
        var row = $('<tr>').attr('data-pk', item.pk || item.quotes_pk || item.invoice_pk);
        row.append($('<td>').text(item.name || item.supplier_name || '-'));
        row.append($('<td>').text(item.amount || item.total_cost || '-'));
        return row;
    }
    
    /**
     * Select a row in the main table
     */
    function selectRow(sectionId, row) {
        var cfg = configs[sectionId];
        var st = state[sectionId];
        
        // Skip if already selected
        if (row.hasClass('selected-row')) {
            return;
        }
        
        var tbody = $('#' + sectionId + 'MainTableBody');
        tbody.addClass('has-selection');
        tbody.find('tr').removeClass('selected-row');
        row.addClass('selected-row');
        
        var pk = row.attr('data-pk');
        var pdfUrl = row.attr('data-pdf-url');
        st.selectedRowPk = pk;
        
        // Update PDF viewer
        if (pdfUrl) {
            $('#' + sectionId + 'PdfViewer').attr('src', pdfUrl).show();
            $('#' + sectionId + 'ViewerPlaceholder').hide();
        } else {
            $('#' + sectionId + 'PdfViewer').hide();
            $('#' + sectionId + 'ViewerPlaceholder').show();
        }
        
        // Custom onRowSelect handler
        if (cfg.mainTable.onRowSelect) {
            cfg.mainTable.onRowSelect(row, pk, cfg);
        }
        
        // Load allocations for this item
        loadAllocations(sectionId, pk);
    }
    
    /**
     * Load allocations for a selected item
     */
    function loadAllocations(sectionId, itemPk) {
        var cfg = configs[sectionId];
        
        if (!cfg.api.loadAllocations) {
            console.log('AllocationsManager: No loadAllocations API configured');
            return;
        }
        
        var url = cfg.api.loadAllocations;
        if (typeof url === 'function') {
            url = url(itemPk);
        } else {
            url = url.replace('{pk}', itemPk);
        }
        
        $.ajax({
            url: url,
            type: 'GET',
            success: function(response) {
                if (response.status === 'success' || response.allocations) {
                    cfg.data.currentItem = response.item || response.quote || response.invoice || response.bill;
                    cfg.data.currentAllocations = response.allocations || [];
                    populateAllocationsTable(sectionId, cfg.data.currentAllocations);
                } else {
                    console.error('AllocationsManager: Error loading allocations:', response.message);
                }
            },
            error: function(xhr, status, error) {
                console.error('AllocationsManager: Failed to load allocations:', error);
            }
        });
    }
    
    /**
     * Populate allocations table
     */
    function populateAllocationsTable(sectionId, allocations) {
        var cfg = configs[sectionId];
        var st = state[sectionId];
        var tbody = $('#' + sectionId + 'AllocationsTableBody');
        tbody.empty();
        
        if (st.isNewMode || st.editMode) {
            // Editable mode
            if (!allocations || allocations.length === 0) {
                addAllocationRow(sectionId);
            } else {
                allocations.forEach(function(alloc) {
                    addAllocationRow(sectionId, alloc);
                });
            }
            $('#' + sectionId + 'AllocationFooterLabel').text('Still to Allocate:');
            $('#' + sectionId + 'AddAllocationBtn').show();
        } else {
            // View mode (read-only)
            if (!allocations || allocations.length === 0) {
                var colCount = $('#' + sectionId + 'AllocationsTable thead th').length || 4;
                tbody.html('<tr><td colspan="' + colCount + '" style="text-align: center; color: #6c757d; padding: 20px;">' + 
                    cfg.allocations.emptyMessage + '</td></tr>');
            } else {
                allocations.forEach(function(alloc) {
                    var row;
                    if (cfg.allocations.renderRow) {
                        row = cfg.allocations.renderRow(alloc, cfg);
                    } else {
                        row = renderDefaultAllocationRow(alloc, sectionId);
                    }
                    if (row) tbody.append(row);
                });
            }
            $('#' + sectionId + 'AllocationFooterLabel').text('Total Allocated:');
            $('#' + sectionId + 'AddAllocationBtn').hide();
        }
        
        // Update still to allocate / total allocated
        updateStillToAllocate(sectionId);
    }
    
    /**
     * Default allocation row renderer (read-only)
     */
    function renderDefaultAllocationRow(alloc, sectionId) {
        var row = $('<tr>').attr('data-allocation-pk', alloc.pk || alloc.quote_allocations_pk || alloc.invoice_allocation_pk);
        row.append($('<td>').text(alloc.item_name || alloc.account_name || '-'));
        var amount = parseFloat(alloc.amount) || 0;
        row.append($('<td>').text('$' + amount.toLocaleString('en-AU', {minimumFractionDigits: 2, maximumFractionDigits: 2})));
        row.append($('<td>').text(alloc.notes || '-'));
        row.append($('<td>')); // Empty cell for delete button column
        return row;
    }
    
    /**
     * Add an editable allocation row
     */
    function addAllocationRow(sectionId, allocation) {
        var cfg = configs[sectionId];
        var tbody = $('#' + sectionId + 'AllocationsTableBody');
        
        var row;
        if (cfg.allocations.renderEditableRow) {
            row = cfg.allocations.renderEditableRow(allocation, cfg, function() {
                updateStillToAllocate(sectionId);
            });
        } else {
            row = renderDefaultEditableRow(allocation, sectionId);
        }
        
        if (row) {
            tbody.append(row);
            
            // Adjust table height
            if (window.adjustAllocationsHeight && window.adjustAllocationsHeight[sectionId]) {
                window.adjustAllocationsHeight[sectionId]();
            }
        }
    }
    
    /**
     * Default editable allocation row renderer
     */
    function renderDefaultEditableRow(allocation, sectionId) {
        var cfg = configs[sectionId];
        var row = $('<tr>');
        
        if (allocation) {
            row.attr('data-allocation-pk', allocation.pk || allocation.quote_allocations_pk);
        }
        
        // Item dropdown
        var itemSelect = $('<select>').addClass('form-control form-control-sm ' + sectionId + '-allocation-item-select');
        itemSelect.append($('<option>').val('').text('Select Item...'));
        
        var costingItems = cfg.data.costingItems || window[sectionId + 'CostingItems'] || [];
        costingItems.forEach(function(item) {
            var option = $('<option>').val(item.costing_pk || item.pk).text(item.item || item.name);
            if (allocation && (allocation.item_pk === item.costing_pk || allocation.item_pk === item.pk)) {
                option.prop('selected', true);
            }
            itemSelect.append(option);
        });
        itemSelect.on('change', function() {
            updateStillToAllocate(sectionId);
        });
        row.append($('<td>').append(itemSelect));
        
        // Amount input
        var amountInput = $('<input>')
            .attr('type', 'number')
            .attr('step', '0.01')
            .addClass('form-control form-control-sm ' + sectionId + '-allocation-amount-input')
            .val(allocation ? parseFloat(allocation.amount).toFixed(2) : '')
            .on('change input', function() {
                updateStillToAllocate(sectionId);
            });
        row.append($('<td>').append(amountInput));
        
        // Notes input
        var notesInput = $('<input>')
            .attr('type', 'text')
            .addClass('form-control form-control-sm ' + sectionId + '-allocation-notes-input')
            .val(allocation ? allocation.notes || '' : '');
        row.append($('<td>').append(notesInput));
        
        // Delete button
        var deleteBtn = $('<button>')
            .addClass('btn btn-sm btn-danger')
            .html('<i class="fas fa-times"></i>')
            .on('click', function() {
                row.remove();
                updateStillToAllocate(sectionId);
                if (window.adjustAllocationsHeight && window.adjustAllocationsHeight[sectionId]) {
                    window.adjustAllocationsHeight[sectionId]();
                }
            });
        row.append($('<td>').css('text-align', 'center').append(deleteBtn));
        
        return row;
    }
    
    /**
     * Update the "Still to Allocate" display
     */
    function updateStillToAllocate(sectionId) {
        var cfg = configs[sectionId];
        var st = state[sectionId];
        
        // Get total from main table row or current item
        var totalNet = 0;
        if (st.isNewMode) {
            // New mode: get total from input field
            var totalInput = $('.new-' + sectionId + '-net');
            totalNet = parseFloat(totalInput.val()) || 0;
        } else if (cfg.data.currentItem) {
            totalNet = parseFloat(cfg.data.currentItem.total_cost || cfg.data.currentItem.total_net || 0);
        }
        
        // Calculate allocated amount
        var allocatedNet = 0;
        $('#' + sectionId + 'AllocationsTableBody tr').each(function() {
            var amountInput = $(this).find('.' + sectionId + '-allocation-amount-input');
            if (amountInput.length) {
                allocatedNet += parseFloat(amountInput.val()) || 0;
            } else {
                // Read-only row - parse from text
                var amountCell = $(this).find('td:eq(1)');
                var text = amountCell.text().replace(/[$,]/g, '');
                allocatedNet += parseFloat(text) || 0;
            }
        });
        
        var stillToAllocate = totalNet - allocatedNet;
        
        // Update display
        var displayEl = $('#' + sectionId + 'RemainingNet');
        if (displayEl.length) {
            if (st.isNewMode || st.editMode) {
                displayEl.text('$' + stillToAllocate.toLocaleString('en-AU', {minimumFractionDigits: 2, maximumFractionDigits: 2}));
                // Color coding: green if zero, red otherwise
                if (Math.abs(stillToAllocate) < 0.01) {
                    displayEl.css('color', '#90EE90');
                } else {
                    displayEl.css('color', '#ffcccc');
                }
            } else {
                // View mode: show total allocated
                displayEl.text('$' + allocatedNet.toLocaleString('en-AU', {minimumFractionDigits: 2, maximumFractionDigits: 2}));
                displayEl.css('color', '#90EE90');
            }
        }
        
        // Trigger validation callback if provided
        if (cfg.allocations.onUpdate) {
            cfg.allocations.onUpdate(sectionId, {
                total: totalNet,
                allocated: allocatedNet,
                remaining: stillToAllocate
            });
        }
        
        return { total: totalNet, allocated: allocatedNet, remaining: stillToAllocate };
    }
    
    /**
     * Get current allocations from the table
     */
    function getAllocations(sectionId) {
        var cfg = configs[sectionId];
        var allocations = [];
        
        $('#' + sectionId + 'AllocationsTableBody tr').each(function() {
            var row = $(this);
            var itemSelect = row.find('.' + sectionId + '-allocation-item-select');
            var amountInput = row.find('.' + sectionId + '-allocation-amount-input');
            var notesInput = row.find('.' + sectionId + '-allocation-notes-input');
            
            if (itemSelect.length && itemSelect.val()) {
                allocations.push({
                    item_pk: itemSelect.val(),
                    amount: parseFloat(amountInput.val()) || 0,
                    notes: notesInput.val() || '',
                    allocation_pk: row.attr('data-allocation-pk') || null
                });
            }
        });
        
        return allocations;
    }
    
    /**
     * Set new mode (for new quotes, etc.)
     */
    function setNewMode(sectionId, isNew) {
        var st = state[sectionId];
        st.isNewMode = isNew;
        st.editMode = false;
        
        if (isNew) {
            $('#' + sectionId + 'AddAllocationBtn').show();
            $('#' + sectionId + 'AllocationFooterLabel').text('Still to Allocate:');
        }
    }
    
    /**
     * Set edit mode (for updating existing items)
     */
    function setEditMode(sectionId, isEdit) {
        var st = state[sectionId];
        st.editMode = isEdit;
        st.isNewMode = false;
    }
    
    /**
     * Get configuration for a section
     */
    function getConfig(sectionId) {
        return configs[sectionId];
    }
    
    /**
     * Get state for a section
     */
    function getState(sectionId) {
        return state[sectionId];
    }
    
    // Public API
    return {
        init: init,
        loadData: loadData,
        populateMainTable: populateMainTable,
        selectRow: selectRow,
        loadAllocations: loadAllocations,
        populateAllocationsTable: populateAllocationsTable,
        addAllocationRow: addAllocationRow,
        updateStillToAllocate: updateStillToAllocate,
        getAllocations: getAllocations,
        setNewMode: setNewMode,
        setEditMode: setEditMode,
        getConfig: getConfig,
        getState: getState,
        _initialized: true
    };
})();

// Mark as initialized to prevent AJAX reload from wiping configs
window.AllocationsManager = AllocationsManager;

} // End of re-init guard
