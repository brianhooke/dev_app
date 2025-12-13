/**
 * Invoice Approvals Section Configuration
 * ========================================
 * Uses AllocationsManager for the approvals page (readonly view)
 * Shows invoices approved and ready to send to Xero
 * 
 * Dependencies:
 * - jQuery
 * - allocations_manager.js (must be loaded before this file)
 * - utils.js (for getCookie)
 */

$(document).ready(function() {
    // Only initialize if we're on a page with the approvals section
    if ($('#approvalsMainTableBody').length === 0) {
        return;
    }
    
    console.log('Initializing approvals section with AllocationsManager...');
    
    var sectionId = 'approvals';
    
    AllocationsManager.init({
        sectionId: sectionId,
        
        mainTable: {
            emptyMessage: 'No approved invoices awaiting Xero submission.',
            showFooter: true,
            footerTotals: [
                { colIndex: 4, valueKey: 'total_gross' },
                { colIndex: 5, valueKey: 'total_net' },
                { colIndex: 6, valueKey: 'total_gst' }
            ],
            
            /**
             * Render a main table row for an approved invoice
             */
            renderRow: function(invoice, index, cfg) {
                var row = $('<tr>')
                    .attr('data-pk', invoice.invoice_pk)
                    .attr('data-invoice-pk', invoice.invoice_pk)
                    .attr('data-pdf-url', invoice.pdf_url || invoice.attachment_url || '');
                
                // 1. Project name
                row.append($('<td>').addClass('truncate-2-lines').text(invoice.project_name || '-'));
                
                // 2. Xero Instance
                row.append($('<td>').addClass('truncate-2-lines').text(invoice.xero_instance || '-'));
                
                // 3. Xero Account
                row.append($('<td>').addClass('truncate-2-lines').text(invoice.xero_account || '-'));
                
                // 4. Supplier
                row.append($('<td>').addClass('truncate-2-lines').text(invoice.supplier_name || invoice.contact_name || '-'));
                
                // 5. $ Gross
                var grossAmount = parseFloat(invoice.total_gross) || 0;
                row.append($('<td>').text('$' + grossAmount.toFixed(2)));
                
                // 6. $ Net
                var netAmount = parseFloat(invoice.total_net) || 0;
                row.append($('<td>').text('$' + netAmount.toFixed(2)));
                
                // 7. $ GST
                var gstAmount = parseFloat(invoice.total_gst) || 0;
                row.append($('<td>').text('$' + gstAmount.toFixed(2)));
                
                // 8. Send to Xero button
                var sendBtn = $('<button>')
                    .addClass('btn btn-sm btn-success approvals-action-btn approvals-send-btn')
                    .html('<i class="fas fa-paper-plane"></i> Send')
                    .attr('title', 'Send to Xero')
                    .on('click', function(e) {
                        e.stopPropagation();
                        sendToXero(invoice.invoice_pk);
                    });
                row.append($('<td>').addClass('text-center').append(sendBtn));
                
                // 9. Return to Project button
                var returnBtn = $('<button>')
                    .addClass('btn btn-sm btn-warning approvals-action-btn approvals-return-btn')
                    .html('<i class="fas fa-undo"></i> Return')
                    .attr('title', 'Return to Project')
                    .on('click', function(e) {
                        e.stopPropagation();
                        returnToProject(invoice.invoice_pk);
                    });
                row.append($('<td>').addClass('text-center').append(returnBtn));
                
                return row;
            },
            
            /**
             * Called when a row is selected
             */
            onRowSelect: function(row, pk, cfg) {
                console.log('Approved invoice selected:', pk);
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
            loadData: '/get_approved_invoices/',
            loadAllocations: function(invoicePk) {
                return '/get_invoice_allocations/' + invoicePk + '/';
            }
        }
    });
    
    // Load initial data - approvals is a global view (not project-specific)
    loadApprovalsData();
    
    /**
     * Load approved invoices data
     */
    function loadApprovalsData() {
        $.ajax({
            url: '/get_approved_invoices/',
            method: 'GET',
            success: function(response) {
                if (response.status === 'success') {
                    AllocationsManager.renderMainTable(sectionId, response.invoices || []);
                } else {
                    console.error('Error loading approved invoices:', response.message);
                }
            },
            error: function(xhr, status, error) {
                console.error('Failed to load approved invoices:', error);
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
     * Send invoice to Xero
     */
    function sendToXero(invoicePk) {
        if (!confirm('Send this invoice to Xero?')) {
            return;
        }
        
        $.ajax({
            url: '/send_invoice_to_xero/' + invoicePk + '/',
            method: 'POST',
            headers: {
                'X-CSRFToken': getCookie('csrftoken')
            },
            success: function(response) {
                if (response.status === 'success') {
                    alert('Invoice sent to Xero successfully.');
                    loadApprovalsData();
                } else {
                    alert('Error: ' + (response.message || 'Failed to send invoice to Xero'));
                }
            },
            error: function(xhr, status, error) {
                alert('Failed to send invoice to Xero: ' + error);
            }
        });
    }
    
    /**
     * Return invoice to project (unapprove)
     */
    function returnToProject(invoicePk) {
        if (!confirm('Return this invoice to the project?')) {
            return;
        }
        
        $.ajax({
            url: '/return_invoice_to_project/' + invoicePk + '/',
            method: 'POST',
            headers: {
                'X-CSRFToken': getCookie('csrftoken')
            },
            success: function(response) {
                if (response.status === 'success') {
                    alert('Invoice returned to project.');
                    loadApprovalsData();
                } else {
                    alert('Error: ' + (response.message || 'Failed to return invoice'));
                }
            },
            error: function(xhr, status, error) {
                alert('Failed to return invoice: ' + error);
            }
        });
    }
});
