$(document).ready(function() {
    $('#poBuildDropdown').change(function() {
        if ($(this).val() === 'createPoBuild') {
            $('#createBuildPoSelectModal').modal('show');
        }
    });

    $('#saveBuildCategoryButton').click(function() {
        var selectedSupplierPk = $('#poBuildSupplierSelect option:selected').val();
        console.log('Selected Supplier PK:', selectedSupplierPk); // Log the selected supplier pk
        var selectedSupplierName = $('#poBuildSupplierSelect option:selected').text();
        $('#createPoModalBuild .modal-body p').text('Supplier: ' + selectedSupplierName);
        $('#createBuildPoSelectModal').modal('hide');
        $('#createPoModalBuild').modal('show');
        $.ajax({
            url: '/get_build_quote_allocations/' + selectedSupplierPk + '/',
            type: 'GET',
            success: function(response) {
                console.log('GET request response:', response); // Log the entire response
                
                var tableBody = $('#createPoModalBuild .table tbody');
                var tableHead = $('#createPoModalBuild .table thead');
                var costings = response.costings;
                console.log('Costings:', costings); // Log the costings part of the response
                
                delete response.costings; // Remove costings from the response object
                var data = response; // Now data only contains the item data
                console.log('Data (without costings):', data); // Log the data part of the response
                
                tableBody.empty();
                tableHead.empty();
                var quoteNumbers = [];
                var quotePks = {};
                for (var item in data) {
                    data[item].forEach(function(quote_allocation) {
                        if (!quoteNumbers.includes(quote_allocation.quote_number)) {
                            quoteNumbers.push(quote_allocation.quote_number);
                            quotePks[quote_allocation.quote_number] = quote_allocation.quote_id;
                        }
                    });
                }
    
                var headerRow = '<tr><th>Item</th>'; // Start with Item column header
                for (var i = 0; i < quoteNumbers.length; i++) {
                    headerRow += '<th>Quote # ' + quoteNumbers[i] + '</th>';
                }
                headerRow += '<th>Variations</th><th>Total</th></tr>'; // Add Variation and Total column headers
                tableHead.append(headerRow);
    
                var columnTotals = new Array(quoteNumbers.length).fill(0); // Initialize column totals
    
                for (var item in data) {
                    if (data[item].length > 0) {
                        var row = '<tr data-item-pk="' + data[item][0].item_id + '"><td>' + item + '</td>'; // Start with Item cell and add item_id as data attribute
                        console.log('Item:', item, "data-item-pk:", data[item][0].item_id); // Log the item name    
                        var rowTotal = 0;
                        quoteNumbers.forEach(function(quoteNumber, index) {
                            var quote_allocation = data[item].find(function(qa) {
                                return qa.quote_number === quoteNumber;
                            });
                            if (quote_allocation) {
                                var formattedAmount = parseFloat(quote_allocation.amount).toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2});
                                row += '<td data-quote-id="' + quote_allocation.quote_id + '">' + formattedAmount + '</td>'; // Add quote_id as data attribute
                                rowTotal += parseFloat(quote_allocation.amount);
                                columnTotals[index] += parseFloat(quote_allocation.amount); // Add to column total
                            } else {
                                row += '<td data-quote-id="' + quotePks[quoteNumber] + '">0.00</td>'; // Add quote_id as data attribute even for empty cells
                            }
                        });
                        var formattedRowTotal = rowTotal.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2});
                        row += '<td><button type="button" class="btn btn-small addVariationButton">+</button></td>'; // Add Variation cell
                        row += '<td class="total-column">' + formattedRowTotal + '</td></tr>'; // Add row total cell last
                        tableBody.append(row);
                    }
                }
    
                var footerRow = '<tr><td><strong>Total</strong></td>';
                columnTotals.forEach(function(total) {
                    var formattedTotal = total.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2});
                    footerRow += '<td class="footer-column">' + formattedTotal + '</td>';
                });
                var overallTotal = columnTotals.reduce((acc, val) => acc + val, 0);
                var formattedOverallTotal = overallTotal.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2});
                footerRow += '<td></td><td class="overall-total">' + formattedOverallTotal + '</td></tr>'; // Overall total and empty cell for Add Variation
    
                $('#createPoModalBuild .table').append('<tfoot>' + footerRow + '</tfoot>');
    
                // Add "Add new Item" button after the table with the same styling
                var addItemButton = '<div style="display: flex; justify-content: center; width: 25%; padding: 2px;"><div style="width: 90%;"><button type="button" class="btn btn-primary addItemButton" style="background-color: white; color: black; border: 3px solid; border-image: linear-gradient(45deg, #A090D0 0%, #B3E1DD 100%) 1; width: 100%; white-space: nowrap; font-size: 1em;"><strong>Add new Item</strong></button></div></div>';
                $('#createPoModalBuild .modal-body').append(addItemButton);
    
                // Add Note rows after the "Add new Item" button
                var notesRows = `
                <div class="form-group" style="display: flex; align-items: center;"><label for="note1" style="flex: 1;">Note 1:</label><input type="text" id="note1" class="form-control" style="flex: 4;"></div>
                <div class="form-group" style="display: flex; align-items: center;"><label for="note2" style="flex: 1;">Note 2:</label><input type="text" id="note2" class="form-control" style="flex: 4;"></div>
                <div class="form-group" style="display: flex; align-items: center;"><label for="note3" style="flex: 1;">Note 3:</label><input type="text" id="note3" class="form-control" style="flex: 4;"></div>
            `;            
                $('#createPoModalBuild .modal-body').append(notesRows); 
                // Add event listener to the "Add new Item" button
                $('.addItemButton').click(function() {
                    var newRow = '<tr><td><select class="item-select"><option value="" disabled selected>Select Item...</option>';
                    var filteredCostings = costings.filter(function(costing) {
                        return !data.hasOwnProperty(costing.item);
                    });
                    for (var i = 0; i < filteredCostings.length; i++) {
                        newRow += '<option value="' + filteredCostings[i].item + '" data-item-pk="' + filteredCostings[i].id + '">' + filteredCostings[i].item + '</option>'; // Add item_id as data attribute
                    }
                    newRow += '</select><input type="hidden" class="item-pk" /></td>';
                    for (var i = 0; i < quoteNumbers.length; i++) {
                        newRow += '<td></td>';
                    }
                    newRow += '<td><button type="button" class="btn btn-small addVariationButton">+</button></td><td class="total-column">0.00</td></tr>'; // Add 'total-column' class
                    tableBody.append(newRow);
                    bindSelectEvent(); // Bind the select event here
                    // Re-bind events to the new row
                    bindEventsToRow();
                });
    
                function bindSelectEvent() {
                    $('.item-select').off('change').on('change', function() {
                        var selectedOption = $(this).find('option:selected');
                        var selectedItem = selectedOption.text();
                        var selectedItemPk = selectedOption.data('item-pk'); // Correct way to access data attribute using data()
                        // Debugging lines
                        console.log('Selected Option:', selectedOption); 
                        // console.log('Selected Primary Key:', selectedItemPk); 
                        console.log('Selected Option Data Attribute (item-pk):', selectedOption.data('item-pk')); 
                        $(this).siblings('.item-pk').val(selectedItemPk);
                        $(this).closest('tr').attr('data-item-pk', selectedItemPk); // Store the item_id as a data attribute on the row
                        $(this).closest('td').text(selectedItem);
                        console.log('Selected Item:', selectedItem);
                        console.log('Selected Item PK:', selectedItemPk);
                    });
                }
    
                // Call bindEventsToRow after initial table generation
                bindEventsToRow();
    
                function bindEventsToRow() {
                    $('.addVariationButton').off('click').on('click', function() {
                        var row = $(this).closest('tr'); // Get the row of the "+" button
                        var firstCell = row.children('td').eq(0); // Get the first cell in the row
                        var uniqueClass = 'sub-row-' + Date.now(); // Generate a unique class based on the current time
                        var newContent = '<div class="' + uniqueClass + '"><div class="sub-row"><div style="border-bottom: none; min-height: 20px;"></div><div class="variation-text" style="border-bottom: none;">→ <input type="text" class="notes-input" placeholder="Variation - add notes..."></div></div></div>'; // The new content to add
                        firstCell.append(newContent); // Append the new content to the existing content
                        var variationTextHeight = $('.variation-text').css('height');
                        var variationCell = row.children('td').eq(-2); // Get the second last cell in the row
                        variationCell.append('<div class="' + uniqueClass + '"><div class="sub-row"><div style="border-bottom: none;"><input type="text" class="numeric-input" data-old-value="0" placeholder="Enter $ amount..." style="height: ' + variationTextHeight + '; margin-right: 5px;"></div><div style="border-bottom: none; min-height: 20px;"></div></div></div>');
                        $('.numeric-input').on('input', function() {
                            this.value = this.value.replace(/[^0-9.]/g, '').replace(/(\..*)\./g, '$1');
                            updateTotals();
                        });
                    });
    
                    $('.numeric-input').off('input').on('input', function() {
                        var inputValue = parseFloat($(this).val()) || 0;
                        var oldInputValue = parseFloat($(this).attr('data-old-value')) || 0;
                        var row = $(this).closest('tr');
                        var formattedTotal = parseFloat(row.find('.total-column').text().replace(/,/g, '')) || 0;
                        row.find('.total-column').text((formattedTotal - oldInputValue + inputValue).toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2}));
                        $(this).attr('data-old-value', inputValue);
                        updateTotals();
                    });
    
                    bindSelectEvent(); // Ensure the event is bound for existing rows as well
                }
    
                function updateTotals() {
                    var columnTotals = new Array(quoteNumbers.length).fill(0);
                    $('#createPoModalBuild .table tbody tr').each(function() {
                        var rowTotal = 0;
                        $(this).find('td:not(:first-child):not(:last-child)').each(function(index) {
                            var cellValue = parseFloat($(this).text().replace(/,/g, '')) || 0;
                            rowTotal += cellValue;
                            columnTotals[index] += cellValue;
                        });
                        $(this).find('.total-column').text(rowTotal.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2}));
                    });
                    columnTotals.forEach(function(total, index) {
                        $('#createPoModalBuild .table tfoot .footer-column').eq(index).text(total.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2}));
                    });
                    var overallTotal = columnTotals.reduce((acc, val) => acc + val, 0);
                    $('.overall-total').text(overallTotal.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2}));
                }
    
                $('#createPoButton').click(function() {
                    var selectedSupplierPk = $('#poBuildSupplierSelect option:selected').val();
                    var rowData = [];
                    var rowsProcessed = new Set(); // Track processed rows to avoid duplication
                    $('#createPoModalBuild .table tbody tr').each(function() {
                        var itemPk = $(this).data('item-pk'); // Get item_id from row's data attribute
                        if (!itemPk) {
                            console.error('Item PK is undefined for row:', $(this));
                            return; // Skip this row
                        }
                        console.log('Processing Row - Item PK:', itemPk);
                
                        // Process quotes
                        $(this).find('td').not(':first').not(':last').not('.total-column').each(function(index) {
                            var cellValue = $(this).text().trim().replace(/,/g, ''); // Remove commas from the amount
                            if (cellValue !== '0.00' && cellValue !== '+' && cellValue !== '') {
                                var quoteId = $(this).data('quote-id'); // Get quote id from data attribute
                                if (!quoteId) {
                                    console.error('Quote ID is undefined for cell:', $(this));
                                    return; // Skip this cell
                                }
                                console.log(`Processing Quote - Item PK: ${itemPk}, Quote ID: ${quoteId}, Amount: ${cellValue}`); // Log the quote data
                                var uniqueRowIdentifier = `${itemPk}-Quote-${quoteId}`;
                                if (!rowsProcessed.has(uniqueRowIdentifier)) {
                                    rowData.push({ itemPk: itemPk, quoteId: quoteId, amount: cellValue });
                                    rowsProcessed.add(uniqueRowIdentifier);
                                }
                            }
                        });
                
                        // Process variations
                        $(this).find('.numeric-input').each(function() {
                            var inputValue = $(this).val().trim().replace(/,/g, ''); // Remove commas from the amount
                            if (inputValue !== '' && inputValue !== '0.00') {
                                var notes = $(this).closest('tr').find('.notes-input').val().trim(); // Get the notes
                                console.log(`Processing Variation - Item PK: ${itemPk}, Amount: ${inputValue}, Notes: ${notes}`); // Log the variation data
                                var uniqueRowIdentifier = `${itemPk}-Variation-${inputValue}`;
                                if (!rowsProcessed.has(uniqueRowIdentifier)) {
                                    rowData.push({ itemPk: itemPk, quoteId: null, amount: inputValue, notes: notes });
                                    rowsProcessed.add(uniqueRowIdentifier);
                                }
                            }
                        });
                    });
                
                    // Retrieve notes from input fields
                    var note1 = $('#note1').val().trim();
                    var note2 = $('#note2').val().trim();
                    var note3 = $('#note3').val().trim();
                
                    // Add notes and supplier to the data
                    var postData = {
                        supplierPk: selectedSupplierPk,
                        notes: { note1: note1, note2: note2, note3: note3 },
                        rows: rowData
                    };
                
                    console.log('POST Data:', JSON.stringify(postData)); // Log the POST data
                
                    // Send data to the server
                    $.ajax({
                        url: '/create_build_po_order/',
                        type: 'POST',
                        data: JSON.stringify(postData),
                        contentType: 'application/json',
                        success: function(response) {
                            console.log('POST request response:', response); // Log the response
                            alert('PO Order created successfully!');
                            // location.reload();
                        },
                        error: function(error) {
                            console.error('Error creating PO Order:', error);
                            alert('An error occurred while creating the PO Order.');
                        }
                    });
                });
            }
        });
    });
});