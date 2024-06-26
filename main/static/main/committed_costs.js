// Create a new div element
var newDiv = document.createElement("div");
newDiv.innerHTML = `
<div class="modal fade" id="committedQuotesModal" tabindex="-1" role="dialog" aria-labelledby="committedQuotesModalLabel" aria-hidden="true">
  <div class="modal-dialog" role="document">
    <div class="modal-content">
      <div class="modal-header">
        <h5 class="modal-title" id="committedQuotesModalLabel">Committed Quotes</h5>
        <button type="button" class="close" data-dismiss="modal" aria-label="Close">
          <span aria-hidden="true">&times;</span>
        </button>
      </div>
      <div class="modal-body">
        <table id="committedQuotesTable" class="table">
          <thead>
            <tr>
              <th>Quote #</th>
              <th>Supplier</th>
              <th>Total Cost</th>
              <th rowspan="2" class="delete-cell-header delete-column">Delete</th>
            </tr>
          </thead>
          <tbody>
            <!-- Table rows will be inserted here -->
          </tbody>
        </table>
      </div>
      <div class="modal-footer">
        <button type="button" class="btn btn-secondary" data-dismiss="modal">Close</button>
      </div>
    </div>
  </div>
</div>`;
document.body.appendChild(newDiv);
document.getElementById('dropdown').addEventListener('change', function() {
  if (this.value === 'committedQuotes') {
      $('#committedQuotesModal').modal('show');
  }
});

// Get the table body
var tableBody = document.querySelector("#committedQuotesTable tbody");
// Loop through each committed quote
$(document).ready(function() {
    $('.modal-footer .btn-secondary').on('click', function() {
        location.reload();
    });
});

committedQuotes.forEach(function(quote) {
    // Format total_cost with thousands separator
    var supplier_quote_number = quote.supplier_quote_number;
    var contact_pk = quote.contact_pk;
    var totalCostFormatted = parseFloat(quote.total_cost).toLocaleString();
    var supplier = quote.contact_pk__contact_name;
    // Create a new table row for each quote
    var newRow = document.createElement("tr");
    newRow.innerHTML = `<td><a href="#" class="quote-link">${supplier_quote_number}</a></td><td>${supplier}</td><td>${totalCostFormatted}</td><td class="delete-column"><button class="btn btn-danger delete-btn">X</button></td>`;
    // Append the table row to the table body
    tableBody.appendChild(newRow);
    // Add event listener to the delete button
    newRow.children[3].children[0].addEventListener('click', function(event) {
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

    // Add event listener to the 'Quote #' cell
    newRow.children[0].addEventListener('click', function() {
      // Get the quote data
      var quote = committedQuotes.find(q => q.supplier_quote_number === supplier_quote_number);
      var allocations = committed_allocations.filter(a => a.quote_id === quote.quote);
      var totalCost = parseFloat(totalCostFormatted.replace(/,/g, ''));
      $('#committedQuotesModal').modal('hide');
      console.log("Allocations are", allocations);
      // Pass the PDF data, supplier, and supplier_quote_number to the displayCombinedModal function
      displayCombinedModal(quote.pdf, quote.quote, supplier, contact_pk, totalCost, allocations, true, quote.supplier_quote_number);
  });  
});
