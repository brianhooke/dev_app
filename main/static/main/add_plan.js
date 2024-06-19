//respond to 'create category' button, popup input box & POST request
document.getElementById('saveCategoryButton').addEventListener('click', function() {
    var categoryName = document.getElementById('categoryName').value;
    var categoryType = document.getElementById('categoryType').value;
    // Check if a valid category type is selected
    if (categoryType === 'Select type of Category...') {
        alert('Error - select a category from the dropdown list.');
        return;
    }
    // Convert category type to number
    var categoryTypeNumber = categoryType === 'Plan' ? 1 : 2;
    fetch('/create_plan/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ plan: categoryName, categoryType: categoryTypeNumber }),
    })
    .then(response => response.json())
    .then(data => {
        console.log('Success:', data);
        location.reload(); // Refresh the page
    })
    .catch((error) => {
        console.error('Error:', error);
    });
});

//display pdfs of plans in iframe viewer
document.querySelectorAll('.plan').forEach(function(plan) {
    plan.addEventListener('click', function() {
        // Set the widths of rev-container and num-container to 50px
        var revContainer = document.querySelector('.rev-container');
        var numberContainer = document.querySelector('.number-container');
        revContainer.style.width = '50px';
        numberContainer.style.width = '50px'; // Move this line up here
        numberContainer.style.display = 'flex'; // Change this line to redisplay numberContainer with flex
        numberContainer.style.flexDirection = 'column'; // Add this line to restore the flex direction
        var planNumbers = this.dataset.planNumbers.split(',');
        var revNumbersStr = this.dataset.revNumbers.replace(/\\u0022/g, '"');
        var revNumbersDict = JSON.parse(revNumbersStr);
        numberContainer.innerHTML = '';
        planNumbers.forEach(function(number, index) {
            var numberBox = document.createElement('div');
            numberBox.className = 'number-box';
            numberBox.textContent = number;
            numberBox.style.cursor = 'pointer';
            numberBox.addEventListener('click', function() {
                // Get the last revision number for this plan number from the revNumbers dictionary
                var revNumbers = revNumbersDict[number];
                var lastRevNumber = revNumbers[revNumbers.length - 1];
                // Include the last revision number in the AJAX request URL
                var url = `/get_design_pdf_url/${plan.dataset.planId}/${number}/${lastRevNumber}`;
                console.log('URL:', url);
                fetch(url)
                    .then(response => response.json())
                    .then(data => {
                        // Set the src of the iframe to the returned file URL
                        var iframe = document.getElementById('pdfViewer');
                        var fileUrl = data.file_url.startsWith('media/') ? data.file_url.slice(6) : data.file_url;
                        iframe.src = fileUrl;
                        // Add revision numbers on the RHS of the iframe
                        var revNumbers = data.rev_numbers; // No need to split
                        console.log('Revision numbers:', revNumbers); // Log the revision numbers
                        // var revContainer = document.querySelector('.rev-container');
                        revContainer.innerHTML = '<p style="text-align: center;">Revision</p>';
                        revNumbers.forEach(function(revNumber) {
                            console.log('Adding revision number:', revNumber); // Log each revision number being added
                            var revBox = document.createElement('div');
                            revBox.className = 'number-box'; // Use the same class as the plan numbers
                            revBox.textContent = revNumber;
                            revBox.style.cursor = 'pointer';
                            revBox.addEventListener('click', function() {
                                highlightElements(numberBox, revBox); // Highlight both elements
                                var url = `/get_design_pdf_url/${plan.dataset.planId}/${number}/${revNumber}`;
                                console.log('URL:', url);
                                fetch(url)
                                    .then(response => response.json())
                                    .then(data => {
                                        // Handle the data from the response here
                                        var iframe = document.getElementById('pdfViewer');
                                        var fileUrl = data.file_url.startsWith('media/') ? data.file_url.slice(6) : data.file_url;
                                        iframe.src = fileUrl;
                                        console.log('File URL:', fileUrl); // Log the file URL
                                        console.log('Iframe src:', iframe.src); // Log the iframe src
                                    })
                                    .catch(error => {
                                        // Handle any errors here
                                        console.error('Error:', error);
                                    });
                            });
                            revContainer.appendChild(revBox);
                        });
                        // Highlight the last revBox for the clicked numberBox
                        var lastRevBox = revContainer.querySelectorAll('.number-box')[revNumbers.length - 1];
                        highlightElements(numberBox, lastRevBox);
                    });
            });
            numberContainer.appendChild(numberBox);
            // If this is the first plan number, make an AJAX request to display its PDF
            if (index === 0) {
                var url = `/get_design_pdf_url/${plan.dataset.planId}/${number}`;
                console.log('URL:', url);
                fetch(url)
                    .then(response => response.json())
                    .then(data => {
                        var iframe = document.getElementById('pdfViewer');
                        var fileUrl = data.file_url.startsWith('media/') ? data.file_url.slice(6) : data.file_url;
                        iframe.src = fileUrl;
                        // Add revision numbers on the RHS of the iframe
                        var revNumbers = data.rev_numbers; // No need to split
                        console.log('Revision numbers:', revNumbers); // Log the revision numbers
                        // var revContainer = document.querySelector('.rev-container');
                        revContainer.innerHTML = '<p style="text-align: center;">Revision</p>';
                        revNumbers.forEach(function(revNumber) {
                            console.log('Adding revision number:', revNumber); // Log each revision number being added
                            let revBox = document.createElement('div');
                            revBox.className = 'number-box'; // Use the same class as the plan numbers
                            revBox.textContent = revNumber;
                            revBox.style.cursor = 'pointer';
                            revBox.addEventListener('click', function() {
                                highlightElements(numberBox, revBox); // Highlight both elements
                                var url = `/get_design_pdf_url/${plan.dataset.planId}/${number}/${revNumber}`;
                                console.log('URL:', url);
                                fetch(url)
                                    .then(response => response.json())
                                    .then(data => {
                                        // Update the src of the iframe to the returned file URL
                                        var iframe = document.getElementById('pdfViewer');
                                        var fileUrl = data.file_url.startsWith('media/') ? data.file_url.slice(6) : data.file_url;
                                        iframe.src = fileUrl;
                                        console.log('File URL:', fileUrl); // Log the file URL
                                        console.log('Iframe src:', iframe.src); // Log the iframe src
                                    })
                                    .catch(error => {
                                        // Handle any errors here
                                        console.error('Error:', error);
                                    });
                            });
                            revContainer.appendChild(revBox);
                        });
                        // Highlight the first numberBox and corresponding revBox
                        var firstNumberBox = numberContainer.querySelector('.number-box');
                        var firstRevBox = revContainer.querySelector('.number-box');
                        highlightElements(firstNumberBox, firstRevBox);
                    });
            }
        });
    });
});

