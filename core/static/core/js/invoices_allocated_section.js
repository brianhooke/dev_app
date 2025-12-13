/**
 * Allocated Invoices Section Configuration
 * =========================================
 * Uses AllocationsManager for the allocated invoices page (readonly view)
 * 
 * Dependencies:
 * - jQuery
 * - allocations_manager.js (must be loaded before this file)
 * - utils.js (for getCookie)
 */

$(document).ready(function() {
    // Only initialize if we're on a page with the allocated invoice section
    if ($('#allocatedInvoiceMainTableBody').length === 0) {
        return;
    }
    
    console.log('Initializing allocated invoices section with AllocationsManager...');
    
    var sectionId = 'allocatedInvoice';
    
    // Get project PK from page context, current project, or URL
    var projectPk = window.projectPk || 
                    (window.currentConstructionProject && window.currentConstructionProject.pk) ||
                    (window.currentProject && window.currentProject.pk) ||
                    getProjectPkFromUrl();
    
    AllocationsManager.init({
        sectionId: sectionId,
        
        mainTable: {
            emptyMessage: 'No allocated invoices found for this project.',
            showFooter: true,
            footerTotals: [
                { colIndex: 2, valueKey: 'total_net' },
                { colIndex: 3, valueKey: 'total_gst' }
            ],
            
            /**
             * Render a main table row for an allocated invoice (readonly with action buttons)
             */
            renderRow: function(invoice, index, cfg) {
                var row = $('<tr>')
                    .attr('data-pk', invoice.invoice_pk)
                    .attr('data-invoice-pk', invoice.invoice_pk)
                    .attr('data-pdf-url', invoice.pdf_url || invoice.attachment_url || '');
                
                // 1. Supplier (readonly)
                row.append($('<td>').text(invoice.supplier_name || invoice.contact_name || '-'));
                
                // 2. Invoice # (editable for corrections)
                var invoiceNumberInput = $('<input>')
                    .attr('type', 'text')
                    .addClass('form-control form-control-sm invoice-number-input')
                    .val(invoice.invoice_number || '')
                    .attr('placeholder', 'Invoice #');
                row.append($('<td>').append(invoiceNumberInput));
                
                // 3. $ Net (readonly display)
                var netAmount = parseFloat(invoice.total_net) || 0;
                row.append($('<td>').text('$' + netAmount.toFixed(2)));
                
                // 4. $ GST (editable for corrections)
                var gstInput = $('<input>')
                    .attr('type', 'number')
                    .attr('step', '0.01')
                    .addClass('form-control form-control-sm gst-input')
                    .val(invoice.total_gst !== null ? invoice.total_gst : '')
                    .attr('placeholder', '0.00');
                row.append($('<td>').append(gstInput));
                
                // 5. Progress Claim checkbox
                var isProgressClaim = invoice.is_progress_claim || invoice.invoice_type === 2;
                var pcCheckbox = $('<input>')
                    .attr('type', 'checkbox')
                    .addClass('form-check-input')
                    .prop('checked', isProgressClaim)
                    .prop('disabled', true);  // Readonly
                row.append($('<td>').addClass('text-center').append(pcCheckbox));
                
                // 6. Unallocate button
                var unallocateBtn = $('<button>')
                    .addClass('btn btn-sm btn-warning allocated-action-btn')
                    .html('<i class="fas fa-undo"></i>')
                    .attr('title', 'Unallocate')
                    .on('click', function(e) {
                        e.stopPropagation();
                        unallocateInvoice(invoice.invoice_pk);
                    });
                row.append($('<td>').addClass('text-center').append(unallocateBtn));
                
                // 7. Approve button
                var approveBtn = $('<button>')
                    .addClass('btn btn-sm btn-success allocated-action-btn')
                    .html('<i class="fas fa-check"></i>')
                    .attr('title', 'Approve')
                    .on('click', function(e) {
                        e.stopPropagation();
                        approveInvoice(invoice.invoice_pk);
                    });
                row.append($('<td>').addClass('text-center').append(approveBtn));
                
                // 8. Save button (for invoice number / GST corrections)
                var saveBtn = $('<button>')
                    .addClass('btn btn-sm btn-primary allocated-action-btn')
                    .html('<i class="fas fa-save"></i>')
                    .attr('title', 'Save Changes')
                    .on('click', function(e) {
                        e.stopPropagation();
                        saveInvoiceChanges(invoice.invoice_pk, row);
                    });
                row.append($('<td>').addClass('text-center').append(saveBtn));
                
                return row;
            },
            
            /**
             * Called when a row is selected
             */
            onRowSelect: function(row, pk, cfg) {
                console.log('Allocated invoice selected:', pk);
                loadInvoiceAllocations(pk);
            }
        },
        
        allocations: {
            emptyMessage: 'No allocations for this invoice.',
            editable: false,  // Readonly view
            
            /**
             * Render a readonly allocation row
             */
            renderRow: function(allocation, cfg) {
                var row = $('<tr>');
                
                // Item name (readonly)
                row.append($('<td>').text(allocation.item_name || allocation.item || '-'));
                
                // Net amount (readonly)
                var netAmount = parseFloat(allocation.amount || 0);
                row.append($('<td>').text('$' + netAmount.toFixed(2)));
                
                // GST amount (readonly)
                var gstAmount = parseFloat(allocation.gst || 0);
                row.append($('<td>').text('$' + gstAmount.toFixed(2)));
                
                // Notes (readonly)
                row.append($('<td>').text(allocation.notes || ''));
                
                return row;
            }
        },
        
        api: {
            loadData: function(projectPk) {
                return '/get_allocated_invoices/' + projectPk + '/';
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
     * Load allocated invoice data for a project
     */
    function loadInvoiceData(projectPk) {
        $.ajax({
            url: '/get_allocated_invoices/' + projectPk + '/',
            method: 'GET',
            success: function(response) {
                if (response.status === 'success') {
                    AllocationsManager.renderMainTable(sectionId, response.invoices || []);
                } else {
                    console.error('Error loading allocated invoices:', response.message);
                }
            },
            error: function(xhr, status, error) {
                console.error('Failed to load allocated invoices:', error);
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
                    AllocationsManager.renderAllocations(sectionId, response.allocations || [], true);  // true = readonly
                }
            },
            error: function(xhr, status, error) {
                console.error('Failed to load allocations:', error);
            }
        });
    }
    
    /**
     * Unallocate an invoice (return to unallocated state)
     */
    function unallocateInvoice(invoicePk) {
        if (!confirm('Are you sure you want to unallocate this invoice?')) {
            return;
        }
        
        $.ajax({
            url: '/unallocate_invoice/' + invoicePk + '/',
            method: 'POST',
            headers: {
                'X-CSRFToken': getCookie('csrftoken')
            },
            success: function(response) {
                if (response.status === 'success') {
                    alert('Invoice unallocated successfully.');
                    if (projectPk) {
                        loadInvoiceData(projectPk);
                    }
                } else {
                    alert('Error: ' + (response.message || 'Failed to unallocate invoice'));
                }
            },
            error: function(xhr, status, error) {
                alert('Failed to unallocate invoice: ' + error);
            }
        });
    }
    
    /**
     * Approve an invoice (move to approvals queue)
     */
    function approveInvoice(invoicePk) {
        $.ajax({
            url: '/approve_invoice/' + invoicePk + '/',
            method: 'POST',
            headers: {
                'X-CSRFToken': getCookie('csrftoken')
            },
            success: function(response) {
                if (response.status === 'success') {
                    alert('Invoice approved successfully.');
                    if (projectPk) {
                        loadInvoiceData(projectPk);
                    }
                } else {
                    alert('Error: ' + (response.message || 'Failed to approve invoice'));
                }
            },
            error: function(xhr, status, error) {
                alert('Failed to approve invoice: ' + error);
            }
        });
    }
    
    /**
     * Save invoice changes (invoice number, GST)
     */
    function saveInvoiceChanges(invoicePk, row) {
        var invoiceNumber = row.find('.invoice-number-input').val();
        var totalGst = row.find('.gst-input').val();
        
        $.ajax({
            url: '/update_allocated_invoice/' + invoicePk + '/',
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            data: JSON.stringify({
                invoice_number: invoiceNumber,
                total_gst: totalGst
            }),
            success: function(response) {
                if (response.status === 'success') {
                    alert('Invoice updated successfully.');
                } else {
                    alert('Error: ' + (response.message || 'Failed to update invoice'));
                }
            },
            error: function(xhr, status, error) {
                alert('Failed to update invoice: ' + error);
            }
        });
    }
});
