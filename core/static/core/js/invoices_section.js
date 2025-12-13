/**
 * Invoices Section Configuration
 * ===============================
 * Uses AllocationsManager for the standalone invoices page
 * Replaces: invoices_1.js, invoices_2.js, invoices_3.js (partially)
 * 
 * Dependencies:
 * - jQuery
 * - allocations_manager.js (must be loaded before this file)
 * - utils.js (for getCookie)
 */

$(document).ready(function() {
    // Only initialize if we're on a page with the invoice section
    if ($('#invoiceMainTableBody').length === 0 && $('#unallocatedInvoicesTableBody').length === 0) {
        return;
    }
    
    // Skip auto-initialization if running within Projects page (which has its own loadUnallocatedInvoices)
    // The Projects page uses projects_scripts.html which handles invoice loading
    if (window.loadUnallocatedInvoices || window.populateUnallocatedInvoicesTable) {
        console.log('Invoices section: Skipping auto-init (running within Projects page)');
        return;
    }
    
    console.log('Initializing invoices section with AllocationsManager (standalone)...');
    
    // Determine which ID pattern to use (new template or legacy mapped)
    var useLegacyIds = $('#unallocatedInvoicesTableBody').length > 0;
    var sectionId = useLegacyIds ? 'unallocatedInvoices' : 'invoice';
    
    // Get project PK from page context, current project, or URL
    var projectPk = window.projectPk || 
                    (window.currentConstructionProject && window.currentConstructionProject.pk) ||
                    (window.currentProject && window.currentProject.pk) ||
                    getProjectPkFromUrl();
    
    // Store suppliers for dropdown population
    var suppliers = window.invoiceSectionSuppliers || [];
    
    AllocationsManager.init({
        sectionId: sectionId,
        
        // Custom ID mapping for legacy compatibility
        idOverrides: useLegacyIds ? {
            mainTable: 'unallocatedInvoicesTable',
            mainTableBody: 'unallocatedInvoicesTableBody',
            mainTableFooter: 'unallocatedInvoicesTableFooter',
            allocationsTableBody: 'invoiceAllocationsTableBody',
            viewer: 'invoiceViewer',
            addAllocationBtn: 'addInvoiceAllocationBtn'
        } : null,
        
        mainTable: {
            emptyMessage: 'No unallocated invoices found for this project.',
            showFooter: true,
            footerTotals: [
                { colIndex: 2, valueKey: 'total_net' },
                { colIndex: 3, valueKey: 'total_gst' }
            ],
            
            /**
             * Render a main table row for an invoice
             */
            renderRow: function(invoice, index, cfg) {
                var row = $('<tr>')
                    .attr('data-pk', invoice.invoice_pk)
                    .attr('data-invoice-pk', invoice.invoice_pk)
                    .attr('data-pdf-url', invoice.pdf_url || invoice.attachment_url || '');
                
                // 1. Supplier dropdown
                var supplierSelect = $('<select>').addClass('form-control form-control-sm supplier-select');
                supplierSelect.append($('<option>').val('').text('Select Supplier...'));
                
                var suppliersList = cfg.data.suppliers || suppliers || [];
                suppliersList.forEach(function(supplier) {
                    var option = $('<option>').val(supplier.contact_pk).text(supplier.name);
                    if (invoice.supplier_pk === supplier.contact_pk) {
                        option.prop('selected', true);
                    }
                    supplierSelect.append(option);
                });
                row.append($('<td>').append(supplierSelect));
                
                // 2. Invoice # input
                var invoiceNumberInput = $('<input>')
                    .attr('type', 'text')
                    .addClass('form-control form-control-sm invoice-number-input')
                    .val(invoice.invoice_number || '')
                    .attr('placeholder', 'Invoice #');
                row.append($('<td>').append(invoiceNumberInput));
                
                // 3. $ Net input
                var netInput = $('<input>')
                    .attr('type', 'number')
                    .attr('step', '0.01')
                    .attr('min', '0')
                    .addClass('form-control form-control-sm net-input')
                    .val(invoice.total_net !== null ? invoice.total_net : '')
                    .attr('placeholder', '0.00')
                    .on('input', function() {
                        handleNetInput($(this));
                    });
                row.append($('<td>').append(netInput));
                
                // 4. $ GST input
                var gstInput = $('<input>')
                    .attr('type', 'number')
                    .attr('step', '0.01')
                    .attr('min', '0')
                    .addClass('form-control form-control-sm gst-input')
                    .val(invoice.total_gst !== null ? invoice.total_gst : '')
                    .attr('placeholder', '0.00')
                    .on('focus', function() {
                        $(this).data('manually-edited', true);
                    })
                    .on('input', function() {
                        limitToTwoDecimals($(this));
                    });
                row.append($('<td>').append(gstInput));
                
                // 5. Allocate button
                var allocateBtn = $('<button>')
                    .addClass('btn btn-sm btn-primary')
                    .html('<i class="fas fa-check"></i> Allocate')
                    .on('click', function(e) {
                        e.stopPropagation();
                        allocateInvoice(invoice.invoice_pk, row);
                    });
                row.append($('<td>').addClass('text-center').append(allocateBtn));
                
                // 6. Delete button
                var deleteBtn = $('<button>')
                    .addClass('btn btn-sm btn-danger')
                    .html('<i class="fas fa-trash"></i>')
                    .on('click', function(e) {
                        e.stopPropagation();
                        deleteInvoice(invoice.invoice_pk);
                    });
                row.append($('<td>').addClass('text-center').append(deleteBtn));
                
                return row;
            },
            
            /**
             * Called when a row is selected
             */
            onRowSelect: function(row, pk, cfg) {
                console.log('Invoice selected:', pk);
                // Load allocations for this invoice
                loadInvoiceAllocations(pk);
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
                    row.attr('data-allocation-pk', allocation.invoice_allocations_pk || allocation.pk);
                }
                
                // Item dropdown
                var itemSelect = $('<select>').addClass('form-control form-control-sm invoice-allocation-item-select');
                itemSelect.append($('<option>').val('').text('Select Item...'));
                
                var costingItems = cfg.data.costingItems || window.invoiceCostingItems || window.costings || [];
                costingItems.forEach(function(item) {
                    var option = $('<option>')
                        .val(item.costing_pk || item.pk)
                        .text(item.item || item.name);
                    if (allocation && allocation.item_pk == (item.costing_pk || item.pk)) {
                        option.prop('selected', true);
                    }
                    itemSelect.append(option);
                });
                itemSelect.on('change', onChange);
                row.append($('<td>').append(itemSelect));
                
                // Net amount input
                var netInput = $('<input>')
                    .attr('type', 'number')
                    .attr('step', '0.01')
                    .addClass('form-control form-control-sm invoice-allocation-net-input')
                    .val(allocation ? parseFloat(allocation.amount || 0).toFixed(2) : '')
                    .on('change input', onChange);
                row.append($('<td>').append(netInput));
                
                // GST amount input
                var gstInput = $('<input>')
                    .attr('type', 'number')
                    .attr('step', '0.01')
                    .addClass('form-control form-control-sm invoice-allocation-gst-input')
                    .val(allocation ? parseFloat(allocation.gst || 0).toFixed(2) : '')
                    .on('change input', onChange);
                row.append($('<td>').append(gstInput));
                
                // Notes input
                var notesInput = $('<input>')
                    .attr('type', 'text')
                    .addClass('form-control form-control-sm invoice-allocation-notes-input')
                    .val(allocation ? allocation.notes || '' : '');
                row.append($('<td>').append(notesInput));
                
                // Delete button
                var deleteBtn = $('<button>')
                    .addClass('btn btn-sm btn-danger')
                    .html('<i class="fas fa-times"></i>')
                    .on('click', function() {
                        row.remove();
                        onChange();
                    });
                row.append($('<td>').css('text-align', 'center').append(deleteBtn));
                
                return row;
            },
            
            /**
             * Calculate still-to-allocate values
             */
            calculateRemaining: function(sectionId, cfg) {
                var selectedRow = $('#' + sectionId + 'MainTableBody tr.selected-row, #unallocatedInvoicesTableBody tr.selected-row').first();
                if (selectedRow.length === 0) return { net: 0, gst: 0 };
                
                var invoiceNet = parseFloat(selectedRow.find('.net-input').val()) || 0;
                var invoiceGst = parseFloat(selectedRow.find('.gst-input').val()) || 0;
                
                var allocatedNet = 0;
                var allocatedGst = 0;
                
                $('#' + sectionId + 'AllocationsTableBody tr, #invoiceAllocationsTableBody tr').each(function() {
                    allocatedNet += parseFloat($(this).find('.invoice-allocation-net-input').val()) || 0;
                    allocatedGst += parseFloat($(this).find('.invoice-allocation-gst-input').val()) || 0;
                });
                
                return {
                    net: (invoiceNet - allocatedNet).toFixed(2),
                    gst: (invoiceGst - allocatedGst).toFixed(2)
                };
            }
        },
        
        api: {
            loadData: function(projectPk) {
                return '/get_unallocated_invoices/' + projectPk + '/';
            },
            loadAllocations: function(invoicePk) {
                return '/get_invoice_allocations/' + invoicePk + '/';
            }
        }
    });
    
    // Load initial data if we have a project PK
    if (projectPk) {
        loadInvoiceData(projectPk);
    }
    
    /**
     * Helper: Get project PK from URL
     */
    function getProjectPkFromUrl() {
        var match = window.location.pathname.match(/\/project\/(\d+)/);
        if (!match) {
            match = window.location.pathname.match(/\/invoices\/(\d+)/);
        }
        return match ? match[1] : null;
    }
    
    /**
     * Load invoice data for a project
     */
    function loadInvoiceData(projectPk) {
        $.ajax({
            url: '/get_unallocated_invoices/' + projectPk + '/',
            method: 'GET',
            success: function(response) {
                if (response.status === 'success') {
                    // Store suppliers
                    suppliers = response.suppliers || [];
                    window.invoiceSectionSuppliers = suppliers;
                    
                    // Store costing items if provided
                    if (response.costings) {
                        window.invoiceCostingItems = response.costings;
                    }
                    
                    // Update AllocationsManager config with suppliers
                    var cfg = AllocationsManager.getConfig(sectionId);
                    if (cfg) {
                        cfg.data.suppliers = suppliers;
                        cfg.data.costingItems = response.costings || [];
                    }
                    
                    // Render the data
                    AllocationsManager.renderMainTable(sectionId, response.invoices || []);
                } else {
                    console.error('Error loading invoices:', response.message);
                }
            },
            error: function(xhr, status, error) {
                console.error('Failed to load invoices:', error);
            }
        });
    }
    
    /**
     * Load allocations for a specific invoice
     */
    function loadInvoiceAllocations(invoicePk) {
        $.ajax({
            url: '/get_invoice_allocations/' + invoicePk + '/',
            method: 'GET',
            success: function(response) {
                if (response.status === 'success') {
                    AllocationsManager.renderAllocations(sectionId, response.allocations || []);
                    
                    // Update still-to-allocate display
                    updateRemainingDisplay();
                }
            },
            error: function(xhr, status, error) {
                console.error('Failed to load allocations:', error);
            }
        });
    }
    
    /**
     * Handle net input changes (auto-calculate GST)
     */
    function handleNetInput($input) {
        var value = $input.val();
        
        // Prevent negative
        if (parseFloat(value) < 0) {
            $input.val(0);
            return;
        }
        
        // Limit to 2dp
        limitToTwoDecimals($input);
        
        // Auto-calculate GST as 10% of NET (unless manually edited)
        var gstInput = $input.closest('tr').find('.gst-input');
        if (!gstInput.data('manually-edited')) {
            var netValue = parseFloat($input.val());
            if (!isNaN(netValue)) {
                gstInput.val((netValue * 0.1).toFixed(2));
            }
        }
    }
    
    /**
     * Limit input to 2 decimal places
     */
    function limitToTwoDecimals($input) {
        var value = $input.val();
        if (value.includes('.')) {
            var parts = value.split('.');
            if (parts[1] && parts[1].length > 2) {
                $input.val(parseFloat(value).toFixed(2));
            }
        }
    }
    
    /**
     * Update the remaining allocation display
     */
    function updateRemainingDisplay() {
        var cfg = AllocationsManager.getConfig(sectionId);
        if (cfg && cfg.allocations.calculateRemaining) {
            var remaining = cfg.allocations.calculateRemaining(sectionId, cfg);
            $('#' + sectionId + 'RemainingNet, #invoiceRemainingNet').text('$' + remaining.net);
            $('#' + sectionId + 'RemainingGst, #invoiceRemainingGst').text('$' + remaining.gst);
        }
    }
    
    /**
     * Allocate an invoice
     */
    function allocateInvoice(invoicePk, row) {
        // Gather data from the row
        var supplierPk = row.find('.supplier-select').val();
        var invoiceNumber = row.find('.invoice-number-input').val();
        var totalNet = row.find('.net-input').val();
        var totalGst = row.find('.gst-input').val();
        
        if (!supplierPk) {
            alert('Please select a supplier.');
            return;
        }
        
        // Gather allocations
        var allocations = [];
        $('#' + sectionId + 'AllocationsTableBody tr, #invoiceAllocationsTableBody tr').each(function() {
            var itemPk = $(this).find('.invoice-allocation-item-select').val();
            var net = $(this).find('.invoice-allocation-net-input').val();
            var gst = $(this).find('.invoice-allocation-gst-input').val();
            var notes = $(this).find('.invoice-allocation-notes-input').val();
            
            if (itemPk && (net || gst)) {
                allocations.push({
                    item_pk: itemPk,
                    amount: net || 0,
                    gst: gst || 0,
                    notes: notes || ''
                });
            }
        });
        
        var data = {
            invoice_pk: invoicePk,
            supplier_pk: supplierPk,
            invoice_number: invoiceNumber,
            total_net: totalNet,
            total_gst: totalGst,
            allocations: allocations
        };
        
        $.ajax({
            url: '/allocate_invoice/',
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            data: JSON.stringify(data),
            success: function(response) {
                if (response.status === 'success') {
                    alert('Invoice allocated successfully!');
                    // Reload the data
                    if (projectPk) {
                        loadInvoiceData(projectPk);
                    }
                } else {
                    alert('Error: ' + (response.message || 'Failed to allocate invoice'));
                }
            },
            error: function(xhr, status, error) {
                alert('Failed to allocate invoice: ' + error);
            }
        });
    }
    
    /**
     * Delete an invoice
     */
    function deleteInvoice(invoicePk) {
        if (!confirm('Are you sure you want to delete this invoice?')) {
            return;
        }
        
        $.ajax({
            url: '/delete_invoice/' + invoicePk + '/',
            method: 'DELETE',
            headers: {
                'X-CSRFToken': getCookie('csrftoken')
            },
            success: function(response) {
                if (response.status === 'success') {
                    // Reload the data
                    if (projectPk) {
                        loadInvoiceData(projectPk);
                    }
                } else {
                    alert('Error: ' + (response.message || 'Failed to delete invoice'));
                }
            },
            error: function(xhr, status, error) {
                alert('Failed to delete invoice: ' + error);
            }
        });
    }
});
