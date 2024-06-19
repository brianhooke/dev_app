$(document).ready(function() {
    $('#poDropdown').change(function() {
        if ($(this).val() === 'viewSendPo') {
            $('#createPoViewSendModal').modal('show');
        }
    });

    // Function to send emails for selected PO boxes when 'send email' clicked
    $('#sendEmailButton').click(function() {
        console.log('Send Email Button Clicked');
        var selectedPoOrderPks = [];
        $('.sent-checkbox:checked').each(function() {
            var poOrderPk = $(this).closest('tr').find('.po-order-pk').val();
            selectedPoOrderPks.push(poOrderPk);
        });

        console.log('Selected PO Order Pks:', selectedPoOrderPks);

        if (selectedPoOrderPks.length > 0) {
            $.ajax({
                url: '/send_po_emails/',
                type: 'POST',
                data: JSON.stringify({ po_order_pks: selectedPoOrderPks }),
                contentType: 'application/json',
                success: function(response) {
                    console.log('Success Response:', response);
                    alert('Emails sent successfully!');
                    location.reload();
                },
                error: function(error) {
                    console.error('Error sending emails:', error);
                    alert('An error occurred while sending the emails. Please try again.');
                }
            });
        } else {
            alert('Please select at least one PO Order to send.');
        }
    });
});