// Display pdf of reports in iframe
document.querySelectorAll('.report').forEach(function(report) {
    report.addEventListener('click', function() {
        var reportId = this.dataset.reportId;
        var url = `/get_report_pdf_url/${reportId}`;
        fetch(url)
            .then(response => {
                console.log('Response:', response);
                return response.json();
            })
            .then(data => {
                console.log('Data:', data); // Log the data
                var iframe = document.getElementById('pdfViewer');
                var revContainer = document.querySelector('.rev-container');
                var numContainer = document.querySelector('.number-container');
                revContainer.innerHTML = '';
                revContainer.style.width = '100px'; // Set the width of revContainer to 100px
                numContainer.style.display = 'none'; // Hide numContainer
                // Check if data is not empty
                if (data.data && data.data.length > 0) {
                    var firstReportBox = null;
                    data.data.forEach(function(reportData, index) {
                        var reportBox = document.createElement('div');
                        reportBox.className = 'number-box'; // Use the same class as the plan numbers
                        reportBox.textContent = reportData.report_reference;
                        reportBox.style.cursor = 'pointer';
                        reportBox.addEventListener('click', function() {
                            var reportRef = reportData.report_reference;
                            var url = `/get_report_pdf_url/${reportId}/${reportRef}`;
                            console.log('Report Reference:', reportRef); // Log the report reference
                            console.log('URL:', url);
                            fetch(url)
                                .then(response => {
                                    console.log('Response:', response); // Log the response
                                    return response.json();
                                    })
                                    .then(data => {
                                        console.log('Data:', data); // Log the data
                                        if (data.file_url) {
                                            var fileUrl2 = data.file_url.startsWith('media/') ? data.file_url.slice(6) : data.file_url;
                                            var iframe = document.getElementById('pdfViewer');
                                            iframe.src = fileUrl2;
                                            console.log('File URL2:', fileUrl2); // Log the file URL
                                            console.log('Iframe src2:', iframe.src); // Log the iframe src
                                        } else {
                                            console.error('No data returned from the server');
                                        }
                                    })
                                    .catch(error => {
                                        // Handle any errors here
                                        console.error('Error:', error);
                                    });
                                    highlightElements(null, reportBox); // Highlight the clicked reportBox
                                    });
                                    revContainer.appendChild(reportBox);
                                    
                                    // If it's the first reportBox, load the PDF and highlight it
                                    if (index === 0) {
                                        reportBox.click();
                                        firstReportBox = reportBox;
                                    }
                                    });
                                    // Highlight the first reportBox
                                    highlightElements(null, firstReportBox);
                                    } else {
                                        console.error('No data returned from the server');
                                    }
                                    })
                                    .catch(error => {
                                        // Handle any errors here
                                        console.error('Error:', error);
            });
        });
});
  
                

