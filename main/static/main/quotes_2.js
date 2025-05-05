// Initialize the committed quotes functionality when the document is ready
$(document).ready(function() {
    // Show modal when dropdown option is selected
    $('#dropdown').on('change', function() {
        if (this.value === 'committedQuotes') {
            $('#committedQuotesModal').modal('show');
            populateCommittedQuotesTable();
        }
    });
// Reset dropdown when committedQuotesModal is closed
$('#committedQuotesModal').on('hidden.bs.modal', function() {
    $('#dropdown').val('Quotes');
});
});

// Function to populate the committed quotes table
function populateCommittedQuotesTable() {

    // Clear existing table content
    const tableBody = document.querySelector("#committedQuotesTable tbody");
    tableBody.innerHTML = '';

    // Add each quote to the table
    committedQuotes.forEach(function(quote) {
        // Format total_cost with thousands separator
        var supplier_quote_number = quote.supplier_quote_number;
        var contact_pk = quote.contact_pk;
        var totalCostFormatted = parseFloat(quote.total_cost).toLocaleString();
        var supplier = quote.contact_pk__contact_name;
        
        // Create a new table row for each quote
        var newRow = document.createElement("tr");
        newRow.style.lineHeight = "1";
        
        newRow.innerHTML = `
            <td style="padding: 4px;">${supplier_quote_number}</td>
            <td style="padding: 4px;">${supplier}</td>
            <td style="padding: 4px;">${totalCostFormatted}</td>
            <td style="padding: 4px;"><a href="#" class="view-pdf">View</a></td>
            <td style="padding: 4px;"><a href="#" class="quote-link">Update</a></td>
            <td style="padding: 4px;"><a href="#" class="delete-link">Delete</a></td>
        `;
        
        tableBody.appendChild(newRow);
        
        // Add event listener for PDF viewing
        newRow.querySelector('.view-pdf').addEventListener('click', function(event) {
            event.preventDefault();
            document.getElementById('quotePdfViewer').src = quote.pdf;
        });
        
        // Add event listener to the delete link
        newRow.querySelector('.delete-link').addEventListener('click', function(event) {
        event.preventDefault();
        var confirmed = window.confirm('Are you sure you want to delete this quote?');
        if (confirmed) {
            // Send delete request to the server
            fetch('/delete_quote/', {
                method: 'DELETE',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    supplier_quote_number: supplier_quote_number,
                }),
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    // Remove the row from the table
                    newRow.remove();
                } else {
                    window.alert('Failed to delete quote: ' + data.message);
                }
            })
            .catch((error) => {
                console.error('Error:', error);
            });
        }
    });

    // Add event listener to the Quote # link
    newRow.querySelector('.quote-link').addEventListener('click', function(event) {
        event.preventDefault();
        var quote = committedQuotes.find(q => q.supplier_quote_number === supplier_quote_number);
        console.log("Quote is", quote.quotes_pk);
        var allocations = quote_allocations.filter(a => a.quotes_pk === quote.quotes_pk);
        var totalCost = parseFloat(totalCostFormatted.replace(/,/g, ''));
        $('#committedQuotesModal').modal('hide');
        console.log("Allocations are", allocations);
        displayCombinedModal(quote.pdf, quote.quotes_pk, supplier, contact_pk, totalCost, allocations, true, quote.supplier_quote_number);
    });
  });
}