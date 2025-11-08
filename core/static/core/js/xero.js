// Xero Instances Management

document.addEventListener('DOMContentLoaded', function() {
    
    // Show Xero Instances Modal when Xero navbar link is clicked
    $(document).on('click', '#xeroLink', function(event) {
        event.preventDefault();
        loadXeroInstances();
    });
    
    // Load Xero Instances from backend
    function loadXeroInstances() {
        fetch('/core/get_xero_instances/')
            .then(response => response.json())
            .then(data => {
                displayXeroInstances(data);
                $('#xeroInstancesModal').modal('show');
            })
            .catch(error => {
                console.error('Error loading Xero instances:', error);
                alert('Failed to load Xero instances');
            });
    }
    
    // Display Xero Instances in table
    function displayXeroInstances(instances) {
        const tbody = document.getElementById('xeroInstancesTableBody');
        tbody.innerHTML = '';
        
        if (instances.length === 0) {
            tbody.innerHTML = '<tr><td colspan="2" style="text-align: center;">No Xero instances found</td></tr>';
            return;
        }
        
        instances.forEach(instance => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${instance.xero_name}</td>
                <td>${instance.xero_client_id}</td>
            `;
            tbody.appendChild(row);
        });
    }
    
    // Show Add New Xero Instance Modal
    $(document).on('click', '#addNewXeroBtn', function() {
        // Clear form
        document.getElementById('xeroNameInput').value = '';
        document.getElementById('xeroClientIdInput').value = '';
        
        // Show second modal
        $('#addXeroInstanceModal').modal('show');
    });
    
    // Submit New Xero Instance
    $(document).on('click', '#submitXeroInstanceBtn', function() {
        const xeroName = document.getElementById('xeroNameInput').value.trim();
        const xeroClientId = document.getElementById('xeroClientIdInput').value.trim();
        
        if (!xeroName || !xeroClientId) {
            alert('Please fill in both fields');
            return;
        }
        
        // Get CSRF token
        const csrftoken = document.querySelector('[name=csrfmiddlewaretoken]').value;
        
        fetch('/core/create_xero_instance/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrftoken
            },
            body: JSON.stringify({
                xero_name: xeroName,
                xero_client_id: xeroClientId
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                alert('Xero instance added successfully');
                $('#addXeroInstanceModal').modal('hide');
                // Reload the main modal
                loadXeroInstances();
            } else {
                alert('Error: ' + data.message);
            }
        })
        .catch(error => {
            console.error('Error creating Xero instance:', error);
            alert('Failed to create Xero instance');
        });
    });
    
    // Clean up modals when closed
    $('#xeroInstancesModal').on('hidden.bs.modal', function () {
        // Don't remove the modal, just hide it
    });
    
    $('#addXeroInstanceModal').on('hidden.bs.modal', function () {
        // Clear form when closed
        document.getElementById('xeroNameInput').value = '';
        document.getElementById('xeroClientIdInput').value = '';
    });
});