function highlightElements(numberBox, revBox) {
    // Remove highlight from previously highlighted elements
    document.querySelectorAll('.highlight').forEach(function(highlighted) {
        highlighted.style.backgroundColor = ''; // Reset the background color
        highlighted.classList.remove('highlight');
    });
    // Add highlight to the current elements
    if (numberBox) {
        numberBox.classList.add('highlight');
        numberBox.style.backgroundColor = 'yellow'; // Set the background color for highlighting
    }
    if (revBox) {
        revBox.classList.add('highlight');
        revBox.style.backgroundColor = 'yellow'; // Set the background color for highlighting
    }
}


//upload pdf
// document.addEventListener('DOMContentLoaded', function() {
//     var inputElements = document.querySelectorAll('input[type="file"]');
//     inputElements.forEach(function(inputElement) {
//         inputElement.addEventListener('change', function(e) {
//             console.log('File selected');
//             var file = e.target.files[0];
//             console.log(`Selected file: ${file.name}, type: ${file.type}`);
//             var planId = e.target.id.replace('fileUpload', '');

//             if (file.type != "application/pdf") {
//                 console.error(file.name, "is not a pdf file.")
//                 return
//             }

//             var formData = new FormData();
//             formData.append('file', file);
//             formData.append('plan_id', planId);

//             fetch('/save_pdf/', {
//                 method: 'POST',
//                 body: formData,
//             })
//             .then(response => {
//                 if (!response.ok) {
//                     throw new Error('Network response was not ok');
//                 }
//                 return response.json();
//             })
//             .then(data => {
//                 console.log('Success:', data);
//             })
//             .catch((error) => {
//                 console.error('Error:', error);
//             });
//         });
//     });
// });

