document.addEventListener('DOMContentLoaded', function() {
    function showContactsModal(contacts) {
        // Ensure contacts is an array
        const contactsArray = Array.isArray(contacts) ? contacts : [];
        
        var tableRows = contactsArray.map(function(contact, index) {
            return `
            <tr>
                <td>${contact.contact_name}</td>
                <td><a href="#" class="email-field" data-index="${index}">${contact.contact_email}</a></td>
                <td><input type="checkbox" class="supplier-checkbox" ${contact.checked == 1 || contact.checked == 3 ? 'checked' : ''}></td>
                <td><input type="checkbox" class="client-checkbox" ${contact.checked == 2 || contact.checked == 3 ? 'checked' : ''}></td>
                <input type="hidden" value="${contact.contact_pk}" class="contact-pk">
            </tr>
            `;
        }).join('');

        var tableHTML = `
        <table id="contactsTable">
            <thead>
                <tr>
                    <th>Contact</th>
                    <th>Email Address</th>
                    <th>Selectable Supplier</th>
                    <th>Selectable Client</th>

                </tr>
            </thead>
            <tbody>
                ${tableRows}
            </tbody>
        </table>
        `;
    
        var modalTitle;
        if (division == 1) {
            modalTitle = "Mason Development Group Suppliers";
        } else if (division == 2) {
            modalTitle = "Mason Build Suppliers";
        } else {
            modalTitle = "Contacts";
        }
        
        var modalHtml = `
        <div class="modal fade" id="contactsModal" tabindex="-1" role="dialog" aria-hidden="true">
            <div class="modal-dialog modal-lg" role="document" style="max-width: 800px;">
                <div class="modal-content" style="border: 3px solid black;">
                    <div class="modal-header" style="text-align: center; background: linear-gradient(45deg, #A090D0 0%, #B3E1DD 100%);">
                        <h5 class="modal-title">${modalTitle}</h5>
                    </div>
                    <div class="modal-body" style="max-height: calc(100vh - 210px); overflow-y: auto;">
                        <div class="table-responsive">
                            <table>
                                ${tableHTML}
                            </table>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <div class="col-4">
                            <button type="button" class="btn btn-secondary" data-dismiss="modal">Close</button>
                        </div>
                        <div class="col-4 text-center">
                            <button type="button" class="btn btn-primary" id="addContactButton">Update Xero Contacts</button>
                        </div>
                        <div class="col-4 text-right">
                            <button type="button" class="btn btn-primary" id="saveButton">Save</button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        `;
    
        $('body').append(modalHtml);
        $('#contactsModal').modal('show');
        $('#contactsModal').on('hidden.bs.modal', function () {
            $(this).remove();
        });
    
        // document.getElementById('addContactButton').addEventListener('click', function() {
        //     fetch('/get_xero_contacts/', {
        //         method: 'GET', // or 'POST'
        //         headers: {
        //             'Content-Type': 'application/json',
        //             // 'X-CSRFToken': csrftoken  // Uncomment this line if you're using CSRF protection
        //         },
        //     })
        //     .then(response => {
        //         if (!response.ok) {
        //             throw new Error('Network response was not ok');
        //         }
        //         return response.json();
        //     })
        //     .then(data => {
        //         console.log(data);
        //         alert('Xero Contacts Successfully Updated.');
        //         location.reload();
        //     })
        //     .catch((error) => {
        //         console.error('Error:', error);
        //         alert('Operation failed. Please try again.');
        //     });
        // });

        document.getElementById('addContactButton').addEventListener('click', function() {
            // var division = division; // Assuming invoiceDivision is globally available
            console.log("Division for contact is:", division);
            fetch('/get_xero_contacts/?division=' + division, {
                method: 'GET', // or 'POST'
                headers: {
                    'Content-Type': 'application/json',
                    // 'X-CSRFToken': csrftoken  // Uncomment this line if you're using CSRF protection
                },
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.json();
            })
            .then(data => {
                console.log(data);
                alert('Xero Contacts Successfully Updated.');
                location.reload();
            })
            .catch((error) => {
                console.error('Error:', error);
                alert('Operation failed. Please try again.');
            });
        });
    
        document.querySelectorAll('.email-field').forEach(function(emailField) {
            emailField.addEventListener('click', function(event) {
                event.preventDefault();
                if (this.querySelector('input')) {
                    return;
                }
                var index = this.dataset.index;
                var currentEmail = this.textContent;
                this.innerHTML = `<input type="text" value="${currentEmail}">`;
                this.querySelector('input').focus();
            });
        });

        document.getElementById('saveButton').addEventListener('click', function() {
            var rows = Array.from(document.querySelectorAll('#contactsTable tbody tr'));
            var data = rows.map(function(row) {
                var contact_pk = row.querySelector('.contact-pk') ? row.querySelector('.contact-pk').value : null;
                var emailField = row.querySelector('.email-field');
                var contact_email = emailField.querySelector('input') ? emailField.querySelector('input').value : emailField.textContent;
                var supplierCheckbox = row.querySelector('.supplier-checkbox');
                var clientCheckbox = row.querySelector('.client-checkbox');
                var checked = 0;
                if (supplierCheckbox.checked) {
                    checked += 1;
                }
                if (clientCheckbox.checked) {
                    checked += 2;
                }
                return {
                    contact_pk: contact_pk,
                    contact_email: contact_email,
                    checked: checked
                };
            });

            $.ajax({
                url: '/update_contacts', // replace with your server endpoint
                type: 'POST',
                data: JSON.stringify(data),
                contentType: 'application/json',
                success: function(response) {
                    // handle success
                    console.log(response);
                    location.reload();
                },
                error: function(error) {
                    // handle error
                    console.error(error);
                }
            });
        });
    }

    $(document).on('click', '#showContactsLink', function(event){
        event.preventDefault();
        showContactsModal(contacts_unfiltered);
    });
});