/**
 * Documents Management Module
 * Handles folder structure and file management for projects
 */

var DocumentsManager = (function() {
    'use strict';
    
    // Private variables
    var projectPk = null;
    var folders = [];
    var currentFolderId = null;
    var currentFileId = null;
    var selectedFolderId = null;
    
    /**
     * Initialize the documents manager
     */
    function init(options) {
        projectPk = options.projectPk;
        
        if (!projectPk) {
            console.error('Project PK is required for Documents Manager');
            return;
        }
        
        console.log('DocumentsManager initializing for project:', projectPk);
        
        // Wait for DOM to be ready
        setTimeout(function() {
            // Move modals to body level so Bootstrap can display them properly
            // They're currently nested in #tenderContentArea which breaks modal display
            if ($('#newFolderModal').length && !$('body > #newFolderModal').length) {
                console.log('Moving modals to body level...');
                var newFolderModal = $('#newFolderModal').detach();
                var renameFolderModal = $('#renameFolderModal').detach();
                $('body').append(newFolderModal);
                $('body').append(renameFolderModal);
                
                // Ensure modals are properly initialized
                newFolderModal.css('z-index', 1055);
                renameFolderModal.css('z-index', 1055);
                
                console.log('Modals moved to body with z-index:', newFolderModal.css('z-index'));
            }
            
            // Load folders and files
            loadFolderStructure();
            
            // Attach event handlers
            attachEventHandlers();
            
            console.log('DocumentsManager initialized');
        }, 100);
    }
    
    /**
     * Attach all event handlers
     */
    function attachEventHandlers() {
        console.log('Attaching event handlers...');
        
        // Check if button exists
        var newFolderBtn = $('#newFolderBtn');
        console.log('Found #newFolderBtn:', newFolderBtn.length > 0);
        console.log('Button element:', newFolderBtn[0]);
        
        // Use event delegation from tenderContentArea to handle dynamically loaded content
        // New Folder button
        $(document).off('click', '#newFolderBtn').on('click', '#newFolderBtn', function(e) {
            e.preventDefault();
            e.stopPropagation();
            console.log('New Folder button clicked');
            showNewFolderModal();
        });
        
        // Create Folder button in modal
        $(document).off('click', '#createFolderBtn').on('click', '#createFolderBtn', function() {
            createFolder();
        });
        
        // Upload File button
        $(document).off('click', '#uploadFileBtn').on('click', '#uploadFileBtn', function() {
            if (!selectedFolderId) {
                alert('Please select a folder first');
                return;
            }
            $('#fileUploadInput').click();
        });
        
        // File input change - use direct binding since it's a file input
        $(document).off('change', '#fileUploadInput').on('change', '#fileUploadInput', function(e) {
            uploadFiles(e.target.files);
        });
        
        // Download file button
        $(document).off('click', '#downloadFileBtn').on('click', '#downloadFileBtn', function() {
            if (currentFileId) {
                downloadFile(currentFileId);
            }
        });
        
        // Delete file button
        $(document).off('click', '#deleteFileBtn').on('click', '#deleteFileBtn', function() {
            if (currentFileId) {
                deleteFile(currentFileId);
            }
        });
        
        // Rename folder button
        $(document).off('click', '#renameFolderBtn').on('click', '#renameFolderBtn', function() {
            renameFolder();
        });
        
        // Allow Enter key in folder name inputs
        $(document).off('keypress', '#newFolderName').on('keypress', '#newFolderName', function(e) {
            if (e.which === 13) {
                createFolder();
            }
        });
        
        $(document).off('keypress', '#renameFolderName').on('keypress', '#renameFolderName', function(e) {
            if (e.which === 13) {
                renameFolder();
            }
        });
        
        console.log('All event handlers attached with delegation');
    }
    
    /**
     * Load folder structure from backend
     */
    function loadFolderStructure() {
        console.log('Loading folder structure for project:', projectPk);
        $.ajax({
            url: '/core/get_project_folders/' + projectPk + '/',
            type: 'GET',
            success: function(response) {
                console.log('Folder structure response:', response);
                if (response.status === 'success') {
                    folders = response.folders || [];
                    console.log('Loaded folders count:', folders.length);
                    console.log('Folders data:', folders);
                    renderFolderTree();
                } else {
                    console.error('Error loading folders:', response.message);
                }
            },
            error: function(xhr, status, error) {
                console.error('AJAX error loading folders:', error);
                console.error('Response:', xhr.responseText);
            }
        });
    }
    
    /**
     * Render the folder tree
     */
    function renderFolderTree() {
        console.log('renderFolderTree called with', folders.length, 'folders');
        
        // CRITICAL: Target the #folderTree that's in #tenderContentArea, not template storage
        var treeContainer = $('#tenderContentArea #folderTree');
        console.log('Found #folderTree container in tenderContentArea:', treeContainer.length > 0);
        console.log('#folderTree is visible:', treeContainer.is(':visible'));
        console.log('#folderTree parent:', treeContainer.parent().attr('id'));
        console.log('#folderTree parent is visible:', treeContainer.parent().is(':visible'));
        console.log('#folderTree CSS display:', treeContainer.css('display'));
        console.log('#folderTree CSS visibility:', treeContainer.css('visibility'));
        
        // CRITICAL FIX: Ensure containers are visible
        // Need to force display with CSS, not just .show()
        $('#tenderContentArea #documentsContainer').css('display', 'flex');
        $('#tenderContentArea #folderTreeContainer').css('display', 'block');
        treeContainer.css('display', 'block');
        
        // Also ensure all parents are visible (but NOT the template storage!)
        treeContainer.parents().each(function() {
            var parentId = $(this).attr('id');
            // Skip the template storage divs
            if (parentId === 'documentsTemplateStorage' || parentId === 'itemsTemplateStorage') {
                console.log('Skipping template storage:', parentId);
                return; // Continue to next parent
            }
            if ($(this).css('display') === 'none') {
                console.log('Found hidden parent:', parentId || $(this)[0].tagName);
                $(this).css('display', 'block');
            }
        });
        
        console.log('Forced containers to show. #folderTree is now visible:', treeContainer.is(':visible'));
        
        treeContainer.empty();
        
        if (folders.length === 0) {
            console.log('No folders to render, showing empty state');
            treeContainer.html(`
                <div style="text-align: center; padding: 40px; color: #6c757d;">
                    <i class="fa fa-folder-open" style="font-size: 48px; margin-bottom: 15px;"></i>
                    <p>No folders yet. Click "New Folder" to create one.</p>
                </div>
            `);
            return;
        }
        
        // Build tree structure (root folders first)
        var rootFolders = folders.filter(f => !f.parent_folder_id);
        console.log('Root folders count:', rootFolders.length);
        rootFolders.forEach(function(folder) {
            console.log('Rendering folder:', folder.folder_name);
            renderFolder(folder, treeContainer, 0);
        });
    }
    
    /**
     * Recursively render a folder and its children
     */
    function renderFolder(folder, container, level) {
        console.log('renderFolder called for:', folder.folder_name, 'at level:', level);
        console.log('Container:', container);
        
        var folderDiv = $('<div></div>')
            .addClass('folder-item')
            .attr('data-folder-id', folder.folder_pk)
            .css('margin-left', (level * 20) + 'px');
        
        console.log('Created folder div:', folderDiv);
        
        if (selectedFolderId === folder.folder_pk) {
            folderDiv.addClass('selected');
        }
        
        // Folder icon and name
        var folderIcon = $('<i></i>').addClass('fa fa-folder folder-icon');
        var folderName = $('<span></span>').text(folder.folder_name);
        
        // Action buttons
        var actionsDiv = $('<div></div>').addClass('folder-actions');
        
        var renameBtn = $('<button></button>')
            .addClass('btn btn-xs btn-warning')
            .html('<i class="fa fa-edit"></i>')
            .attr('title', 'Rename folder')
            .on('click', function(e) {
                e.stopPropagation();
                showRenameFolderModal(folder);
            });
        
        var deleteBtn = $('<button></button>')
            .addClass('btn btn-xs btn-danger')
            .html('<i class="fa fa-trash"></i>')
            .attr('title', 'Delete folder')
            .on('click', function(e) {
                e.stopPropagation();
                deleteFolderPrompt(folder.folder_pk);
            });
        
        actionsDiv.append(renameBtn).append(deleteBtn);
        
        folderDiv.append(folderIcon).append(folderName).append(actionsDiv);
        
        // Click handler to select folder and load files
        folderDiv.on('click', function(e) {
            if ($(e.target).closest('.folder-actions').length === 0) {
                selectFolder(folder.folder_pk);
            }
        });
        
        console.log('Appending folder div to container...');
        container.append(folderDiv);
        console.log('Folder div appended. Container children count:', container.children().length);
        
        // Render files in this folder
        if (folder.files && folder.files.length > 0) {
            console.log('Rendering', folder.files.length, 'files in folder');
            var filesContainer = $('<div></div>')
                .addClass('folder-children')
                .css('margin-left', ((level + 1) * 20) + 'px');
            
            folder.files.forEach(function(file) {
                renderFile(file, filesContainer);
            });
            
            container.append(filesContainer);
        }
        
        // Render subfolders
        var subfolders = folders.filter(f => f.parent_folder_id === folder.folder_pk);
        console.log('Found', subfolders.length, 'subfolders');
        subfolders.forEach(function(subfolder) {
            renderFolder(subfolder, container, level + 1);
        });
    }
    
    /**
     * Render a file item
     */
    function renderFile(file, container) {
        var fileDiv = $('<div></div>')
            .addClass('file-item')
            .attr('data-file-id', file.file_pk);
        
        if (currentFileId === file.file_pk) {
            fileDiv.addClass('selected');
        }
        
        // File icon based on type
        var icon = 'fa-file';
        if (file.file_type === 'pdf') {
            icon = 'fa-file-pdf text-danger';
        } else if (['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp'].includes(file.file_type)) {
            icon = 'fa-file-image text-primary';
        }
        
        var fileIcon = $('<i></i>').addClass('fa ' + icon + ' file-icon');
        var fileName = $('<span></span>').text(file.file_name);
        var fileSize = $('<span></span>')
            .addClass('file-size')
            .text(formatFileSize(file.file_size));
        
        fileDiv.append(fileIcon).append(fileName).append(fileSize);
        
        // Click handler to view file
        fileDiv.on('click', function() {
            console.log('File clicked:', file.file_name);
            viewFile(file);
        });
        
        console.log('Rendered file item:', file.file_name);
        container.append(fileDiv);
    }
    
    /**
     * Select a folder
     */
    function selectFolder(folderId) {
        selectedFolderId = folderId;
        $('.folder-item').removeClass('selected');
        $('.folder-item[data-folder-id="' + folderId + '"]').addClass('selected');
        console.log('Selected folder:', folderId);
    }
    
    /**
     * Show new folder modal
     */
    function showNewFolderModal() {
        console.log('showNewFolderModal called');
        
        // Get the modal and ensure we're using the one at body level
        var modal = $('#newFolderModal');
        console.log('Found #newFolderModal count:', modal.length);
        
        // CRITICAL: Move modal to body if it's not already there
        // This needs to happen every time because template reloads reset the position
        if (modal.parent()[0].tagName !== 'BODY') {
            console.log('Modal not at body level, moving now...');
            modal.detach().appendTo('body');
            console.log('Modal parent AFTER move:', modal.parent()[0].tagName);
        }
        
        // Now work with the modal that's at body level
        modal = $('#newFolderModal');
        var folderNameInput = modal.find('#newFolderName');
        var parentSelect = modal.find('#parentFolderSelect');
        
        console.log('Using modal at:', modal.parent()[0].tagName);
        console.log('Found input in modal:', folderNameInput.length > 0);
        
        // Clear the input
        folderNameInput.val('');
        
        // Populate parent folder dropdown
        console.log('Found #parentFolderSelect:', parentSelect.length > 0);
        parentSelect.empty();
        parentSelect.append('<option value="">Root (No parent)</option>');
        
        folders.forEach(function(folder) {
            var indent = '';
            // Calculate indent based on parent hierarchy
            var level = getFolderLevel(folder.folder_pk);
            for (var i = 0; i < level; i++) {
                indent += '-- ';
            }
            parentSelect.append(
                '<option value="' + folder.folder_pk + '">' + indent + folder.folder_name + '</option>'
            );
        });
        
        // Pre-select current folder if one is selected
        if (selectedFolderId) {
            parentSelect.val(selectedFolderId);
        }
        
        console.log('Showing modal...');
        
        // First hide any existing modals
        $('.modal').modal('hide');
        $('.modal-backdrop').remove();
        
        // Small delay to ensure clean state
        setTimeout(function() {
            // Show modal with proper options
            modal.modal({
                backdrop: true,
                keyboard: true,
                focus: true,
                show: true
            });
            
            // Force z-index after modal is shown
            setTimeout(function() {
                // Use attr to set inline style with !important
                modal.attr('style', 'z-index: 1055 !important; display: block;');
                
                var backdrop = $('.modal-backdrop');
                backdrop.each(function() {
                    $(this).attr('style', 'z-index: 1050 !important;');
                });
                
                console.log('Modal shown with z-index:', modal.css('z-index'));
                console.log('Backdrop count:', backdrop.length);
                console.log('Backdrop z-index:', backdrop.css('z-index'));
                
                // Focus on the first input
                $('#newFolderName').focus();
            }, 50);
        }, 50);
    }
    
    /**
     * Get folder nesting level
     */
    function getFolderLevel(folderId, level = 0) {
        var folder = folders.find(f => f.folder_pk === folderId);
        if (!folder || !folder.parent_folder_id) {
            return level;
        }
        return getFolderLevel(folder.parent_folder_id, level + 1);
    }
    
    /**
     * Create a new folder
     */
    function createFolder() {
        console.log('createFolder called');
        
        // Get inputs from the modal that's at body level
        var modal = $('#newFolderModal');
        var folderNameInput = modal.find('#newFolderName');
        var parentFolderSelect = modal.find('#parentFolderSelect');
        
        console.log('Found modal:', modal.length > 0);
        console.log('Modal parent:', modal.parent()[0].tagName);
        console.log('Found #newFolderName input in modal:', folderNameInput.length > 0);
        console.log('Input value RAW:', folderNameInput.val());
        
        var folderName = folderNameInput.val().trim();
        console.log('Input value TRIMMED:', folderName);
        console.log('Folder name length:', folderName.length);
        
        var parentFolderId = parentFolderSelect.val() || null;
        console.log('Parent folder ID:', parentFolderId);
        
        if (!folderName) {
            alert('Please enter a folder name');
            return;
        }
        
        console.log('Sending AJAX request to create folder...');
        
        $.ajax({
            url: '/core/create_folder/',
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({
                project_pk: projectPk,
                folder_name: folderName,
                parent_folder_id: parentFolderId
            }),
            success: function(response) {
                if (response.status === 'success') {
                    $('#newFolderModal').modal('hide');
                    loadFolderStructure();
                } else {
                    alert('Error creating folder: ' + response.message);
                }
            },
            error: function(xhr, status, error) {
                console.error('Error creating folder:', error);
                alert('Error creating folder. Please try again.');
            }
        });
    }
    
    /**
     * Show rename folder modal
     */
    function showRenameFolderModal(folder) {
        currentFolderId = folder.folder_pk;
        $('#renameFolderName').val(folder.folder_name);
        
        var modal = $('#renameFolderModal');
        
        // Move modal to body if it's not already there
        if (modal.parent()[0].tagName !== 'BODY') {
            modal.detach().appendTo('body');
        }
        
        // Clear any existing modals
        $('.modal').modal('hide');
        $('.modal-backdrop').remove();
        
        setTimeout(function() {
            modal.modal({
                backdrop: true,
                keyboard: true,
                focus: true,
                show: true
            });
            
            // Force z-index
            setTimeout(function() {
                modal.attr('style', 'z-index: 1055 !important; display: block;');
                $('.modal-backdrop').each(function() {
                    $(this).attr('style', 'z-index: 1050 !important;');
                });
                $('#renameFolderName').focus();
            }, 50);
        }, 50);
    }
    
    /**
     * Rename a folder
     */
    function renameFolder() {
        var newName = $('#renameFolderName').val().trim();
        
        if (!newName) {
            alert('Please enter a folder name');
            return;
        }
        
        $.ajax({
            url: '/core/rename_folder/',
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({
                folder_pk: currentFolderId,
                new_name: newName
            }),
            success: function(response) {
                if (response.status === 'success') {
                    $('#renameFolderModal').modal('hide');
                    loadFolderStructure();
                } else {
                    alert('Error renaming folder: ' + response.message);
                }
            },
            error: function(xhr, status, error) {
                console.error('Error renaming folder:', error);
                alert('Error renaming folder. Please try again.');
            }
        });
    }
    
    /**
     * Delete folder prompt
     */
    function deleteFolderPrompt(folderId) {
        var folder = folders.find(f => f.folder_pk === folderId);
        if (!folder) return;
        
        var hasFiles = folder.files && folder.files.length > 0;
        var hasSubfolders = folders.some(f => f.parent_folder_id === folderId);
        
        var message = 'Are you sure you want to delete "' + folder.folder_name + '"?';
        if (hasFiles || hasSubfolders) {
            message += '\n\nThis will also delete all files and subfolders inside it.';
        }
        
        if (confirm(message)) {
            deleteFolder(folderId);
        }
    }
    
    /**
     * Delete a folder
     */
    function deleteFolder(folderId) {
        $.ajax({
            url: '/core/delete_folder/',
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({
                folder_pk: folderId
            }),
            success: function(response) {
                if (response.status === 'success') {
                    if (selectedFolderId === folderId) {
                        selectedFolderId = null;
                    }
                    loadFolderStructure();
                    clearFileViewer();
                } else {
                    alert('Error deleting folder: ' + response.message);
                }
            },
            error: function(xhr, status, error) {
                console.error('Error deleting folder:', error);
                alert('Error deleting folder. Please try again.');
            }
        });
    }
    
    /**
     * Upload files to selected folder
     */
    function uploadFiles(files) {
        if (!files || files.length === 0) return;
        if (!selectedFolderId) {
            alert('Please select a folder first');
            return;
        }
        
        var formData = new FormData();
        formData.append('folder_pk', selectedFolderId);
        
        for (var i = 0; i < files.length; i++) {
            formData.append('files', files[i]);
        }
        
        $.ajax({
            url: '/core/upload_files/',
            type: 'POST',
            data: formData,
            processData: false,
            contentType: false,
            success: function(response) {
                if (response.status === 'success') {
                    loadFolderStructure();
                    $('#fileUploadInput').val(''); // Clear input
                } else {
                    alert('Error uploading files: ' + response.message);
                }
            },
            error: function(xhr, status, error) {
                console.error('Error uploading files:', error);
                alert('Error uploading files. Please try again.');
            }
        });
    }
    
    /**
     * View a file
     */
    function viewFile(file) {
        console.log('viewFile called for:', file.file_name);
        console.log('File type:', file.file_type);
        console.log('File URL:', file.file_url);
        
        currentFileId = file.file_pk;
        $('.file-item').removeClass('selected');
        $('.file-item[data-file-id="' + file.file_pk + '"]').addClass('selected');
        
        // Update file info bar - target within tenderContentArea
        var fileInfoBar = $('#tenderContentArea #fileInfoBar');
        var currentFileName = $('#tenderContentArea #currentFileName');
        var currentFileInfo = $('#tenderContentArea #currentFileInfo');
        
        console.log('Found fileInfoBar:', fileInfoBar.length > 0);
        console.log('Found currentFileName:', currentFileName.length > 0);
        
        currentFileName.text(file.file_name);
        currentFileInfo.html(
            'Type: ' + file.file_type.toUpperCase() + ' | ' +
            'Size: ' + formatFileSize(file.file_size) + ' | ' +
            'Uploaded: ' + formatDate(file.uploaded_at)
        );
        fileInfoBar.show();
        
        // Clear viewer - target within tenderContentArea
        var viewer = $('#tenderContentArea #fileViewer');
        console.log('Found fileViewer:', viewer.length > 0);
        viewer.empty();
        
        // Render based on file type
        if (file.file_type === 'pdf') {
            viewer.html('<iframe src="' + file.file_url + '" style="width: 100%; height: 100%; border: none;"></iframe>');
        } else if (['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'svg'].includes(file.file_type)) {
            viewer.html('<img src="' + file.file_url + '" style="max-width: 100%; max-height: 100%; object-fit: contain;">');
        } else {
            viewer.html(`
                <div style="text-align: center; color: #6c757d; padding: 40px;">
                    <i class="fa fa-file" style="font-size: 64px; margin-bottom: 20px;"></i>
                    <p>File type not supported for preview</p>
                    <p style="font-size: 12px;">Click "Download" to view this file</p>
                </div>
            `);
        }
    }
    
    /**
     * Download a file
     */
    function downloadFile(fileId) {
        window.open('/core/download_file/' + fileId + '/', '_blank');
    }
    
    /**
     * Delete a file
     */
    function deleteFile(fileId) {
        if (!confirm('Are you sure you want to delete this file?')) {
            return;
        }
        
        $.ajax({
            url: '/core/delete_file/',
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({
                file_pk: fileId
            }),
            success: function(response) {
                if (response.status === 'success') {
                    clearFileViewer();
                    loadFolderStructure();
                } else {
                    alert('Error deleting file: ' + response.message);
                }
            },
            error: function(xhr, status, error) {
                console.error('Error deleting file:', error);
                alert('Error deleting file. Please try again.');
            }
        });
    }
    
    /**
     * Clear file viewer
     */
    function clearFileViewer() {
        currentFileId = null;
        $('#fileInfoBar').hide();
        $('#fileViewer').html(`
            <div style="text-align: center; color: #6c757d;">
                <i class="fa fa-file" style="font-size: 64px; margin-bottom: 20px;"></i>
                <p>Select a file to view</p>
            </div>
        `);
        $('.file-item').removeClass('selected');
    }
    
    /**
     * Format file size for display
     */
    function formatFileSize(bytes) {
        if (!bytes) return '0 B';
        var k = 1024;
        var sizes = ['B', 'KB', 'MB', 'GB'];
        var i = Math.floor(Math.log(bytes) / Math.log(k));
        return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i];
    }
    
    /**
     * Format date for display
     */
    function formatDate(dateString) {
        var date = new Date(dateString);
        return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
    }
    
    /**
     * Emergency function to clear stuck modal backdrops
     * Call DocumentsManager.clearModals() from console if stuck
     */
    function clearModals() {
        console.log('Clearing all modals and backdrops...');
        $('.modal').modal('hide');
        $('.modal-backdrop').remove();
        $('body').removeClass('modal-open');
        $('body').css('padding-right', '');
        console.log('Modals cleared');
    }
    
    // Public API
    return {
        init: init,
        reload: loadFolderStructure,
        clearModals: clearModals  // Emergency escape function
    };
})();

// Make available globally
window.DocumentsManager = DocumentsManager;