// PDF Upload and Navigation Handler
document.addEventListener('DOMContentLoaded', function() {
    pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://unpkg.com/pdfjs-dist@2.6.347/build/pdf.worker.js';
    var uploadBtn = document.getElementById('uploadbtn');
    var fileInput = document.createElement('input');
    fileInput.type = 'file';
    fileInput.accept = '.pdf';
    fileInput.style.display = 'none';
    document.body.appendChild(fileInput);
    var pdf = null;
    var pageNum = 1;
    var renderTask = null;
    var pageValues = {};
    function renderPage(num) {
        console.log(`Rendering page number: ${num}`);
        pdf.getPage(num).then(function(page) {
            var scale = 1.5;
            var viewport = page.getViewport({ scale: scale });

            var canvas = document.getElementById('pdfModalViewer');
            var context = canvas.getContext('2d');
            canvas.height = viewport.height;
            canvas.width = viewport.width;

            if (renderTask) {
                renderTask.cancel();
            }

            var renderContext = {
                canvasContext: context,
                viewport: viewport
            };
            renderTask = page.render(renderContext);
            renderTask.promise.then(function() {
                $('#pdfUploadModal').modal('show'); // Show the new modal
            });
        });
    }
    var revValues = {};
    document.getElementById('prevPage').addEventListener('click', function() {
        if (pageNum <= 1) {
            return;
        }
        pageValues[pageNum] = document.getElementById('pdfName').value;
        revValues[pageNum] = document.getElementById('revNum').value;
        document.getElementById('pdfName').value = pageValues[pageNum - 1] || '';
        document.getElementById('revNum').value = revValues[pageNum - 1] || '';
        pageNum--;
        renderPage(pageNum);
    });
    document.getElementById('nextPage').addEventListener('click', function() {
        if (pageNum >= pdf.numPages) {
            return;
        }
        pageValues[pageNum] = document.getElementById('pdfName').value;
        revValues[pageNum] = document.getElementById('revNum').value;
        document.getElementById('pdfName').value = pageValues[pageNum + 1] || '';
        document.getElementById('revNum').value = revValues[pageNum + 1] || '';
        pageNum++;
        renderPage(pageNum);
    });
    uploadBtn.addEventListener('click', function() {
        fileInput.click();
    });
    fileInput.addEventListener('change', function(e) {
        console.log("File input change event triggered");
        if (e.target.files.length == 0) {
            return;
        }
        var file = e.target.files[0];
        if (file.type != "application/pdf") {
            console.error(file.name, "is not a pdf file.")
            return;
        }
        var reader = new FileReader();
        reader.onload = function(e) {
            var blob = new Blob([new Uint8Array(this.result)], { type: "application/pdf" });
            var url = URL.createObjectURL(blob);
            // Load the PDF file using PDF.js
            pdfjsLib.getDocument(url).promise.then(function(_pdf) {
                pdf = _pdf;
                console.log(`PDF loaded, number of pages: ${pdf.numPages}`);
                document.getElementById('pdfName').value = '';
                document.getElementById('revNum').value = '';
                renderPage(pageNum);
            });
        };
        reader.readAsArrayBuffer(file);
    });
    document.getElementById('uploadPDFButton').addEventListener('click', function() {
        pageValues[pageNum] = document.getElementById('pdfName').value;
        revValues[pageNum] = document.getElementById('revNum').value;
        console.log('pageValues:', pageValues);
        console.log('revValues:', revValues);
        // Check for duplicate pageValues
        var pageValuesArr = Object.values(pageValues);
        var hasDuplicates = pageValuesArr.some((val, i) => pageValuesArr.indexOf(val) !== i);
        if (hasDuplicates) {
            alert("Error - Multiple plans have the same plan number");
            return;
        }
        // Check if user has selected a Category
        var categorySelect = document.getElementById('categorySelect');
        var selectedCategory = categorySelect.value;
        console.log("Category selected: " + selectedCategory);
        if (!selectedCategory || selectedCategory === "Select...") {
            alert("Error - select a category from the dropdown list.");
            return;
        }
        // Check for pairs with one value missing
        var hasIncompletePairs = Object.keys(pageValues).some((key) => {
            return (pageValues[key] && !revValues[key]) || (!pageValues[key] && revValues[key]);
        });
        if (hasIncompletePairs) {
            alert("Error - One or more plans have a Plan # but not a Revision # (or visa versa). Either complete the missing info or delete the plan/rev # to ignore that plan.");
            return;
        }
        // Check for pairs with both values missing
        var hasEmptyPairs = Object.keys(pageValues).some((key) => {
            return !pageValues[key] && !revValues[key];
        });
        if (hasEmptyPairs) {
            var proceed = confirm("Some plans are not labelled and will be ignored. Do you want to proceed anyway?");
            if (!proceed) {
                return;
            }
        }
        var pdfFile = fileInput.files[0];
        var categorySelect = document.getElementById('categorySelect');
        var selectedCategory = categorySelect.value;
        // Collect the data
        var data = {
            pdfFile: pdfFile,
            categorySelect: selectedCategory,
            pdfNameValues: pageValues,
            revNumValues: revValues,
        };
        console.log('Data to be sent:', data);
        // Use the function
        postData('/upload_design_pdf/', data)
            .then(data => console.log(data))
            .catch((error) => console.error('Error:', error));
    });
    function postData(url = '', data = {}) {
        var formData = new FormData();
        formData.append('pdfFile', data.pdfFile);
        formData.append('categorySelect', data.categorySelect);
        formData.append('pdfNameValues', JSON.stringify(data.pdfNameValues));
        formData.append('revNumValues', JSON.stringify(data.revNumValues));
    
        return fetch(url, {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            console.log(data);
            if (data.status === 'success') { // Check if the server returned a success message
                $('#pdfUploadModal').modal('hide'); // Close the modal
                // location.reload(); // Refresh the page
            }
        })
        .catch((error) => console.error('Error:', error));
    }
});

