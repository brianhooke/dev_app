/**
 * Allocations Manager Module
 * ==========================
 * Reusable JavaScript module for sections with:
 * - Main data table (top-left)
 * - Allocations table (bottom-left)
 * - PDF/Document viewer (right side)
 * 
 * Used by: Quotes, Bills (project), PO
 * 
 * Configuration:
 * - sectionId: Prefix for all element IDs (e.g., 'quote', 'bill', 'po')
 * - features: { deleteRowBtn, saveRowBtn, constructionMode, gstField }
 * - mainTable: { renderRow, onRowSelect, emptyMessage }
 * - allocations: { renderRow, renderEditableRow, columns, validate }
 * - api: { loadData, loadAllocations, save, delete }
 * - callbacks: { onSave, onDelete, onSaveSuccess, onDeleteSuccess }
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
            // Feature flags - toggle functionality on/off per section
            features: {
                deleteRowBtn: false,      // Show delete button in main table rows
                saveRowBtn: false,        // Show save/update button in main table rows
                constructionMode: false,  // Enable qty/unit/rate for allocations
                gstField: false,          // Show GST inputs in allocations
                confirmDelete: true,      // Show confirmation dialog before delete
                reloadAfterSave: false,   // Reload data after successful save
                reloadAfterDelete: true   // Reload data after successful delete
            },
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
            api: {
                save: null,     // URL for save/update endpoint
                delete: null    // URL for delete endpoint
            },
            callbacks: {
                onSave: null,          // Called before save, return false to cancel
                onDelete: null,        // Called before delete, return false to cancel
                onSaveSuccess: null,   // Called after successful save
                onDeleteSuccess: null, // Called after successful delete
                preparePayload: null   // Transform data before save
            },
            data: {
                items: [],
                currentItem: null,
                currentAllocations: [],
                pkField: 'pk'  // Field name for primary key (quotes_pk, bill_pk, etc.)
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
        
        // Set up dynamic height adjustment for allocations table
        setupAllocationsHeightAdjustment(sectionId);
        
        console.log('AllocationsManager initialized for section:', sectionId);
        return configs[sectionId];
    }
    
    /**
     * Set up dynamic height adjustment for allocations table
     * Sizes table to content up to a maximum number of rows
     */
    function setupAllocationsHeightAdjustment(sectionId) {
        var rowHeight = 28; // Matches --rt-row-height CSS variable
        var maxRows = 6;    // Maximum rows before scrolling kicks in
        
        // Create the height adjustment function for this section
        window.adjustAllocationsHeight = window.adjustAllocationsHeight || {};
        window.adjustAllocationsHeight[sectionId] = function() {
            var tbody = document.getElementById(sectionId + 'AllocationsTableBody');
            if (!tbody) return;
            
            var rowCount = tbody.querySelectorAll('tr').length;
            // Size to actual content, but cap at maxRows
            var displayRows = Math.min(Math.max(rowCount, 1), maxRows);
            var newHeight = displayRows * rowHeight;
            
            // Set the tbody height to fit content up to max
            tbody.style.maxHeight = (maxRows * rowHeight) + 'px';
            tbody.style.height = newHeight + 'px';
        };
        
        // Set up MutationObserver to auto-adjust when rows change
        var observer = new MutationObserver(function() {
            if (window.adjustAllocationsHeight[sectionId]) {
                window.adjustAllocationsHeight[sectionId]();
                
                // After height adjustment, ensure selected row in main table remains visible
                // IMPORTANT: Only scroll within the table container, never use scrollIntoView
                // as it can scroll parent containers and cause the page header to disappear
                var mainTableContainer = document.getElementById(sectionId + 'TableContainer');
                if (mainTableContainer) {
                    var selectedRow = mainTableContainer.querySelector('tr.selected-row');
                    if (selectedRow) {
                        // Use setTimeout to allow layout to settle before scrolling
                        setTimeout(function() {
                            // Calculate position relative to scroll container
                            var containerRect = mainTableContainer.getBoundingClientRect();
                            var rowRect = selectedRow.getBoundingClientRect();
                            var headerHeight = 35; // Account for sticky header height
                            var footerHeight = 35; // Account for sticky footer height
                            
                            // Check if row is below visible area (accounting for footer)
                            if (rowRect.bottom > containerRect.bottom - footerHeight) {
                                // Scroll so row is comfortably visible above footer
                                var scrollOffset = rowRect.bottom - containerRect.bottom + footerHeight + 10;
                                mainTableContainer.scrollTop += scrollOffset;
                            }
                            // Check if row is above visible area (accounting for header)
                            else if (rowRect.top < containerRect.top + headerHeight) {
                                // Scroll container up so row is visible below header
                                var scrollOffset = containerRect.top + headerHeight - rowRect.top + 10;
                                mainTableContainer.scrollTop -= scrollOffset;
                            }
                        }, 50);
                    }
                }
            }
        });
        
        // Start observing when DOM is ready (or immediately if already ready)
        var startObserving = function() {
            var tbody = document.getElementById(sectionId + 'AllocationsTableBody');
            if (tbody) {
                observer.observe(tbody, { childList: true, subtree: true });
                // Initial adjustment
                window.adjustAllocationsHeight[sectionId]();
            }
        };
        
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', function() {
                setTimeout(startObserving, 100);
            });
        } else {
            // DOM already ready
            setTimeout(startObserving, 100);
        }
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
    
    // ========================================
    // BUTTON HELPERS - Reusable button creators
    // ========================================
    
    /**
     * Create a save/update button for main table rows
     * @param {Object} item - The item data
     * @param {Object} cfg - Section configuration
     * @returns {jQuery} Button element
     */
    function createSaveButton(item, cfg) {
        var sectionId = cfg.sectionId;
        var pkField = cfg.data.pkField || 'pk';
        var itemPk = item[pkField] || item.pk || item.quotes_pk || item.bill_pk;
        
        return $('<button>')
            .addClass('btn btn-sm btn-success ' + sectionId + '-save-btn')
            .attr('data-pk', itemPk)
            .html('<i class="fas fa-save"></i>')
            .attr('title', 'Save')
            .on('click', function(e) {
                e.stopPropagation();
                saveItem(sectionId, itemPk);
            });
    }
    
    /**
     * Create an update button (text version) for main table rows
     * @param {Object} item - The item data
     * @param {Object} cfg - Section configuration
     * @returns {jQuery} Button element
     */
    function createUpdateButton(item, cfg) {
        var sectionId = cfg.sectionId;
        var pkField = cfg.data.pkField || 'pk';
        var itemPk = item[pkField] || item.pk || item.quotes_pk || item.bill_pk;
        
        return $('<button>')
            .addClass('btn btn-sm btn-warning ' + sectionId + '-update-btn')
            .attr('data-pk', itemPk)
            .text('Update')
            .attr('title', 'Update')
            .on('click', function(e) {
                e.stopPropagation();
                if (cfg.callbacks.onUpdate) {
                    cfg.callbacks.onUpdate(item, cfg);
                } else {
                    saveItem(sectionId, itemPk);
                }
            });
    }
    
    /**
     * Create a delete button for main table rows
     * @param {Object} item - The item data
     * @param {Object} cfg - Section configuration
     * @returns {jQuery} Button element
     */
    function createDeleteButton(item, cfg) {
        var sectionId = cfg.sectionId;
        var pkField = cfg.data.pkField || 'pk';
        var itemPk = item[pkField] || item.pk || item.quotes_pk || item.bill_pk;
        var displayName = item.supplier_quote_number || item.bill_number || item.name || itemPk;
        
        return $('<button>')
            .addClass('btn btn-sm btn-danger ' + sectionId + '-delete-btn')
            .attr('data-pk', itemPk)
            .html('<i class="fas fa-trash"></i>')
            .attr('title', 'Delete')
            .on('click', function(e) {
                e.stopPropagation();
                deleteItem(sectionId, itemPk, displayName, $(this).closest('tr'));
            });
    }
    
    /**
     * Create a delete button for allocation rows
     * @param {jQuery} row - The row element
     * @param {Object} cfg - Section configuration
     * @param {Function} onChange - Callback when allocation changes
     * @returns {jQuery} Button element
     */
    function createAllocationDeleteButton(row, cfg, onChange) {
        var sectionId = cfg.sectionId;
        
        return $('<button>')
            .addClass('btn btn-sm btn-danger')
            .html('<i class="fas fa-times"></i>')
            .attr('title', 'Remove row')
            .on('click', function() {
                row.remove();
                if (onChange) onChange();
                if (window.adjustAllocationsHeight && window.adjustAllocationsHeight[sectionId]) {
                    window.adjustAllocationsHeight[sectionId]();
                }
            });
    }
    
    // ========================================
    // SAVE / DELETE HANDLERS
    // ========================================
    
    /**
     * Save/update an item
     * @param {string} sectionId - Section identifier
     * @param {string|number} itemPk - Primary key of item to save
     */
    function saveItem(sectionId, itemPk) {
        var cfg = configs[sectionId];
        var st = state[sectionId];
        
        // Get allocations
        var allocations = getAllocations(sectionId);
        
        // Validate allocations
        if (!allocations || allocations.length === 0) {
            alert('Please add at least one allocation.');
            return;
        }
        
        // Pre-save callback - can cancel save by returning false
        if (cfg.callbacks.onSave) {
            var shouldContinue = cfg.callbacks.onSave(itemPk, allocations, cfg);
            if (shouldContinue === false) return;
        }
        
        // Build payload
        var payload = {
            pk: itemPk,
            allocations: allocations
        };
        
        // Allow custom payload transformation
        if (cfg.callbacks.preparePayload) {
            payload = cfg.callbacks.preparePayload(payload, cfg);
        }
        
        // Check if save URL is configured
        if (!cfg.api.save) {
            console.error('AllocationsManager: No save API configured for', sectionId);
            return;
        }
        
        var url = cfg.api.save;
        if (typeof url === 'function') {
            url = url(itemPk);
        }
        
        $.ajax({
            url: url,
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken()
            },
            data: JSON.stringify(payload),
            success: function(response) {
                if (response.status === 'success') {
                    // Success callback
                    if (cfg.callbacks.onSaveSuccess) {
                        cfg.callbacks.onSaveSuccess(response, itemPk, cfg);
                    } else {
                        alert('Saved successfully!');
                    }
                    
                    // Reload data if configured
                    if (cfg.features.reloadAfterSave && window.projectPk) {
                        loadData(sectionId, { projectPk: window.projectPk });
                    }
                } else {
                    alert('Error: ' + (response.message || 'Unknown error'));
                }
            },
            error: function(xhr, status, error) {
                alert('Failed to save: ' + error);
            }
        });
    }
    
    /**
     * Delete an item
     * @param {string} sectionId - Section identifier
     * @param {string|number} itemPk - Primary key of item to delete
     * @param {string} displayName - Display name for confirmation
     * @param {jQuery} row - The row element (optional, for immediate removal)
     */
    function deleteItem(sectionId, itemPk, displayName, row) {
        var cfg = configs[sectionId];
        
        // Confirmation dialog
        if (cfg.features.confirmDelete) {
            if (!confirm('Are you sure you want to delete "' + displayName + '"?')) {
                return;
            }
        }
        
        // Pre-delete callback - can cancel delete by returning false
        if (cfg.callbacks.onDelete) {
            var shouldContinue = cfg.callbacks.onDelete(itemPk, cfg);
            if (shouldContinue === false) return;
        }
        
        // Check if delete URL is configured
        if (!cfg.api.delete) {
            console.error('AllocationsManager: No delete API configured for', sectionId);
            return;
        }
        
        var url = cfg.api.delete;
        if (typeof url === 'function') {
            url = url(itemPk);
        }
        
        $.ajax({
            url: url,
            method: 'DELETE',
            headers: { 
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken()
            },
            data: JSON.stringify({ pk: itemPk }),
            success: function(response) {
                if (response.status === 'success') {
                    // Success callback
                    if (cfg.callbacks.onDeleteSuccess) {
                        cfg.callbacks.onDeleteSuccess(response, itemPk, cfg);
                    }
                    
                    // Reload data if configured
                    if (cfg.features.reloadAfterDelete && window.projectPk) {
                        loadData(sectionId, { projectPk: window.projectPk });
                    } else if (row) {
                        // Just remove the row
                        row.remove();
                    }
                } else {
                    alert('Error: ' + (response.message || 'Failed to delete'));
                }
            },
            error: function(xhr, status, error) {
                alert('Failed to delete: ' + error);
            }
        });
    }
    
    /**
     * Create a bill/allocation row with editable fields
     * This is a reusable row builder for allocation tables
     * 
     * @param {Object} options - Configuration options
     * @param {Object} options.allocation - Allocation data (or null for new row)
     * @param {boolean} options.isConstruction - Whether in construction mode
     * @param {Array} options.costingItems - Array of costing items for dropdown
     * @param {Function} options.onUpdate - Callback when values change (for validation)
     * @param {Object} options.api - API endpoints { save: '/url/{pk}/', delete: '/url/{pk}/' }
     * @returns {jQuery} The created row element
     */
    function createEditableAllocationRow(options) {
        var alloc = options.allocation || {};
        var isConstruction = options.isConstruction || false;
        var costingItems = options.costingItems || [];
        var onUpdate = options.onUpdate || function() {};
        var api = options.api || {};
        
        var row = $('<tr>').attr('data-allocation-pk', alloc.allocation_pk || alloc.quote_allocations_pk || '');
        
        // Helper function to save allocation to database (debounced)
        var saveTimeout = null;
        function saveAllocation() {
            clearTimeout(saveTimeout);
            saveTimeout = setTimeout(function() {
                var pk = row.attr('data-allocation-pk');
                if (!pk || !api.save) return;
                
                var data;
                if (isConstruction) {
                    // Construction mode: save qty, rate, unit, amount (calculated)
                    var qty = parseFloat(row.find('.allocation-qty-input').val()) || 0;
                    var rate = parseFloat(row.find('.allocation-rate-input').val()) || 0;
                    data = {
                        item_pk: row.find('.allocation-item-select').val() || null,
                        qty: qty,
                        rate: rate,
                        unit: row.find('.allocation-unit-input').val() || '',
                        amount: qty * rate,
                        gst_amount: 0,
                        notes: row.find('.allocation-notes-input').val() || ''
                    };
                } else {
                    // Non-construction mode: save net and gst
                    data = {
                        item_pk: row.find('.allocation-item-select').val() || null,
                        amount: parseFloat(row.find('.allocation-net-input').val()) || 0,
                        gst_amount: parseFloat(row.find('.allocation-gst-input').val()) || 0,
                        notes: row.find('.allocation-notes-input').val() || ''
                    };
                }
                
                var url = typeof api.save === 'function' ? api.save(pk) : api.save.replace('{pk}', pk);
                
                $.ajax({
                    url: url,
                    type: 'POST',
                    contentType: 'application/json',
                    data: JSON.stringify(data),
                    success: function(response) {
                        console.log('Allocation saved:', pk);
                    },
                    error: function(xhr, status, error) {
                        console.error('Error saving allocation:', error);
                    }
                });
            }, 500); // Debounce 500ms
        }
        
        // 1. Item dropdown (populated with costing items)
        var itemSelect = $('<select>').addClass('form-control form-control-sm allocation-item-select');
        itemSelect.append($('<option>').val('').text('Select Item...'));
        
        // Populate with costing items, grouped by category
        var currentCategory = null;
        costingItems.forEach(function(item) {
            // Add category optgroup if category changed
            if (item.category__category !== currentCategory) {
                currentCategory = item.category__category;
                itemSelect.append($('<optgroup>').attr('label', currentCategory || 'Uncategorized'));
            }
            var option = $('<option>').val(item.costing_pk).text(item.item);
            // Store unit as data attribute for construction mode
            option.attr('data-unit', item.unit__unit_name || item.unit || '');
            if (alloc.item_pk && item.costing_pk == alloc.item_pk) {
                option.prop('selected', true);
            }
            itemSelect.find('optgroup').last().append(option);
        });
        
        if (isConstruction) {
            // Construction mode: Item | Unit | Qty | $ Rate | $ Amount | Notes | Del
            
            // Item dropdown with unit auto-populate
            itemSelect.on('change', function() {
                var selectedOption = $(this).find('option:selected');
                var unit = selectedOption.attr('data-unit') || '';
                row.find('.allocation-unit-display').text(unit);
                row.find('.allocation-unit-input').val(unit);
                saveAllocation();
                onUpdate();
            });
            row.append($('<td>').append(itemSelect));
            
            // 2. Unit (read-only, auto-populated from item)
            var selectedUnit = alloc.unit || '';
            var unitDisplay = $('<span>').addClass('allocation-unit-display').text(selectedUnit);
            var unitInput = $('<input>').attr('type', 'hidden').addClass('allocation-unit-input').val(selectedUnit);
            row.append($('<td>').append(unitDisplay).append(unitInput));
            
            // 3. Qty input
            var qtyInput = $('<input>')
                .attr('type', 'number')
                .attr('step', '0.01')
                .addClass('form-control form-control-sm allocation-qty-input')
                .val(alloc.qty ? parseFloat(alloc.qty).toFixed(2) : '')
                .on('change input', function() {
                    // Calculate amount = qty * rate
                    var qty = parseFloat($(this).val()) || 0;
                    var rate = parseFloat(row.find('.allocation-rate-input').val()) || 0;
                    var amount = (qty * rate).toFixed(2);
                    row.find('.allocation-amount-display').text('$' + parseFloat(amount).toLocaleString('en-AU', {minimumFractionDigits: 2, maximumFractionDigits: 2}));
                    row.find('.allocation-net-input').val(amount);
                    onUpdate();
                    saveAllocation();
                });
            row.append($('<td>').append(qtyInput));
            
            // 4. $ Rate input
            var rateInput = $('<input>')
                .attr('type', 'number')
                .attr('step', '0.01')
                .addClass('form-control form-control-sm allocation-rate-input')
                .val(alloc.rate ? parseFloat(alloc.rate).toFixed(2) : '')
                .on('change input', function() {
                    // Calculate amount = qty * rate
                    var qty = parseFloat(row.find('.allocation-qty-input').val()) || 0;
                    var rate = parseFloat($(this).val()) || 0;
                    var amount = (qty * rate).toFixed(2);
                    row.find('.allocation-amount-display').text('$' + parseFloat(amount).toLocaleString('en-AU', {minimumFractionDigits: 2, maximumFractionDigits: 2}));
                    row.find('.allocation-net-input').val(amount);
                    onUpdate();
                    saveAllocation();
                });
            row.append($('<td>').append(rateInput));
            
            // 5. $ Amount (calculated, read-only display but hidden input for data)
            var calcAmount = alloc.amount ? parseFloat(alloc.amount) : 0;
            var amountDisplay = $('<span>').addClass('allocation-amount-display')
                .text('$' + calcAmount.toLocaleString('en-AU', {minimumFractionDigits: 2, maximumFractionDigits: 2}));
            var amountHidden = $('<input>').attr('type', 'hidden')
                .addClass('allocation-net-input').val(calcAmount.toFixed(2));
            row.append($('<td>').append(amountDisplay).append(amountHidden));
            
            // 6. Notes input
            var notesInput = $('<input>')
                .attr('type', 'text')
                .addClass('form-control form-control-sm allocation-notes-input')
                .attr('placeholder', 'Notes...')
                .val(alloc.notes || '')
                .on('blur', saveAllocation);
            row.append($('<td>').append(notesInput));
            
        } else {
            // Non-construction mode: Item | $ Net | $ GST | Notes | Del
            
            // Save on change and update validation
            itemSelect.on('change', function() {
                saveAllocation();
                onUpdate();
            });
            row.append($('<td>').append(itemSelect));
            
            // 2. $ Net input
            var netInput = $('<input>')
                .attr('type', 'number')
                .attr('step', '0.01')
                .attr('min', '0')
                .addClass('form-control form-control-sm allocation-net-input')
                .val(alloc.amount || '')
                .on('input', function() {
                    var value = $(this).val();
                    if (parseFloat(value) < 0) {
                        $(this).val(0);
                        return;
                    }
                    if (value.includes('.')) {
                        var parts = value.split('.');
                        if (parts[1] && parts[1].length > 2) {
                            $(this).val(parseFloat(value).toFixed(2));
                        }
                    }
                    // Auto-calculate GST as 10%
                    var gstInputEl = $(this).closest('tr').find('.allocation-gst-input');
                    if (!gstInputEl.data('manually-edited')) {
                        var netVal = parseFloat($(this).val());
                        if (!isNaN(netVal)) {
                            gstInputEl.val((netVal * 0.1).toFixed(2));
                        }
                    }
                    onUpdate();
                    saveAllocation();
                });
            row.append($('<td>').append(netInput));
            
            // 3. $ GST input
            var gstInput = $('<input>')
                .attr('type', 'number')
                .attr('step', '0.01')
                .attr('min', '0')
                .addClass('form-control form-control-sm allocation-gst-input')
                .val(alloc.gst_amount || '')
                .on('focus', function() {
                    $(this).data('manually-edited', true);
                })
                .on('input', function() {
                    var value = $(this).val();
                    if (parseFloat(value) < 0) {
                        $(this).val(0);
                        return;
                    }
                    if (value.includes('.')) {
                        var parts = value.split('.');
                        if (parts[1] && parts[1].length > 2) {
                            $(this).val(parseFloat(value).toFixed(2));
                        }
                    }
                    onUpdate();
                    saveAllocation();
                });
            row.append($('<td>').append(gstInput));
            
            // 4. Notes input
            var notesInput = $('<input>')
                .attr('type', 'text')
                .addClass('form-control form-control-sm allocation-notes-input')
                .attr('placeholder', 'Notes...')
                .val(alloc.notes || '')
                .on('blur', saveAllocation);
            row.append($('<td>').append(notesInput));
        }
        
        // Delete button (both modes)
        var deleteBtn = $('<button>')
            .addClass('btn btn-sm btn-danger delete-allocation-btn')
            .html('<i class="fas fa-times"></i>')
            .on('click', function() {
                var pk = row.attr('data-allocation-pk');
                if (pk && api.delete) {
                    var url = typeof api.delete === 'function' ? api.delete(pk) : api.delete.replace('{pk}', pk);
                    $.ajax({
                        url: url,
                        type: 'POST',
                        success: function(response) {
                            console.log('Allocation deleted:', pk);
                            row.remove();
                            onUpdate();
                        },
                        error: function(xhr, status, error) {
                            console.error('Error deleting allocation:', error);
                        }
                    });
                } else {
                    row.remove();
                    onUpdate();
                }
            });
        row.append($('<td>').append(deleteBtn));
        
        return row;
    }
    
    /**
     * Get CSRF token from cookie
     */
    function getCsrfToken() {
        var name = 'csrftoken';
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
        // Button helpers - use these in custom renderRow functions
        createSaveButton: createSaveButton,
        createUpdateButton: createUpdateButton,
        createDeleteButton: createDeleteButton,
        createAllocationDeleteButton: createAllocationDeleteButton,
        // Direct action methods
        saveItem: saveItem,
        deleteItem: deleteItem,
        // Reusable row builders
        createEditableAllocationRow: createEditableAllocationRow,
        _initialized: true
    };
})();

// Mark as initialized to prevent AJAX reload from wiping configs
window.AllocationsManager = AllocationsManager;

} // End of re-init guard
