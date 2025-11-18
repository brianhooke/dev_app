// Xero Instances Management

document.addEventListener('DOMContentLoaded', function() {
    
    // Show Xero Instances inline in workspace when Xero navbar link is clicked
    $(document).on('click', '#xeroLink', function(event) {
        event.preventDefault();
        
        // Remove active class from all nav items and set this one
        $('.reusable-navbar a').removeClass('active');
        $(this).addClass('active');
        
        // Hide all other sections
        $('#billsInboxSection').hide();
        $('#allocationsSection').hide();
        $('#contactsSection').css('display', 'none');
        
        // Show Xero section and hide empty state
        $('#emptyState').hide();
        $('#xeroSection').css('display', 'flex').show();
        
        // Load Xero instances
        loadXeroInstances();
        
        // Scroll to top
        $('html, body').animate({ scrollTop: 0 }, 300);
    });
    
    // Load Xero Instances from backend
    function loadXeroInstances() {
        fetch('/core/get_xero_instances/')
            .then(response => response.json())
            .then(data => {
                displayXeroInstances(data);
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
            tbody.innerHTML = '<tr><td colspan="4" style="text-align: center; padding: 20px; color: #999;">No Xero instances found</td></tr>';
            return;
        }
        
        instances.forEach(instance => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${instance.xero_name}</td>
                <td style="text-align: center;">
                    <button class="btn btn-sm btn-primary test-xero-btn" data-instance-pk="${instance.xero_instance_pk}" data-instance-name="${instance.xero_name}">
                        Test
                    </button>
                </td>
                <td style="text-align: center;">
                    <button class="btn btn-sm btn-info authorize-xero-btn" data-instance-pk="${instance.xero_instance_pk}" data-instance-name="${instance.xero_name}">
                        <i class="fas fa-key"></i> Authorize
                    </button>
                </td>
                <td style="text-align: center;">
                    <button class="btn btn-sm btn-danger delete-xero-btn" data-instance-pk="${instance.xero_instance_pk}" data-instance-name="${instance.xero_name}">
                        <i class="fas fa-times"></i>
                    </button>
                </td>
            `;
            tbody.appendChild(row);
        });
    }
    
    // Authorize Xero Instance
    $(document).on('click', '.authorize-xero-btn', function() {
        const instancePk = $(this).data('instance-pk');
        const instanceName = $(this).data('instance-name');
        
        if (confirm(`Authorize "${instanceName}" with Xero?\n\nThis will redirect you to Xero to grant permissions.`)) {
            window.location.href = `/core/xero_oauth_authorize/${instancePk}/`;
        }
    });
    
    // Test Xero Connection
    $(document).on('click', '.test-xero-btn', function() {
        const instancePk = $(this).data('instance-pk');
        const instanceName = $(this).data('instance-name');
        const button = $(this);
        const row = button.closest('tr');
        
        // Disable button and show loading state
        button.prop('disabled', true).html('<i class="fas fa-spinner fa-spin"></i> Testing...');
        
        fetch(`/core/test_xero_connection/${instancePk}/`, {
            method: 'GET'
        })
        .then(response => response.json().then(data => ({status: response.status, body: data})))
        .then(({status, body}) => {
            // Handle OAuth authorization needed
            if (status === 401 && body.needs_auth) {
                button.prop('disabled', false).html('Test');
                if (confirm('This Xero instance needs authorization. Would you like to authorize now?')) {
                    window.location.href = `/core/xero_oauth_authorize/${instancePk}/`;
                }
                return;
            }
            
            if (body.status === 'success') {
                // Change button to green tick (no alert needed)
                button.removeClass('btn-primary').addClass('btn-success');
                button.prop('disabled', false).html('<i class="fas fa-check"></i>');
                
                // Update the name in the table if it changed
                if (body.details && body.details.xero_org_name) {
                    row.find('td:first').text(body.details.xero_org_name);
                }
            } else {
                button.prop('disabled', false).html('Test');
                
                // Only show error alerts, not success
                alert(`✗ Test Failed\n\n${body.message}`);
            }
        })
        .catch(error => {
            button.prop('disabled', false).html('Test');
            console.error('Error testing Xero connection:', error);
            alert('✗ Test Failed\n\nFailed to connect to server');
        });
    });
    
    // Delete Xero Instance
    $(document).on('click', '.delete-xero-btn', function() {
        const instancePk = $(this).data('instance-pk');
        const instanceName = $(this).data('instance-name');
        
        if (!confirm(`Are you sure you want to delete "${instanceName}"?`)) {
            return;
        }
        
        // Get CSRF token
        const csrftoken = document.querySelector('[name=csrfmiddlewaretoken]').value;
        
        fetch(`/core/delete_xero_instance/${instancePk}/`, {
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
        
        fetch('/core/create_xero_instance/', {
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