// Report Upload and Navigation Handler
document.addEventListener('DOMContentLoaded', function() {
    pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://unpkg.com/pdfjs-dist@2.6.347/build/pdf.worker.js';
    var uploadReportBtn = document.getElementById('uploadReportBtn');
    var fileInput = document.createElement('input');
    fileInput.type = 'file';
    fileInput.accept = '.pdf';
    fileInput.style.display = 'none';
    document.body.appendChild(fileInput);
    var pdf = null;
    var pageNum = 1;
    var renderTask = null;
    function renderPage(num) {
        console.log(`Rendering page number: ${num}`);
        pdf.getPage(num).then(function(page) {
            var scale = 1.5;
            var viewport = page.getViewport({ scale: scale });
            var canvas = document.getElementById('reportModalViewer');
            var context = canvas.getContext('2d');
            canvas.height = viewport.height;
            canvas.width = viewport.width;
            if (renderTask) {
                renderTask.cancel();
            }
            var renderContext = {
                canvasContext: context,
                viewport: viewport
            };
            renderTask = page.render(renderContext);
            renderTask.promise.then(function() {
                $('#reportsUploadModal').modal('show'); // Show the new modal
            });
        });
    }
    document.getElementById('reportPrevPage').addEventListener('click', function() {
        if (pageNum <= 1) {
            return;
        }
        pageNum--;
        renderPage(pageNum);
    });
    document.getElementById('reportNextPage').addEventListener('click', function() {
        if (pageNum >= pdf.numPages) {
            return;
        }
        pageNum++;
        renderPage(pageNum);
    });
    uploadReportBtn.addEventListener('click', function() {
        fileInput.click();
    });
    fileInput.addEventListener('change', function(e) {
        console.log("File input change event triggered");
        if (e.target.files.length == 0) {
            return;
        }
        var file = e.target.files[0];
        if (file.type != "application/pdf") {
            console.error(file.name, "is not a pdf file.")
            return;
        }
        var reader = new FileReader();
        reader.onload = function(e) {
            var blob = new Blob([new Uint8Array(this.result)], { type: "application/pdf" });
            var url = URL.createObjectURL(blob);
            // Load the PDF file using PDF.js
            pdfjsLib.getDocument(url).promise.then(function(_pdf) {
                pdf = _pdf;
                document.getElementById('reportPdfName').value = '';
                renderPage(pageNum);
            });
        };
        reader.readAsArrayBuffer(file);
    });
    document.getElementById('uploadReportButton').addEventListener('click', function() {
        var pdfNameValue = document.getElementById('reportPdfName').value;
        // Check if user has selected a Category
        var categorySelect = document.getElementById('reportCategorySelect');
        var selectedCategory = categorySelect.value;
        console.log("Category selected: " + selectedCategory);
        var pdfFile = fileInput.files[0];
    
        // Check if a category is selected
        if (!selectedCategory) {
            alert("Error - select a category from the dropdown list");
            return;
        }
    
        // Check if a page number is set
        if (!pageNum || pageNum < 1) {
            alert("Error - report needs a name");
            return;
        }
    
        // Collect the data
        var data = {
            pdfFile: pdfFile,
            categorySelect: selectedCategory,
            pdfNameValue: pdfNameValue,
        };
        console.log('Data to be sent:', data);
        // Use the function
        postData('/upload_report_pdf/', data)
            .then(data => console.log(data))
            .catch((error) => console.error('Error:', error));
    });
    function postData(url = '', data = {}) {
        var formData = new FormData();
        formData.append('pdfFile', data.pdfFile);
        formData.append('categorySelect', data.categorySelect);
        formData.append('pdfNameValue', data.pdfNameValue);    
        return fetch(url, {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            console.log(data);
            if (data.status === 'success') { // Check if the server returned a success message
                $('#reportsUploadModal').modal('hide'); // Close the modal
                // location.reload(); // Refresh the page
            }
        })
        .catch((error) => console.error('Error:', error));
    }
});