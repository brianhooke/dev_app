document.addEventListener('DOMContentLoaded', function() {
    function showContactsModal(contacts) {
        var tableRows = contacts.map(function(contact) {
            return `
            <tr>
                <td>${contact.contact_name}</td>
                <td>${contact.contact_email}</td>
                <input type="hidden" value="${contact.contact_id}" class="contact-id">
            </tr>
            `;
        }).join('');
    
        var tableHTML = `
        <table>
            <thead>
                <tr>
                    <th>Contact</th>
                    <th>Email Address</th>
                </tr>
            </thead>
            <tbody>
                ${tableRows}
            </tbody>
        </table>
        <button id="addContactButton">+</button>
        `;
    
        // Assuming you have a modal with an element to hold the table
        var modalHtml = `
        <div class="modal fade" id="contactsModal" tabindex="-1" role="dialog" aria-hidden="true">
            <div class="modal-dialog modal-lg" role="document" style="max-width: 500px;">
                <div class="modal-content" style="border: 3px solid black;">
                    <div class="modal-header" style="text-align: center; background: linear-gradient(45deg, #A090D0 0%, #B3E1DD 100%);">
                        <h5 class="modal-title">Contacts</h5>
                    </div>
                    <div class="modal-body">
                        <div class="table-responsive">
                            <table>
                                ${tableHTML}
                            </table>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <div class="col-6">
                            <button type="button" class="btn btn-secondary" data-dismiss="modal">Close</button>
                        </div>
                        <div class="col-6 text-right">
                            <button type="button" class="btn btn-primary" id="saveButton" disabled>Save</button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        `;
    
        // Append the modal to the body
        $('body').append(modalHtml);
    
        // Show the modal
        $('#contactsModal').modal('show');
    
        // Remove the modal when it's hidden
        $('#contactsModal').on('hidden.bs.modal', function () {
            $(this).remove();
        });
    
        // Add event listener to '+' button
        document.getElementById('addContactButton').addEventListener('click', function() {
            // Code to show modal for creating new supplier goes here
        });
    }
    
    $(document).on('click', '#showContactsLink', function(event){
        event.preventDefault();
        showContactsModal(contacts);
    });

    $(document).on('click', '#addContactButton', function(event){
        event.preventDefault();
        var table = document.querySelector('#contactsModal table tbody');
        var row = table.insertRow(-1);
        var nameCell = row.insertCell(0);
        var emailCell = row.insertCell(1);
        var nameInput = document.createElement('input');
        var emailInput = document.createElement('input');
        nameInput.type = 'text';
        emailInput.type = 'text';
        nameInput.id = 'newContactName' + (table.rows.length - 1);  // Create a unique ID for each new contact
        emailInput.id = 'newContactEmail' + (table.rows.length - 1);  // Create a unique ID for each new contact's email
        nameCell.appendChild(nameInput);
        emailCell.appendChild(emailInput);
        // Enable the save button
        document.getElementById('saveButton').disabled = false;
    });
    
    $(document).on('click', '#saveButton', function(event){
        event.preventDefault();
        // Gather the new contacts and their email addresses
        var table = document.querySelector('#contactsModal table tbody');
        var newContacts = Array.from(table.querySelectorAll('input[id^="newContactName"]')).map((input, index) => {
            var rowIndex = Array.from(table.children).indexOf(input.parentElement.parentElement);
            return {
                name: input.value,
                email: document.getElementById('newContactEmail' + rowIndex).value
            };
        });
        // Send the new contacts to the server
        fetch('/create_contacts/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify({ contacts: newContacts })  // Wrap the array in an object
        }).then(function(response) {
            if (response.ok) {
                alert('Contacts saved successfully');
                location.reload();
            } else {
                alert('An error occurred.');
            }
        });
    });

});