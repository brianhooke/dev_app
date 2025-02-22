// Key sequence handler for admin controls
const ADMIN_KEY_SEQUENCE = ['Shift', 'm', 'a', 's', 'o', 'n'];
let currentSequence = [];
let shiftPressed = false;

document.addEventListener('keydown', function(event) {
    // Handle Shift key
    if (event.key === 'Shift') {
        shiftPressed = true;
        currentSequence = [];
        currentSequence.push('Shift');
        return;
    }

    // Only proceed if we're in the middle of a sequence
    if (currentSequence.length === 0 && !shiftPressed) {
        return;
    }

    // Add the current key to the sequence
    const key = event.key.toLowerCase();
    currentSequence.push(key);

    // Check if the sequence matches up to the current point
    for (let i = 0; i < currentSequence.length; i++) {
        if (currentSequence[i] !== ADMIN_KEY_SEQUENCE[i]) {
            // Reset if there's a mismatch
            currentSequence = [];
            shiftPressed = false;
            return;
        }
    }

    // Check if the full sequence is complete
    if (currentSequence.length === ADMIN_KEY_SEQUENCE.length) {
        const adminButtons = document.getElementById('adminButtons');
        if (adminButtons) {
            // Show the buttons with a slide down animation
            adminButtons.style.display = 'block';
            adminButtons.style.maxHeight = '0';
            adminButtons.style.overflow = 'hidden';
            adminButtons.style.transition = 'max-height 0.3s ease-in-out';
            requestAnimationFrame(() => {
                adminButtons.style.maxHeight = adminButtons.scrollHeight + 'px';
            });
        }
        // Reset the sequence
        currentSequence = [];
        shiftPressed = false;
    }
});

document.addEventListener('keyup', function(event) {
    // Reset shift state when shift is released
    if (event.key === 'Shift') {
        shiftPressed = false;
        if (currentSequence.length <= 1) {
            currentSequence = [];
        }
    }
});

// Event listeners for upload buttons
document.getElementById('uploadCategoriesButton').addEventListener('click', function() {
    document.getElementById('csvFileInput').click();
});

document.getElementById('csvFileInput').addEventListener('change', function(event) {
    var file = event.target.files[0];
    if (file) {
        var formData = new FormData();
        formData.append('csv_file', file);

        fetch('/upload_categories/', {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: formData
        }).then(response => {
            if (response.ok) {
                alert('File uploaded successfully');
                location.reload();
            } else {
                alert('An error occurred while uploading the file.');
            }
        }).catch(error => {
            console.error('Error:', error);
        });
    }
});

document.getElementById('uploadCostingsButton').addEventListener('click', function() {
    document.getElementById('costingCsvFileInput').click();
});

document.getElementById('costingCsvFileInput').addEventListener('change', function(event) {
    var file = event.target.files[0];
    if (file) {
        var formData = new FormData();
        formData.append('csv_file', file);

        fetch('/upload_costings/', {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: formData
        }).then(response => {
            if (!response.ok) {
                return response.text().then(text => {
                    console.error('Server error:', response.status, response.statusText, text);
                    throw new Error(`Server responded with ${response.status}: ${text}`);
                });
            }
            alert('File uploaded successfully');
            location.reload();
        }).catch(error => {
            console.error('Error:', error);
            alert('An error occurred while uploading the file. Details: ' + error.message);
        });
    }
});

document.getElementById('updateContractBudgetButton').addEventListener('click', function() {
    document.getElementById('updateContractBudgetCsvFileInput').click();
});

document.getElementById('updateContractBudgetCsvFileInput').addEventListener('change', function(event) {
    var file = event.target.files[0];
    if (file) {
        var formData = new FormData();
        formData.append('csv_file', file);

        fetch('/update_contract_budget_amounts/', {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: formData
        })
        .then(response => response.json().then(data => ({ status: response.status, body: data })))
        .then(({ status, body }) => {
            if (body.error) {
                alert('Error: ' + body.error);
                return;
            }
            
            let message = `File processed successfully.\n\nUpdated: ${body.updated} rows\nSkipped: ${body.skipped} rows`;
            
            if (body.skipped_rows && body.skipped_rows.length > 0) {
                message += '\n\nSkipped rows:';
                body.skipped_rows.forEach(row => {
                    message += `\n${row.category} - ${row.item}: ${row.reason}`;
                });
            }
            
            alert(message);
            location.reload();
        })
        .catch(error => {
            console.error('Error:', error);
            alert('Error processing file: ' + error.message);
        });
    }
});

// Helper function for fetching CSRF token
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// Event listeners for margin category and lines upload
document.getElementById('uploadMarginCategoryAndLinesButton').addEventListener('click', function() {
    document.getElementById('marginCategoryAndLinesCsvFileInput').click();
});

document.getElementById('marginCategoryAndLinesCsvFileInput').addEventListener('change', function(event) {
    var file = event.target.files[0];
    if (file) {
        var reader = new FileReader();
        reader.onload = function(e) {
            var csvData = e.target.result;
            var lines = csvData.split('\n');
            var headers = lines[0].split(',');
            var rows = [];
            
            // Process each line after headers
            for (var i = 1; i < lines.length; i++) {
                if (lines[i].trim() === '') continue; // Skip empty lines
                
                var currentLine = lines[i].split(',');
                console.log('CSV line:', currentLine);
                var row = {
                    category: currentLine[0],
                    item: currentLine[1],
                    xero_code: currentLine[2],
                    contract_budget: currentLine[3],
                    invoice_category: currentLine[4] // Now at index 4 with no empty column
                };
                rows.push(row);
            }

            // Get division from the page and convert to integer
            var division = parseInt(document.getElementById('division').value, 10);

            // Send the processed data to the server
            fetch('/upload_margin_category_and_lines/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken')
                },
                body: JSON.stringify({ 
                    rows: rows,
                    division: division
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    alert('Error: ' + data.error);
                    return;
                }
                alert('Margin categories and lines uploaded successfully');
                location.reload();
            })
            .catch(error => {
                console.error('Error:', error);
                alert('Error uploading margin categories and lines: ' + error.message);
            });
        };
        reader.readAsText(file);
    }
});
