/**
 * Project Type Specific Logic
 * ===========================
 * Centralized configuration and helper functions for construction vs non-construction projects.
 * 
 * Load this script before any scripts that need project-type-aware behavior:
 * <script src="{% static 'core/js/project_type_config.js' %}"></script>
 * 
 * Usage:
 * - ProjectTypeConfig.isConstruction(projectType) - returns true if construction
 * - ProjectTypeConfig.quotes.getColumns(isConstruction) - get column config for quotes
 * - ProjectTypeConfig.bills.getColumns(isConstruction) - get column config for bills
 * - ProjectTypeConfig.pos.getColumns(isConstruction) - get column config for POs
 * - ProjectTypeConfig.contractBudget.getColumns(isTender, isConstruction) - get column config for contract budget
 * - ProjectTypeConfig.formatCurrency(value) - format as $X,XXX.XX
 * - ProjectTypeConfig.formatNumber(value, decimals) - format number with locale
 */

(function() {
    'use strict';
    
    // =========================================================================
    // PROJECT TYPE CONFIGURATION
    // =========================================================================
    
    window.ProjectTypeConfig = {
        
        // Check if project type is construction
        isConstruction: function(projectType) {
            return projectType === 'construction';
        },
        
        // =====================================================================
        // QUOTES CONFIGURATION
        // =====================================================================
        quotes: {
            // Column widths
            columnWidths: {
                construction: ['25%', '8%', '10%', '14%', '15%', '23%', '5%'],  // Item, Unit, Qty, Rate, Amount, Notes, Del
                nonConstruction: ['40%', '25%', '30%', '5%']  // Item, $ Net, Notes, Del
            },
            
            // Column headers
            headers: {
                construction: ['Item', 'Unit', 'Qty', '$ Rate', '$ Amount', 'Notes', ''],
                nonConstruction: ['Item', '$ Net', 'Notes', '']
            },
            
            // Index of the "amount" column for footer placement
            amountColumnIndex: {
                construction: 4,
                nonConstruction: 1
            },
            
            getColumns: function(isConstruction) {
                return {
                    widths: isConstruction ? this.columnWidths.construction : this.columnWidths.nonConstruction,
                    headers: isConstruction ? this.headers.construction : this.headers.nonConstruction,
                    amountIndex: isConstruction ? this.amountColumnIndex.construction : this.amountColumnIndex.nonConstruction
                };
            },
            
            // Render a read-only allocation row
            renderReadOnlyRow: function(allocation, isConstruction) {
                var row = $('<tr>')
                    .attr('data-allocation-pk', allocation.quote_allocations_pk || allocation.allocation_pk)
                    .attr('data-item-pk', allocation.item_pk || allocation.item);
                
                if (isConstruction) {
                    row.append($('<td>').attr('data-item-pk', allocation.item_pk || allocation.item).text(allocation.item_name || '-'));
                    row.append($('<td>').text(allocation.unit || '-'));
                    row.append($('<td>').text(ProjectTypeConfig.formatNumber(allocation.qty, 2)));
                    row.append($('<td>').text(ProjectTypeConfig.formatCurrency(allocation.rate)));
                    row.append($('<td>').text(ProjectTypeConfig.formatCurrency(allocation.amount)));
                    row.append($('<td>').text(allocation.notes || '-'));
                    row.append($('<td>')); // Empty for actions
                } else {
                    row.append($('<td>').attr('data-item-pk', allocation.item_pk || allocation.item).text(allocation.item_name || '-'));
                    row.append($('<td>').text(ProjectTypeConfig.formatCurrency(allocation.amount || allocation.net)));
                    row.append($('<td>').text(allocation.notes || '-'));
                    row.append($('<td>')); // Empty for actions
                }
                
                return row;
            },
            
            // Gather allocation data from a row
            gatherRowData: function(row, isConstruction) {
                var data = {
                    item_pk: row.find('.quote-allocation-item-select, [data-item-pk]').val() || row.attr('data-item-pk'),
                    notes: row.find('.quote-allocation-notes-input').val() || ''
                };
                
                if (isConstruction) {
                    data.qty = parseFloat(row.find('.quote-allocation-qty-input').val()) || 0;
                    data.rate = parseFloat(row.find('.quote-allocation-rate-input').val()) || 0;
                    data.unit = row.find('.quote-allocation-unit-input').val() || '';
                    data.amount = data.qty * data.rate;
                } else {
                    data.amount = parseFloat(row.find('.quote-allocation-net-input').val()) || 0;
                }
                
                return data;
            },
            
            // Render editable row inputs (construction vs non-construction)
            // callbacks: { onItemChange, onAmountChange, onNotesChange }
            renderEditableRowInputs: function(row, itemSelect, allocation, isConstruction, callbacks) {
                if (isConstruction) {
                    // Construction mode: Item | Unit | Qty | $ Rate | $ Amount | Notes
                    
                    // Item dropdown with unit auto-populate
                    itemSelect.on('change', function() {
                        var selectedOption = $(this).find('option:selected');
                        var unit = selectedOption.attr('data-unit') || '';
                        row.find('.quote-allocation-unit-display').text(unit);
                        row.find('.quote-allocation-unit-input').val(unit);
                        if (callbacks.onItemChange) callbacks.onItemChange(row);
                    });
                    row.append($('<td>').append(itemSelect));
                    
                    // Unit (read-only, auto-populated from item)
                    var selectedUnit = allocation ? (allocation.unit || '') : '';
                    var unitDisplay = $('<span>').addClass('quote-allocation-unit-display').text(selectedUnit);
                    var unitInput = $('<input>').attr('type', 'hidden').addClass('quote-allocation-unit-input').val(selectedUnit);
                    row.append($('<td>').append(unitDisplay).append(unitInput));
                    
                    // Qty input
                    var qtyInput = $('<input>')
                        .attr('type', 'number')
                        .attr('step', '0.01')
                        .addClass('form-control form-control-sm quote-allocation-qty-input')
                        .val(allocation && allocation.qty ? parseFloat(allocation.qty).toFixed(2) : '')
                        .on('change input', function() {
                            var qty = parseFloat($(this).val()) || 0;
                            var rate = parseFloat(row.find('.quote-allocation-rate-input').val()) || 0;
                            var amount = (qty * rate).toFixed(2);
                            row.find('.quote-allocation-amount-display').text(ProjectTypeConfig.formatCurrency(parseFloat(amount)));
                            row.find('.quote-allocation-net-input').val(amount);
                            if (callbacks.onAmountChange) callbacks.onAmountChange(row);
                        });
                    row.append($('<td>').append(qtyInput));
                    
                    // $ Rate input
                    var rateInput = $('<input>')
                        .attr('type', 'number')
                        .attr('step', '0.01')
                        .addClass('form-control form-control-sm quote-allocation-rate-input')
                        .val(allocation && allocation.rate ? parseFloat(allocation.rate).toFixed(2) : '')
                        .on('change input', function() {
                            var qty = parseFloat(row.find('.quote-allocation-qty-input').val()) || 0;
                            var rate = parseFloat($(this).val()) || 0;
                            var amount = (qty * rate).toFixed(2);
                            row.find('.quote-allocation-amount-display').text(ProjectTypeConfig.formatCurrency(parseFloat(amount)));
                            row.find('.quote-allocation-net-input').val(amount);
                            if (callbacks.onAmountChange) callbacks.onAmountChange(row);
                        });
                    row.append($('<td>').append(rateInput));
                    
                    // $ Amount (calculated, read-only display but hidden input for data)
                    var calcAmount = allocation && allocation.amount ? parseFloat(allocation.amount) : 0;
                    var amountDisplay = $('<span>').addClass('quote-allocation-amount-display')
                        .text(ProjectTypeConfig.formatCurrency(calcAmount));
                    var amountHidden = $('<input>').attr('type', 'hidden')
                        .addClass('form-control form-control-sm quote-allocation-net-input')
                        .val(calcAmount.toFixed(2));
                    row.append($('<td>').append(amountDisplay).append(amountHidden));
                    
                    // Notes input
                    var notesInput = $('<input>')
                        .attr('type', 'text')
                        .addClass('form-control form-control-sm quote-allocation-notes-input')
                        .val(allocation ? allocation.notes || '' : '')
                        .on('change', function() {
                            if (callbacks.onNotesChange) callbacks.onNotesChange(row);
                        });
                    row.append($('<td>').append(notesInput));
                    
                } else {
                    // Non-construction mode: Item | $ Net | Notes
                    itemSelect.on('change', function() {
                        if (callbacks.onItemChange) callbacks.onItemChange(row);
                    });
                    row.append($('<td>').append(itemSelect));
                    
                    // $ Net input
                    var netInput = $('<input>')
                        .attr('type', 'number')
                        .attr('step', '0.01')
                        .addClass('form-control form-control-sm quote-allocation-net-input')
                        .val(allocation ? parseFloat(allocation.amount).toFixed(2) : '')
                        .on('change', function() {
                            if (callbacks.onAmountChange) callbacks.onAmountChange(row);
                        });
                    row.append($('<td>').append(netInput));
                    
                    // Notes input
                    var notesInput = $('<input>')
                        .attr('type', 'text')
                        .addClass('form-control form-control-sm quote-allocation-notes-input')
                        .val(allocation ? allocation.notes || '' : '')
                        .on('change', function() {
                            if (callbacks.onNotesChange) callbacks.onNotesChange(row);
                        });
                    row.append($('<td>').append(notesInput));
                }
            }
        },
        
        // =====================================================================
        // BILLS CONFIGURATION
        // =====================================================================
        bills: {
            // Column widths for main table
            mainTableWidths: {
                unallocated: {
                    construction: ['20%', '15%', '12%', '12%', '10%', '5%'],  // Supplier, Bill#, Net, GST, Allocate, Del
                    nonConstruction: ['25%', '20%', '17%', '17%', '13%', '8%']
                },
                allocated: {
                    construction: ['15%', '12%', '10%', '10%', '10%', '13%', '13%', '10%'],
                    nonConstruction: ['15%', '12%', '10%', '10%', '10%', '13%', '13%', '10%']
                }
            },
            
            // Allocation table column widths
            allocationWidths: {
                construction: ['20%', '8%', '10%', '10%', '12%', '12%', '23%', '5%'],  // Item, Unit, Qty, Rate, Net, GST, Notes, Del
                constructionReadonly: ['20%', '8%', '10%', '10%', '15%', '15%', '22%'],  // No delete column
                nonConstruction: ['35%', '15%', '15%', '30%', '5%'],  // Item, Net, GST, Notes, Del
                nonConstructionReadonly: ['20%', '12%', '12%', '56%']  // No delete column
            },
            
            // Allocation table headers
            allocationHeaders: {
                construction: ['Item', 'Unit', 'Qty', '$ Rate', '$ Net', '$ GST', 'Notes', ''],
                constructionReadonly: ['Item', 'Unit', 'Qty', '$ Rate', '$ Net', '$ GST', 'Notes'],
                nonConstruction: ['Item', '$ Net', '$ GST', 'Notes', ''],
                nonConstructionReadonly: ['Item', '$ Net', '$ GST', 'Notes']
            },
            
            getColumns: function(isConstruction, isReadonly) {
                var widthKey = isConstruction ? 
                    (isReadonly ? 'constructionReadonly' : 'construction') : 
                    (isReadonly ? 'nonConstructionReadonly' : 'nonConstruction');
                
                return {
                    widths: this.allocationWidths[widthKey],
                    headers: this.allocationHeaders[widthKey]
                };
            },
            
            // Render a bill allocation row
            renderAllocationRow: function(allocation, isConstruction, isReadonly) {
                var row = $('<tr>').attr('data-allocation-pk', allocation.allocation_pk || allocation.bill_allocation_pk);
                
                if (isConstruction) {
                    row.append($('<td>').attr('data-item-pk', allocation.item_pk).text(allocation.item_name || '-'));
                    row.append($('<td>').text(allocation.unit || '-'));
                    row.append($('<td>').text(ProjectTypeConfig.formatNumber(allocation.qty, 2)));
                    row.append($('<td>').text(ProjectTypeConfig.formatCurrency(allocation.rate)));
                    row.append($('<td>').text(ProjectTypeConfig.formatCurrency(allocation.amount || allocation.net)));
                    row.append($('<td>').text(ProjectTypeConfig.formatCurrency(allocation.gst_amount || allocation.gst)));
                    row.append($('<td>').text(allocation.notes || '-'));
                    if (!isReadonly) row.append($('<td>')); // Delete column
                } else {
                    row.append($('<td>').attr('data-item-pk', allocation.item_pk).text(allocation.item_name || '-'));
                    row.append($('<td>').text(ProjectTypeConfig.formatCurrency(allocation.amount || allocation.net)));
                    row.append($('<td>').text(ProjectTypeConfig.formatCurrency(allocation.gst_amount || allocation.gst)));
                    row.append($('<td>').text(allocation.notes || '-'));
                    if (!isReadonly) row.append($('<td>')); // Delete column
                }
                
                return row;
            },
            
            // Gather bill allocation data from a row
            // Supports both .allocation-* and .bill-allocation-* class patterns
            gatherAllocationData: function(row, isConstruction) {
                var data = {
                    item_pk: row.find('.allocation-item-select, .bill-allocation-item-select').val() || row.attr('data-item-pk'),
                    notes: row.find('.allocation-notes-input, .bill-allocation-notes-input').val() || '',
                    amount: parseFloat(row.find('.allocation-net-input, .bill-allocation-net-input').val()) || 0,
                    gst_amount: parseFloat(row.find('.allocation-gst-input, .bill-allocation-gst-input').val()) || 0
                };
                
                if (isConstruction) {
                    data.qty = parseFloat(row.find('.allocation-qty-input, .bill-allocation-qty-input').val()) || null;
                    data.rate = parseFloat(row.find('.allocation-rate-input, .bill-allocation-rate-input').val()) || null;
                    data.unit = row.find('.allocation-unit-input, .bill-allocation-unit-input').val() || '';
                    // For construction, amount = qty * rate
                    if (data.qty && data.rate) {
                        data.amount = data.qty * data.rate;
                    }
                }
                
                return data;
            },
            
            // Render editable bill allocation row inputs (construction vs non-construction)
            // callbacks: { onItemChange, onAmountChange, onNotesChange }
            renderEditableRowInputs: function(row, itemSelect, alloc, isConstruction, callbacks) {
                if (isConstruction) {
                    // Construction mode: Item | Unit | Qty | $ Rate | $ Amount | Notes
                    
                    // Item dropdown with unit auto-populate
                    itemSelect.on('change', function() {
                        var selectedOption = $(this).find('option:selected');
                        var unit = selectedOption.attr('data-unit') || '';
                        row.find('.allocation-unit-display').text(unit);
                        row.find('.allocation-unit-input').val(unit);
                        if (callbacks.onItemChange) callbacks.onItemChange(row);
                    });
                    row.append($('<td>').append(itemSelect));
                    
                    // Unit (read-only, auto-populated from item)
                    var selectedUnit = alloc.unit || '';
                    var unitDisplay = $('<span>').addClass('allocation-unit-display').text(selectedUnit);
                    var unitInput = $('<input>').attr('type', 'hidden').addClass('allocation-unit-input').val(selectedUnit);
                    row.append($('<td>').append(unitDisplay).append(unitInput));
                    
                    // Qty input
                    var qtyInput = $('<input>')
                        .attr('type', 'number')
                        .attr('step', '0.01')
                        .addClass('form-control form-control-sm allocation-qty-input')
                        .val(alloc.qty ? parseFloat(alloc.qty).toFixed(2) : '')
                        .on('change input', function() {
                            var qty = parseFloat($(this).val()) || 0;
                            var rate = parseFloat(row.find('.allocation-rate-input').val()) || 0;
                            var amount = (qty * rate).toFixed(2);
                            row.find('.allocation-amount-display').text(ProjectTypeConfig.formatCurrency(parseFloat(amount)));
                            row.find('.allocation-net-input').val(amount);
                            if (callbacks.onAmountChange) callbacks.onAmountChange(row);
                        });
                    row.append($('<td>').append(qtyInput));
                    
                    // $ Rate input
                    var rateInput = $('<input>')
                        .attr('type', 'number')
                        .attr('step', '0.01')
                        .addClass('form-control form-control-sm allocation-rate-input')
                        .val(alloc.rate ? parseFloat(alloc.rate).toFixed(2) : '')
                        .on('change input', function() {
                            var qty = parseFloat(row.find('.allocation-qty-input').val()) || 0;
                            var rate = parseFloat($(this).val()) || 0;
                            var amount = (qty * rate).toFixed(2);
                            row.find('.allocation-amount-display').text(ProjectTypeConfig.formatCurrency(parseFloat(amount)));
                            row.find('.allocation-net-input').val(amount);
                            if (callbacks.onAmountChange) callbacks.onAmountChange(row);
                        });
                    row.append($('<td>').append(rateInput));
                    
                    // $ Amount (calculated, read-only display but hidden input for data)
                    var calcAmount = alloc.amount ? parseFloat(alloc.amount) : 0;
                    var amountDisplay = $('<span>').addClass('allocation-amount-display')
                        .text(ProjectTypeConfig.formatCurrency(calcAmount));
                    var amountHidden = $('<input>').attr('type', 'hidden')
                        .addClass('allocation-net-input').val(calcAmount.toFixed(2));
                    row.append($('<td>').append(amountDisplay).append(amountHidden));
                    
                    // Notes input
                    var notesInput = $('<input>')
                        .attr('type', 'text')
                        .addClass('form-control form-control-sm allocation-notes-input')
                        .attr('placeholder', 'Notes...')
                        .val(alloc.notes || '')
                        .on('change blur', function() {
                            if (callbacks.onNotesChange) callbacks.onNotesChange(row);
                        });
                    row.append($('<td>').append(notesInput));
                    
                } else {
                    // Non-construction mode: Item | $ Net | $ GST | Notes
                    itemSelect.on('change', function() {
                        if (callbacks.onItemChange) callbacks.onItemChange(row);
                    });
                    row.append($('<td>').append(itemSelect));
                    
                    // $ Net input with auto-GST calculation
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
                            // Auto-calculate GST as 10%
                            var gstInputEl = row.find('.allocation-gst-input');
                            if (!gstInputEl.data('manually-edited')) {
                                var netVal = parseFloat(value);
                                if (!isNaN(netVal)) {
                                    gstInputEl.val((netVal * 0.1).toFixed(2));
                                }
                            }
                            if (callbacks.onAmountChange) callbacks.onAmountChange(row);
                        });
                    row.append($('<td>').append(netInput));
                    
                    // $ GST input
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
                            if (callbacks.onAmountChange) callbacks.onAmountChange(row);
                        });
                    row.append($('<td>').append(gstInput));
                    
                    // Notes input
                    var notesInput = $('<input>')
                        .attr('type', 'text')
                        .addClass('form-control form-control-sm allocation-notes-input')
                        .attr('placeholder', 'Notes...')
                        .val(alloc.notes || '')
                        .on('change blur', function() {
                            if (callbacks.onNotesChange) callbacks.onNotesChange(row);
                        });
                    row.append($('<td>').append(notesInput));
                }
            }
        },
        
        // =====================================================================
        // PO (PURCHASE ORDERS) CONFIGURATION
        // =====================================================================
        pos: {
            // Column widths for PO tables
            columnWidths: {
                construction: ['28%', '8%', '10%', '12%', '15%', '12%'],  // Description, Units, Qty, Rate, Amount, Quote#
                nonConstruction: ['55%', '20%', '15%']  // Description, Amount, Quote#
            },
            
            headers: {
                construction: ['Description', 'Units', 'Qty', 'Rate', 'Amount', 'Quote #'],
                nonConstruction: ['Description', 'Amount', 'Quote #']
            },
            
            getColumns: function(isConstruction) {
                return {
                    widths: isConstruction ? this.columnWidths.construction : this.columnWidths.nonConstruction,
                    headers: isConstruction ? this.headers.construction : this.headers.nonConstruction
                };
            },
            
            // Format PO item for display
            formatItem: function(item, isConstruction) {
                if (isConstruction) {
                    return {
                        description: item.description || item.item_name,
                        unit: item.unit || '-',
                        qty: ProjectTypeConfig.formatNumber(item.qty, 2),
                        rate: ProjectTypeConfig.formatCurrency(item.rate),
                        amount: ProjectTypeConfig.formatCurrency(item.amount),
                        quoteNumber: item.quote_number || '-'
                    };
                } else {
                    return {
                        description: item.description || item.item_name,
                        amount: ProjectTypeConfig.formatCurrency(item.amount),
                        quoteNumber: item.quote_number || '-'
                    };
                }
            }
        },
        
        // =====================================================================
        // CONTRACT BUDGET CONFIGURATION
        // =====================================================================
        contractBudget: {
            // Column widths based on tender mode and construction type
            columnWidths: {
                executionConstruction: ['18%', '6%', '10%', '10%', '7%', '7%', '10%', '10%', '10%', '6%', '6%'],
                executionNonConstruction: ['22%', '6%', '12%', '12%', '12%', '12%', '12%', '6%', '6%'],
                tenderConstruction: ['24%', '8%', '16%', '10%', '10%', '16%', '16%'],
                tenderNonConstruction: ['32%', '10%', '18%', '20%', '20%']
            },
            
            // Headers for execution mode
            executionHeaders: {
                construction: {
                    row1: ['Category/Item', 'Unit', 'Contract Budget', 'Working Budget', 'Uncommitted', '', '', 'Committed', 'Cost to Complete', 'Billed', 'Fixed on Site'],
                    row2: ['', '', '', '', 'Qty', 'Rate', 'Amount', '', '', '', ''],
                    colspan: [1, 1, 1, 1, 3, 0, 0, 1, 1, 1, 1]  // 0 = skip (part of colspan)
                },
                nonConstruction: {
                    row1: ['Category/Item', 'Unit', 'Contract Budget', 'Working Budget', 'Uncommitted', 'Committed', 'Cost to Complete', 'Billed', 'Fixed on Site']
                }
            },
            
            // Headers for tender mode
            tenderHeaders: {
                construction: {
                    row1: ['Category/Item', 'Unit', 'Working Budget', 'Uncommitted', '', '', 'Committed'],
                    row2: ['', '', '', 'Qty', 'Rate', 'Amount', ''],
                    colspan: [1, 1, 1, 3, 0, 0, 1]
                },
                nonConstruction: {
                    row1: ['Category/Item', 'Unit', 'Working Budget', 'Uncommitted', 'Committed']
                }
            },
            
            getColumns: function(isTender, isConstruction) {
                var widthKey;
                if (isTender) {
                    widthKey = isConstruction ? 'tenderConstruction' : 'tenderNonConstruction';
                } else {
                    widthKey = isConstruction ? 'executionConstruction' : 'executionNonConstruction';
                }
                
                var headerKey = isTender ? 'tenderHeaders' : 'executionHeaders';
                var typeKey = isConstruction ? 'construction' : 'nonConstruction';
                
                return {
                    widths: this.columnWidths[widthKey],
                    headers: this[headerKey][typeKey],
                    colspan: isTender ? 
                        (isConstruction ? 11 : 9) : 
                        (isConstruction ? 7 : 5)
                };
            }
        },
        
        // =====================================================================
        // UTILITY FUNCTIONS
        // =====================================================================
        
        // Format a value as currency
        formatCurrency: function(value) {
            var num = parseFloat(value) || 0;
            return '$' + num.toLocaleString('en-AU', {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2
            });
        },
        
        // Format a number with specified decimal places
        formatNumber: function(value, decimals) {
            var num = parseFloat(value) || 0;
            return num.toLocaleString('en-AU', {
                minimumFractionDigits: decimals || 2,
                maximumFractionDigits: decimals || 2
            });
        },
        
        // Calculate amount from qty and rate
        calculateAmount: function(qty, rate) {
            return (parseFloat(qty) || 0) * (parseFloat(rate) || 0);
        },
        
        // Parse currency string to number
        parseCurrency: function(value) {
            if (typeof value === 'number') return value;
            return parseFloat(String(value).replace(/[^0-9.-]/g, '')) || 0;
        }
    };
    
})();
