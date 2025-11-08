// Xero Instances Management

document.addEventListener('DOMContentLoaded', function() {
    
    // Show Xero Instances Modal when Xero navbar link is clicked
    $(document).on('click', '#xeroLink', function(event) {
        event.preventDefault();
        loadXeroInstances();
    });
    
    // Load Xero Instances from backend
    function loadXeroInstances() {
        fetch('/get_xero_instances/')
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
            tbody.innerHTML = '<tr><td colspan="3" style="text-align: center;">No Xero instances found</td></tr>';
            return;
        }
        
        instances.forEach(instance => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${instance.xero_name}</td>
                <td>${instance.xero_client_id}</td>
                <td style="text-align: center;">
                    <button class="btn btn-sm btn-danger delete-xero-btn" data-instance-pk="${instance.xero_instance_pk}" data-instance-name="${instance.xero_name}">
                        <i class="fas fa-times"></i>
                    </button>
                </td>
            `;
            tbody.appendChild(row);
        });
    }
    
    // Delete Xero Instance
    $(document).on('click', '.delete-xero-btn', function() {
        const instancePk = $(this).data('instance-pk');
        const instanceName = $(this).data('instance-name');
        
        if (!confirm(`Are you sure you want to delete "${instanceName}"?`)) {
            return;
        }
        
        // Get CSRF token
        const csrftoken = document.querySelector('[name=csrfmiddlewaretoken]').value;
        
        fetch(`/delete_xero_instance/${instancePk}/`, {
            method: 'DELETE',
            headers: {
                'X-CSRFToken': csrftoken
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                alert(data.message);
                // Reload the table
                loadXeroInstances();
            } else {
                alert('Error: ' + data.message);
            }
        })
        .catch(error => {
            console.error('Error deleting Xero instance:', error);
            alert('Failed to delete Xero instance');
        });
    });
    
    // Show Add New Xero Instance Modal
    $(document).on('click', '#addNewXeroBtn', function() {
        // Clear form
        document.getElementById('xeroNameInput').value = '';
        document.getElementById('xeroClientIdInput').value = '';
        document.getElementById('xeroClientSecretInput').value = '';
        
        // Show second modal
        $('#addXeroInstanceModal').modal('show');
    });
    
    // Submit New Xero Instance
    $(document).on('click', '#submitXeroInstanceBtn', function() {
        const xeroName = document.getElementById('xeroNameInput').value.trim();
        const xeroClientId = document.getElementById('xeroClientIdInput').value.trim();
        const xeroClientSecret = document.getElementById('xeroClientSecretInput').value.trim();
        
        if (!xeroName || !xeroClientId || !xeroClientSecret) {
            alert('Please fill in all fields');
            return;
        }
        
        // Get CSRF token
        const csrftoken = document.querySelector('[name=csrfmiddlewaretoken]').value;
        
        fetch('/create_xero_instance/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrftoken
            },
            body: JSON.stringify({
                xero_name: xeroName,
                xero_client_id: xeroClientId,
                xero_client_secret: xeroClientSecret
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
        document.getElementById('xeroClientSecretInput').value = '';
    });
});
