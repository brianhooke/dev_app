document.addEventListener('DOMContentLoaded', function() {

$(document).ready(function(){
    $("#uploadContactsButton").click(function(){
        $("#csvFileInput").click();
    });
    $("#csvFileInput").change(function(){
        var formData = new FormData();
        formData.append('file', $('#csvFileInput')[0].files[0]);
        $.ajax({
            url: '/upload_contacts/',
            type: 'POST',
            data: formData,
            processData: false,
            contentType: false,
            headers: {
                'X-CSRFToken': getCookie('csrftoken')
            },
            success: function(data, status) {
                // Handle success
            },
            error: function(xhr, status, error) {
                // Handle error
            }
        });
    });
});

function getCookie(name) {
    var cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        var cookies = document.cookie.split(';');
        for (var i = 0; i < cookies.length; i++) {
            var cookie = jQuery.trim(cookies[i]);
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// $(document).ready(function() {
//     $('#id_csv_file').on('change', function() {
//         var form = $('#upload-form')[0];
//         var formData = new FormData(form);
//         $.ajax({
//             url: '/upload_csv/',  // replace with your actual endpoint
//             type: 'POST',
//             data: formData,
//             processData: false,
//             contentType: false,
//             success: function(response) {
//                 alert('CSV file uploaded successfully');
//                 location.reload();
//             },
//             error: function(jqXHR, textStatus, errorThrown) {
//             alert(jqXHR.responseJSON.message);
//             location.reload();
//             }
//         });
//     });
// });

$(document).ready(function() {
    $('#uploadCostingsButton').on('click', function() {
        $('#id_csv_file').click();
    });

    $('#id_csv_file').on('change', function() {
        var formData = new FormData();
        formData.append('csv_file', this.files[0]);
        $.ajax({
            url: '/upload_csv/',  // replace with your actual endpoint
            type: 'POST',
            data: formData,
            processData: false,
            contentType: false,
            success: function(response) {
                alert('CSV file uploaded successfully');
                location.reload();
            },
            error: function(jqXHR, textStatus, errorThrown) {
                alert(jqXHR.responseJSON.message);
                location.reload();
            }
        });
    });
});

$(document).ready(function() {
  $('#uploadButton').on('click', function() {
      $('#csvFile').click();
  });
  $('#csvFile').on('change', function() {
      var formData = new FormData();
      formData.append('csv_file', this.files[0]);
      $.ajax({
          url: '/upload_categories/',
          type: 'POST',
          data: formData,
          processData: false,
          contentType: false,
          success: function(response) {
              alert('CSV file uploaded successfully');
              location.reload();
          },
          error: function(jqXHR, textStatus, errorThrown) {
              alert(jqXHR.responseJSON.message);
              location.reload();
          }
      });
  });
});

// Send uncommitted costs to DB
$('.save-costs').click(function() {
    var costingId = $(this).data('id');  // Get the costing id from the data-id attribute
    var newUncommittedValue = $('#uncommittedInput' + costingId).val();  // Get the new uncommitted value from the input field

    if (!costingId || !newUncommittedValue) {
        alert('Costing ID or uncommitted value is missing');
        return;
    }

    var data = {
        'costing_id': costingId,
        'uncommitted': newUncommittedValue
    };

    console.log("Data being sent to server:", data);

    fetch('/update_costing/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: JSON.stringify(data)
    }).then(function(response) {
        if (response.ok) {
            alert('Costs updated successfully');
            location.reload();
        } else {
            alert('An error occurred.');
        }
    });
});


for (var item_id in hc_claim_lines_sums) {
    var cell = document.getElementById("hc_claimed_" + item_id);
    if (cell) {
        var amount = parseFloat(hc_claim_lines_sums[item_id]);
        cell.textContent = amount.toLocaleString('en', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }
}



function populateModal(quoteNumber) {
    // Retrieve the corresponding Committed_quotes and Committed_allocations data
    var quote = committedQuotes.find(q => q.pk === quoteNumber);
    var allocations = committed_allocations.filter(a => a.fields.quote === quoteNumber);
    // Populate the modal fields with this data
    document.getElementById('supplierInput').value = quote.fields.supplier;
    document.getElementById('totalCostInput').value = quote.fields.total_cost;
    allocations.forEach(function(allocation) {
        addLineItem(allocation.fields.item, allocation.fields.amount);
    });
    // Open the modaly
    $('#combinedModal').modal('show');
}
});