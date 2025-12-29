/*
================================================================================
ALLOCATIONS MANAGER MODULE - allocations_layout.js
================================================================================
Reusable JavaScript module for sections with:
- Main data table (top-left)
- Allocations table (bottom-left)  
- PDF/Document viewer (right side)

Used by: quotes.html, bills_project.html, po.html

================================================================================
FUNCTION SUMMARY
================================================================================

INITIALIZATION & SETUP
--------------------------------------
init(config)                        - Initialize a section with configuration
setupAllocationsHeightAdjustment(sectionId) - Set up dynamic height adjustment for allocations table
bindEventHandlers(sectionId)        - Bind event handlers (Add Row, Save, row clicks)

DATA LOADING
--------------------------------------
loadData(sectionId, params, callback) - Load data via AJAX and populate main table
loadAllocations(sectionId, itemPk)  - Load allocations for a selected item

TABLE POPULATION
--------------------------------------
populateMainTable(sectionId, items) - Populate main table with items
renderDefaultMainRow(item, sectionId) - Default row renderer for main table
populateAllocationsTable(sectionId, allocations) - Populate allocations table
renderDefaultAllocationRow(alloc, sectionId) - Default read-only allocation row
addAllocationRow(sectionId, allocation) - Add an editable allocation row
renderDefaultEditableRow(allocation, sectionId) - Default editable allocation row

ROW SELECTION & STATE
--------------------------------------
selectRow(sectionId, row)           - Select a row in main table, load PDF & allocations
updateStillToAllocate(sectionId)    - Update "Still to Allocate" display (Net & GST)
getAllocations(sectionId)           - Extract allocation data from table inputs
setNewMode(sectionId, isNew)        - Set new mode (for creating new items)
setEditMode(sectionId, isEdit)      - Set edit mode (for updating existing items)
getConfig(sectionId)                - Get configuration for a section
getState(sectionId)                 - Get state for a section

BUTTON HELPERS (For custom renderRow functions)
--------------------------------------
createSaveButton(item, cfg)         - Create save icon button for main table rows
createUpdateButton(item, cfg)       - Create "Update" text button for main table rows
createDeleteButton(item, cfg)       - Create delete icon button for main table rows
createAllocationDeleteButton(row, cfg, onChange) - Create delete button for allocation rows

SAVE / DELETE HANDLERS
--------------------------------------
saveItem(sectionId, itemPk)         - Save/update an item's allocations via AJAX
deleteItem(sectionId, itemPk, displayName, row) - Delete an item via AJAX

REUSABLE ROW BUILDERS
--------------------------------------
createEditableAllocationRow(options) - Create editable allocation row with auto-save
                                       Supports construction mode (Qty/Rate/Amount)
                                       and non-construction mode (Net/GST)

INTERNAL HELPERS
--------------------------------------
getCsrfToken()                      - Get CSRF token from cookie for AJAX requests

================================================================================
CONFIGURATION OPTIONS
================================================================================
{
    sectionId: 'quote',              // Required: prefix for all element IDs
    features: {
        deleteRowBtn: false,         // Show delete button in main table rows
        saveRowBtn: false,           // Show save/update button in main table rows
        constructionMode: false,     // Enable qty/unit/rate for allocations
        gstField: false,             // Show GST inputs in allocations
        confirmDelete: true,         // Show confirmation dialog before delete
        reloadAfterSave: false,      // Reload data after successful save
        reloadAfterDelete: true,     // Reload data after successful delete
        showSaveButton: true,        // Show Save button in allocations footer
        alwaysShowAddButton: false   // Always show Add Row button
    },
    mainTable: {
        emptyMessage: 'No items.',
        showFooter: true,
        footerTotals: [],            // [{colIndex, valueKey}] for totals
        renderRow: function(item, index, cfg) { return $('<tr>'); },
        onRowSelect: function(row, pk, cfg) { },
        onAllocationsLoaded: function(sectionId, allocations) { }
    },
    allocations: {
        emptyMessage: 'No allocations.',
        editable: false,
        showStillToAllocate: true,
        renderRow: function(alloc, cfg) { return $('<tr>'); },
        renderEditableRow: function(alloc, cfg, onChange) { return $('<tr>'); },
        onUpdate: function(sectionId, totals) { }
    },
    api: {
        loadData: '/api/url/{pk}/',
        loadAllocations: '/api/url/{pk}/',
        save: '/api/url/',
        delete: '/api/url/{pk}/'
    },
    callbacks: {
        onSave: function(itemPk, allocations, cfg) { },
        onDelete: function(itemPk, cfg) { },
        onSaveSuccess: function(response, itemPk, cfg) { },
        onDeleteSuccess: function(response, itemPk, cfg) { },
        onUpdate: function(item, cfg, row) { },
        preparePayload: function(payload, cfg) { return payload; }
    },
    data: {
        items: [],
        currentItem: null,
        currentAllocations: [],
        pkField: 'pk'                // Primary key field name
    }
}
================================================================================
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
    
    // ========================================
    // NOTE: Utility functions moved to utils.js
    // ========================================
    // formatMoney, escapeHtml, getProjectPkFromUrl, isConstructionProject,
    // applyColumnStyles, recalculateFooterTotals are now in utils.js
    
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
                reloadAfterDelete: true,  // Reload data after successful delete
                showSaveButton: true,     // Show Save button in allocations footer
                alwaysShowAddButton: false, // Always show Add Row button (vs only in edit mode)
                emailViewer: false        // Enable email link click to show email in viewer
            },
            mainTable: {
                emptyMessage: 'No items found.',
                showFooter: true,
                footerTotals: []  // Array of {colIndex, valueKey} for calculating totals
            },
            allocations: {
                emptyMessage: 'No allocations.',
                editable: false,
                showStillToAllocate: true,
                columnWidths: null  // Array of width strings to apply via Utils.applyColumnStyles
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
            editMode: false,
            pendingSaveItemPk: null,  // For Update button on non-selected rows
            showingEmail: false       // Track if viewer is showing email vs PDF
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
        var fallbackRowHeight = 28; // Fallback if no rows to measure
        var maxRows = 6;    // Maximum rows before scrolling kicks in
        
        // Create the height adjustment function for this section
        window.adjustAllocationsHeight = window.adjustAllocationsHeight || {};
        window.adjustAllocationsHeight[sectionId] = function() {
            var tbody = document.getElementById(sectionId + 'AllocationsTableBody');
            if (!tbody) return;
            
            var rows = tbody.querySelectorAll('tr');
            var rowCount = rows.length;
            
            // Measure actual row height from first row, or use fallback
            var actualRowHeight = fallbackRowHeight;
            if (rows.length > 0) {
                actualRowHeight = rows[0].offsetHeight || fallbackRowHeight;
            }
            
            // Size to actual content, but cap at maxRows
            var displayRows = Math.min(Math.max(rowCount, 1), maxRows);
            var newHeight = displayRows * actualRowHeight;
            var maxHeight = maxRows * actualRowHeight;
            
            // Set the tbody height to fit content up to max
            tbody.style.maxHeight = maxHeight + 'px';
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
        
        // Save allocations button
        $(document).off('click', '#' + sectionId + 'SaveAllocationsBtn')
            .on('click', '#' + sectionId + 'SaveAllocationsBtn', function() {
                var st = state[sectionId];
                var cfg = configs[sectionId];
                
                // In new mode, call custom save handler if defined
                if (st.isNewMode && cfg.callbacks && cfg.callbacks.onSaveNew) {
                    cfg.callbacks.onSaveNew(sectionId, cfg);
                } else if (st.selectedRowPk) {
                    saveItem(sectionId, st.selectedRowPk);
                }
            });
        
        // Main table row click - use event delegation
        $(document).off('click', '#' + sectionId + 'MainTableBody tr')
            .on('click', '#' + sectionId + 'MainTableBody tr', function(e) {
                // Don't trigger on buttons or email links
                if ($(e.target).closest('button, .email-link').length) return;
                
                // Restore PDF if we were showing email
                var st = state[sectionId];
                if (cfg.features.emailViewer && st && st.showingEmail) {
                    restorePdfViewer(sectionId, $(this));
                }
                
                selectRow(sectionId, $(this));
            });
        
        // Email viewer feature - email link click handler
        if (cfg.features.emailViewer) {
            $(document).off('click', '#' + sectionId + 'MainTableBody .email-link')
                .on('click', '#' + sectionId + 'MainTableBody .email-link', function(e) {
                    e.preventDefault();
                    e.stopPropagation();
                    showEmailInViewer(sectionId, $(this));
                });
            
            // Focus handler for inputs/selects - restore PDF when focused
            $(document).off('focus', '#' + sectionId + 'MainTableBody input, #' + sectionId + 'MainTableBody select')
                .on('focus', '#' + sectionId + 'MainTableBody input, #' + sectionId + 'MainTableBody select', function() {
                    var st = state[sectionId];
                    if (st && st.showingEmail) {
                        restorePdfViewer(sectionId, $(this).closest('tr'));
                    }
                });
        }
    }
    
    /**
     * Show email content in the viewer (for emailViewer feature)
     */
    function showEmailInViewer(sectionId, emailLink) {
        var st = state[sectionId];
        
        var emailHtml = emailLink.attr('data-email-html') || '';
        var emailText = emailLink.attr('data-email-text') || '';
        var emailSubject = emailLink.attr('data-email-subject') || '';
        var emailFrom = emailLink.attr('data-email-from') || '';
        
        // Create HTML content with email header
        var emailContent = '<div style="padding: 20px; font-family: Arial, sans-serif;">';
        emailContent += '<div style="border-bottom: 2px solid #ddd; margin-bottom: 20px; padding-bottom: 10px;">';
        emailContent += '<p style="margin: 5px 0;"><strong>From:</strong> ' + emailFrom + '</p>';
        emailContent += '<p style="margin: 5px 0;"><strong>Subject:</strong> ' + emailSubject + '</p>';
        emailContent += '</div>';
        
        // Add email body (HTML or text)
        if (emailHtml) {
            emailContent += emailHtml;
        } else if (emailText) {
            emailContent += '<pre style="white-space: pre-wrap; font-family: Arial, sans-serif;">' + emailText + '</pre>';
        } else {
            emailContent += '<p><em>No email content available</em></p>';
        }
        emailContent += '</div>';
        
        // Create a blob URL for the HTML content
        var blob = new Blob([emailContent], { type: 'text/html' });
        var blobUrl = URL.createObjectURL(blob);
        
        // Load HTML in iframe
        $('#' + sectionId + 'PdfViewer').attr('src', blobUrl).show();
        $('#' + sectionId + 'ViewerPlaceholder').hide();
        
        // Mark that we're showing email
        st.showingEmail = true;
    }
    
    /**
     * Restore PDF in the viewer (for emailViewer feature)
     */
    function restorePdfViewer(sectionId, row) {
        var st = state[sectionId];
        if (!st.showingEmail) return;
        
        var pdfUrl = row.attr('data-pdf-url');
        if (pdfUrl) {
            $('#' + sectionId + 'PdfViewer').attr('src', pdfUrl).show();
            $('#' + sectionId + 'ViewerPlaceholder').hide();
        } else {
            $('#' + sectionId + 'PdfViewer').hide();
            $('#' + sectionId + 'ViewerPlaceholder').show();
        }
        st.showingEmail = false;
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
                if (response.status === 'success' || response.items || response.quotes || response.invoices || response.bills || response.variations) {
                    // Normalize response data
                    var items = response.items || response.quotes || response.invoices || response.bills || response.variations || [];
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
        if (!cfg) {
            console.error('AllocationsManager.populateMainTable: No config found for sectionId:', sectionId);
            return;
        }
        var tbody = $('#' + sectionId + 'MainTableBody');
        if (!tbody.length) {
            console.error('AllocationsManager.populateMainTable: tbody not found for:', sectionId + 'MainTableBody');
            return;
        }
        tbody.empty();
        tbody.removeClass('has-selection');
        
        // Store items in config for later use (e.g., selectRow needs to find currentItem)
        cfg.data.items = items || [];
        
        if (!items || items.length === 0) {
            var colCount = $('#' + sectionId + 'MainTable thead th').length || 5;
            tbody.html('<tr><td colspan="' + colCount + '" style="text-align: center; padding: 40px; color: #6c757d;">' + 
                cfg.mainTable.emptyMessage + '</td></tr>');
            // Only hide footer if alwaysShowFooter is not set
            if (!cfg.mainTable.alwaysShowFooter) {
                $('#' + sectionId + 'MainTableFooter').hide();
            }
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
                var formatted = '$' + Utils.formatMoney(value);
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
     * Recalculate footer totals based on current table rows
     * Called after a row is removed to update the totals
     */
    function recalculateFooterTotals(sectionId) {
        var cfg = configs[sectionId];
        if (!cfg || !cfg.mainTable.showFooter || !cfg.mainTable.footerTotals) {
            return;
        }
        
        var totals = {};
        var tbody = $('#' + sectionId + 'MainTableBody');
        
        // Sum values from remaining rows
        tbody.find('tr[data-pk]').each(function() {
            var row = $(this);
            cfg.mainTable.footerTotals.forEach(function(ft) {
                // Get the cell at the specified column index (1-indexed for display)
                var cell = row.find('td').eq(ft.colIndex - 1);
                var text = cell.text().replace(/[$,]/g, '');
                var value = parseFloat(text) || 0;
                totals[ft.colIndex] = (totals[ft.colIndex] || 0) + value;
            });
        });
        
        // Update footer cells
        cfg.mainTable.footerTotals.forEach(function(ft) {
            var value = totals[ft.colIndex] || 0;
            var formatted = '$' + Utils.formatMoney(value);
            $('#' + sectionId + 'FooterCol' + ft.colIndex).text(formatted);
        });
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
        
        // Skip if row has no pk (empty state row or new row)
        var pk = row.attr('data-pk');
        if (!pk || row.hasClass('new-variation-row') || row.hasClass('new-quote-row')) {
            return;
        }
        
        // Skip if already selected
        if (row.hasClass('selected-row')) {
            return;
        }
        
        var tbody = $('#' + sectionId + 'MainTableBody');
        tbody.addClass('has-selection');
        tbody.find('tr').removeClass('selected-row');
        row.addClass('selected-row');
        var pdfUrl = row.attr('data-pdf-url');
        st.selectedRowPk = pk;
        
        // Find and set currentItem from items array
        if (cfg.data.items && cfg.data.items.length) {
            var pkField = cfg.data.pkField || cfg.mainTable.pkField || 'pk';
            cfg.data.currentItem = cfg.data.items.find(function(item) {
                var itemPk = item[pkField] || item.pk || item.quotes_pk || item.invoice_pk || item.hc_variation_pk;
                return String(itemPk) === String(pk);
            }) || null;
            console.log('selectRow currentItem:', cfg.data.currentItem);
        }
        
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
                    // Only set currentItem from response if not already set by onRowSelect
                    // This preserves values like total_net/total_gst from the main table row
                    var responseItem = response.item || response.quote || response.invoice || response.bill;
                    if (!cfg.data.currentItem) {
                        cfg.data.currentItem = responseItem;
                    } else if (responseItem) {
                        // Merge response data into existing currentItem without overwriting
                        Object.keys(responseItem).forEach(function(key) {
                            if (cfg.data.currentItem[key] === undefined) {
                                cfg.data.currentItem[key] = responseItem[key];
                            }
                        });
                    }
                    cfg.data.currentAllocations = response.allocations || [];
                    populateAllocationsTable(sectionId, cfg.data.currentAllocations);
                    
                    // Call onAllocationsLoaded callback if provided
                    if (cfg.mainTable && cfg.mainTable.onAllocationsLoaded) {
                        cfg.mainTable.onAllocationsLoaded(sectionId, cfg.data.currentAllocations);
                    }
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
        
        // Determine if we should show editable controls
        var showEditable = st.isNewMode || st.editMode || cfg.features.alwaysShowAddButton;
        
        if (st.isNewMode || st.editMode) {
            // Editable mode - show editable allocation rows
            if (!allocations || allocations.length === 0) {
                addAllocationRow(sectionId);
            } else {
                allocations.forEach(function(alloc) {
                    addAllocationRow(sectionId, alloc);
                });
            }
        } else if (cfg.features.alwaysShowAddButton) {
            // Always show editable rows (bills_project style)
            if (!allocations || allocations.length === 0) {
                addAllocationRow(sectionId);
            } else {
                allocations.forEach(function(alloc) {
                    addAllocationRow(sectionId, alloc);
                });
            }
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
        }
        
        // Update footer label and button visibility based on config
        console.log('populateAllocationsTable:', sectionId, 'showEditable:', showEditable, 'isNewMode:', st.isNewMode, 'editMode:', st.editMode, 'alwaysShowAddButton:', cfg.features.alwaysShowAddButton);
        console.log('Footer exists:', $('#' + sectionId + 'AllocationsFooter').length, 'Footer HTML:', $('#' + sectionId + 'AllocationsFooter').html() ? $('#' + sectionId + 'AllocationsFooter').html().substring(0, 200) : 'EMPTY');
        console.log('Button elements found - AddBtn:', $('#' + sectionId + 'AddAllocationBtn').length, 'SaveBtn:', $('#' + sectionId + 'SaveAllocationsBtn').length);
        if (showEditable) {
            $('#' + sectionId + 'AllocationFooterLabel').text('Still to Allocate:');
            $('#' + sectionId + 'AddAllocationBtn').show();
            console.log('Showing AddAllocationBtn for', sectionId);
            // Only show Save button if configured
            if (cfg.features.showSaveButton) {
                $('#' + sectionId + 'SaveAllocationsBtn').show();
                console.log('Showing SaveAllocationsBtn for', sectionId);
            } else {
                $('#' + sectionId + 'SaveAllocationsBtn').hide();
            }
        } else {
            $('#' + sectionId + 'AllocationFooterLabel').text('Total Allocated:');
            $('#' + sectionId + 'AddAllocationBtn').hide();
            $('#' + sectionId + 'SaveAllocationsBtn').hide();
        }
        
        // Update still to allocate / total allocated
        updateStillToAllocate(sectionId);
        
        // Check for pending save (triggered by Update button on non-selected row)
        if (st.pendingSaveItemPk) {
            var itemPkToSave = st.pendingSaveItemPk;
            st.pendingSaveItemPk = null; // Clear flag
            // Small delay to ensure UI is fully rendered
            setTimeout(function() {
                saveItem(sectionId, itemPkToSave);
            }, 100);
        }
        
        // Apply column widths if configured
        if (cfg.allocations.columnWidths) {
            Utils.applyColumnStyles(sectionId, cfg.allocations.columnWidths, { addEditableClass: showEditable });
        }
    }
    
    /**
     * Default allocation row renderer (read-only)
     */
    function renderDefaultAllocationRow(alloc, sectionId) {
        var row = $('<tr>').attr('data-allocation-pk', alloc.pk || alloc.quote_allocations_pk || alloc.invoice_allocation_pk);
        row.append($('<td>').text(alloc.item_name || alloc.account_name || '-'));
        var amount = parseFloat(alloc.amount) || 0;
        row.append($('<td>').text('$' + Utils.formatMoney(amount)));
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
        row.append($('<td>').addClass('col-action-first').attr('data-edit-only', 'true').append(deleteBtn));
        
        return row;
    }
    
    /**
     * Update the "Still to Allocate" display
     * Supports both Net-only (quotes) and Net+GST (bills) modes
     */
    function updateStillToAllocate(sectionId) {
        var cfg = configs[sectionId];
        var st = state[sectionId];
        var hasGst = cfg.features && cfg.features.gstField;
        var cls = sectionId + '-allocation';
        
        // Get totals from main table row or current item
        var totalNet = 0, totalGst = 0;
        if (st.isNewMode) {
            // New mode: get total from input field
            var totalInput = $('.new-' + sectionId + '-net');
            totalNet = parseFloat(totalInput.val()) || 0;
            if (hasGst) {
                var gstInput = $('.new-' + sectionId + '-gst');
                totalGst = parseFloat(gstInput.val()) || 0;
            }
        } else if (cfg.data.currentItem) {
            totalNet = parseFloat(cfg.data.currentItem.total_cost || cfg.data.currentItem.total_net || cfg.data.currentItem.total_amount || cfg.data.currentItem.amount || 0);
            console.log('updateStillToAllocate totalNet from currentItem:', totalNet, 'currentItem:', cfg.data.currentItem);
            if (hasGst) {
                totalGst = parseFloat(cfg.data.currentItem.total_gst || 0);
            }
        }
        
        // Calculate allocated amounts
        var allocatedNet = 0, allocatedGst = 0;
        console.log('updateStillToAllocate - sectionId:', sectionId, 'looking for class:', cls + '-net-input');
        $('#' + sectionId + 'AllocationsTableBody tr').each(function(index) {
            // Net amount - use standardized class name
            var netInput = $(this).find('.' + cls + '-net-input');
            console.log('  Row', index, '- netInput found:', netInput.length, 'value:', netInput.val());
            if (netInput.length) {
                allocatedNet += parseFloat(netInput.val()) || 0;
            } else {
                // Fallback: try amount-input class or parse from text
                var amountInput = $(this).find('.' + cls + '-amount-input');
                if (amountInput.length) {
                    allocatedNet += parseFloat(amountInput.val()) || 0;
                } else {
                    // Read-only row - parse from text (column index varies)
                    var amountCell = $(this).find('td:eq(1)');
                    var text = amountCell.text().replace(/[$,]/g, '');
                    console.log('  Row', index, '- fallback text parse from td:eq(1):', text);
                    allocatedNet += parseFloat(text) || 0;
                }
            }
            
            // GST amount (if enabled)
            if (hasGst) {
                var gstInput = $(this).find('.' + cls + '-gst-input');
                if (gstInput.length) {
                    allocatedGst += parseFloat(gstInput.val()) || 0;
                }
            }
        });
        
        var remainingNet = totalNet - allocatedNet;
        var remainingGst = hasGst ? totalGst - allocatedGst : 0;
        console.log('updateStillToAllocate RESULT - totalNet:', totalNet, 'allocatedNet:', allocatedNet, 'remainingNet:', remainingNet);
        
        // Update Net display
        var netDisplayEl = $('#' + sectionId + 'RemainingNet');
        if (netDisplayEl.length) {
            if (st.isNewMode || st.editMode) {
                netDisplayEl.text('$' + Utils.formatMoney(remainingNet));
                netDisplayEl.css('color', Math.abs(remainingNet) < 0.01 ? '#90EE90' : '#ffcccc');
            } else {
                // View mode: show total allocated
                netDisplayEl.text('$' + Utils.formatMoney(allocatedNet));
                netDisplayEl.css('color', '#90EE90');
            }
        }
        
        // Update GST display (if enabled)
        if (hasGst) {
            var gstDisplayEl = $('#' + sectionId + 'RemainingGst');
            if (gstDisplayEl.length) {
                if (st.isNewMode || st.editMode) {
                    gstDisplayEl.text('$' + Utils.formatMoney(remainingGst));
                    gstDisplayEl.css('color', Math.abs(remainingGst) < 0.01 ? '#90EE90' : '#ffcccc');
                } else {
                    gstDisplayEl.text('$' + Utils.formatMoney(allocatedGst));
                    gstDisplayEl.css('color', '#90EE90');
                }
            }
        }
        
        // Trigger validation callback if provided
        if (cfg.allocations && cfg.allocations.onUpdate) {
            cfg.allocations.onUpdate(sectionId, {
                totalNet: totalNet,
                totalGst: totalGst,
                allocatedNet: allocatedNet,
                allocatedGst: allocatedGst,
                remainingNet: remainingNet,
                remainingGst: remainingGst
            });
        }
        
        return { 
            totalNet: totalNet, 
            totalGst: totalGst,
            allocatedNet: allocatedNet, 
            allocatedGst: allocatedGst,
            remainingNet: remainingNet,
            remainingGst: remainingGst
        };
    }
    
    /**
     * Get current allocations from the table
     */
    function getAllocations(sectionId) {
        var cfg = configs[sectionId];
        var allocations = [];
        var isConstruction = cfg.features && cfg.features.constructionMode;
        
        $('#' + sectionId + 'AllocationsTableBody tr').each(function() {
            var row = $(this);
            var itemSelect = row.find('.' + sectionId + '-allocation-item-select');
            var amountInput = row.find('.' + sectionId + '-allocation-amount-input');
            var notesInput = row.find('.' + sectionId + '-allocation-notes-input');
            
            if (itemSelect.length && itemSelect.val()) {
                var alloc = {
                    item_pk: itemSelect.val(),
                    amount: parseFloat(amountInput.val()) || 0,
                    notes: notesInput.val() || '',
                    allocation_pk: row.attr('data-allocation-pk') || null
                };
                
                // Include qty and rate for construction mode
                if (isConstruction) {
                    var qtyInput = row.find('.' + sectionId + '-allocation-qty-input');
                    var rateInput = row.find('.' + sectionId + '-allocation-rate-input');
                    alloc.qty = parseFloat(qtyInput.val()) || null;
                    alloc.rate = parseFloat(rateInput.val()) || null;
                    
                    // Get unit from selected item
                    var selectedOption = itemSelect.find('option:selected');
                    alloc.unit = selectedOption.attr('data-unit') || '';
                }
                
                allocations.push(alloc);
            }
        });
        
        return allocations;
    }
    
    /**
     * Add "New Item" button to main table footer
     * @param {string} sectionId - Section identifier
     * @param {string} buttonText - Text for the button (e.g., "New Quote", "New Variation")
     * @param {Function} onClick - Click handler function
     */
    function addNewItemButton(sectionId, buttonText, onClick) {
        var newBtn = $('<button type="button" class="' + sectionId + '-action-btn" id="' + sectionId + 'NewBtn">')
            .html('<i class="fas fa-plus"></i> ' + buttonText)
            .on('click', onClick);
        
        // Add to the TitleActions span in the table footer (first column)
        $('#' + sectionId + 'TitleActions').empty().append(newBtn);
        
        // Show the footer
        $('#' + sectionId + 'MainTableFooter').show();
        
        console.log(buttonText + ' button added to table footer');
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
            $('#' + sectionId + 'SaveAllocationsBtn').show();
            $('#' + sectionId + 'AllocationFooterLabel').text('Still to Allocate:');
        }
        
        // Show/hide edit-only columns (e.g., Delete column)
        toggleEditOnlyColumns(sectionId, isNew);
    }
    
    /**
     * Set edit mode (for updating existing items)
     */
    function setEditMode(sectionId, isEdit) {
        console.log('setEditMode called:', sectionId, 'isEdit:', isEdit);
        var st = state[sectionId];
        st.editMode = isEdit;
        st.isNewMode = false;
        console.log('State after setEditMode:', 'editMode:', st.editMode, 'isNewMode:', st.isNewMode);
        
        // Show/hide edit-only columns (e.g., Delete column)
        toggleEditOnlyColumns(sectionId, isEdit);
    }
    
    /**
     * Toggle visibility of edit-only columns (th and td with data-edit-only)
     */
    function toggleEditOnlyColumns(sectionId, show) {
        var table = $('#' + sectionId + 'AllocationsTable');
        if (show) {
            table.find('th[data-edit-only], td[data-edit-only]').show();
        } else {
            table.find('th[data-edit-only], td[data-edit-only]').hide();
        }
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
                var row = $(this).closest('tr');
                
                // Custom callback takes precedence
                if (cfg.callbacks.onUpdate) {
                    cfg.callbacks.onUpdate(item, cfg, row);
                    return;
                }
                
                // Default: trigger save for this item
                // If row not selected, select it first then save after allocations load
                if (!row.hasClass('selected-row')) {
                    // Set flag to save after allocations load
                    state[sectionId].pendingSaveItemPk = itemPk;
                    selectRow(sectionId, row);
                } else {
                    // Row already selected - save immediately
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
                'X-CSRFToken': Utils.getCSRFToken()
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
                'X-CSRFToken': Utils.getCSRFToken()
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
                        loadData(sectionId, { queryParams: { project_pk: window.projectPk } });
                    } else if (row) {
                        // Just remove the row and recalculate footer totals
                        row.remove();
                        recalculateFooterTotals(sectionId);
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
        var sectionId = options.sectionId || 'bill';  // Default to 'bill' for backwards compatibility
        var isConstruction = options.isConstruction || false;
        var costingItems = options.costingItems || [];
        var onUpdate = options.onUpdate || function() {};
        var api = options.api || {};
        
        // Standardized class prefix for this section
        var cls = sectionId + '-allocation';
        
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
                    var qty = parseFloat(row.find('.' + cls + '-qty-input').val()) || 0;
                    var rate = parseFloat(row.find('.' + cls + '-rate-input').val()) || 0;
                    data = {
                        item_pk: row.find('.' + cls + '-item-select').val() || null,
                        qty: qty,
                        rate: rate,
                        unit: row.find('.' + cls + '-unit-input').val() || '',
                        amount: qty * rate,
                        gst_amount: 0,
                        notes: row.find('.' + cls + '-notes-input').val() || ''
                    };
                } else {
                    // Non-construction mode: save net and gst
                    data = {
                        item_pk: row.find('.' + cls + '-item-select').val() || null,
                        amount: parseFloat(row.find('.' + cls + '-net-input').val()) || 0,
                        gst_amount: parseFloat(row.find('.' + cls + '-gst-input').val()) || 0,
                        notes: row.find('.' + cls + '-notes-input').val() || ''
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
        var itemSelect = $('<select>').addClass('form-control form-control-sm ' + cls + '-item-select');
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
        
        console.log('createEditableAllocationRow - isConstruction:', isConstruction, 'sectionId:', sectionId);
        
        if (isConstruction) {
            // Construction mode: Item | Unit | Qty | $ Rate | $ Amount | Notes | Del
            
            // Item dropdown with unit auto-populate
            itemSelect.on('change', function() {
                var selectedOption = $(this).find('option:selected');
                var unit = selectedOption.attr('data-unit') || '';
                row.find('.' + cls + '-unit-display').text(unit);
                row.find('.' + cls + '-unit-input').val(unit);
                saveAllocation();
                onUpdate();
            });
            row.append($('<td>').append(itemSelect));
            
            // 2. Unit (read-only, auto-populated from item)
            var selectedUnit = alloc.unit || '';
            var unitDisplay = $('<span>').addClass(cls + '-unit-display').text(selectedUnit);
            var unitInput = $('<input>').attr('type', 'hidden').addClass(cls + '-unit-input').val(selectedUnit);
            row.append($('<td>').append(unitDisplay).append(unitInput));
            
            // 3. Qty input
            var qtyInput = $('<input>')
                .attr('type', 'number')
                .attr('step', '0.01')
                .addClass('form-control form-control-sm ' + cls + '-qty-input')
                .val(alloc.qty ? parseFloat(alloc.qty).toFixed(2) : '')
                .on('change input', function() {
                    // Calculate amount = qty * rate
                    var qty = parseFloat($(this).val()) || 0;
                    var rate = parseFloat(row.find('.' + cls + '-rate-input').val()) || 0;
                    var amount = (qty * rate).toFixed(2);
                    row.find('.' + cls + '-amount-display').text('$' + Utils.formatMoney(amount));
                    row.find('.' + cls + '-net-input').val(amount);
                    onUpdate();
                    saveAllocation();
                });
            row.append($('<td>').append(qtyInput));
            
            // 4. $ Rate input
            var rateInput = $('<input>')
                .attr('type', 'number')
                .attr('step', '0.01')
                .addClass('form-control form-control-sm ' + cls + '-rate-input')
                .val(alloc.rate ? parseFloat(alloc.rate).toFixed(2) : '')
                .on('change input', function() {
                    // Calculate amount = qty * rate
                    var qty = parseFloat(row.find('.' + cls + '-qty-input').val()) || 0;
                    var rate = parseFloat($(this).val()) || 0;
                    var amount = (qty * rate).toFixed(2);
                    row.find('.' + cls + '-amount-display').text('$' + Utils.formatMoney(amount));
                    row.find('.' + cls + '-net-input').val(amount);
                    onUpdate();
                    saveAllocation();
                });
            row.append($('<td>').append(rateInput));
            
            // 5. $ Amount (calculated, read-only display but hidden input for data)
            // If amount not set but qty and rate are, calculate it
            var calcAmount = alloc.amount ? parseFloat(alloc.amount) : 0;
            if (calcAmount === 0 && alloc.qty && alloc.rate) {
                calcAmount = parseFloat(alloc.qty) * parseFloat(alloc.rate);
            }
            console.log('createEditableAllocationRow construction - alloc.amount:', alloc.amount, 'calcAmount:', calcAmount, 'qty:', alloc.qty, 'rate:', alloc.rate);
            var amountDisplay = $('<span>').addClass(cls + '-amount-display')
                .text('$' + Utils.formatMoney(calcAmount));
            var amountHidden = $('<input>').attr('type', 'hidden')
                .addClass(cls + '-net-input').val(calcAmount.toFixed(2));
            row.append($('<td>').append(amountDisplay).append(amountHidden));
            
            // 6. Notes input
            var notesInput = $('<input>')
                .attr('type', 'text')
                .addClass('form-control form-control-sm ' + cls + '-notes-input')
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
                .addClass('form-control form-control-sm ' + cls + '-net-input')
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
                    var gstInputEl = $(this).closest('tr').find('.' + cls + '-gst-input');
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
                .addClass('form-control form-control-sm ' + cls + '-gst-input')
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
                .addClass('form-control form-control-sm ' + cls + '-notes-input')
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
        row.append($('<td>').addClass('col-action-first').attr('data-edit-only', 'true').append(deleteBtn));
        
        return row;
    }
    
    
    /**
     * Show success tick on button, then fade out and remove the row.
     * Used after successful send/submit actions.
     * 
     * @param {jQuery} button - The button element that was clicked
     * @param {jQuery} row - The table row to fade out
     * @param {Function} onComplete - Optional callback after row is removed
     */
    function showSuccessAndFadeRow(button, row, onComplete) {
        // Show green tick success animation
        button.removeClass('btn-success btn-secondary btn-primary')
            .addClass('btn-success')
            .html('<i class="fas fa-check"></i>')
            .css('background-color', '#28a745')
            .prop('disabled', true);
        
        // Fade out row after brief delay to show success
        setTimeout(function() {
            row.fadeOut(1000, function() {
                $(this).remove();
                if (typeof onComplete === 'function') {
                    onComplete();
                }
            });
        }, 800);
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
        addNewItemButton: addNewItemButton,
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
        // Success animation
        showSuccessAndFadeRow: showSuccessAndFadeRow,
        // Utility functions are now in utils.js (Utils.isConstructionProject, etc.)
        _initialized: true
    };
})();

// Mark as initialized to prevent AJAX reload from wiping configs
window.AllocationsManager = AllocationsManager;

} // End of re-init guard
