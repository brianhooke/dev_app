document.addEventListener('DOMContentLoaded', function() {
    const totalRow = document.getElementById('totalRow');
    const tableContainer = totalRow.closest('div');

    // Function to update total row position
    function updateTotalRowPosition(immediate = false) {
        const tableRect = tableContainer.getBoundingClientRect();
        const viewportHeight = window.innerHeight;
        const tableBottom = tableRect.bottom;
        
        // Check if any category is expanded
        const expandedRows = document.querySelectorAll('tr.collapse.show');
        const isAnyExpanded = expandedRows.length > 0;

        if (isAnyExpanded && (tableBottom > viewportHeight || immediate)) {
            // Make the total row sticky at bottom immediately
            totalRow.style.position = 'sticky';
            totalRow.style.bottom = '0';
            totalRow.style.zIndex = '1';
            totalRow.style.backgroundColor = totalRow.style.background;
        } else {
            // Let it flow normally with the table
            totalRow.style.position = 'static';
            totalRow.style.bottom = 'auto';
            totalRow.style.zIndex = 'auto';
            totalRow.style.backgroundColor = '';
        }
    }

    // Update position when scrolling
    window.addEventListener('scroll', () => updateTotalRowPosition(false));
    
    // Update position when window is resized
    window.addEventListener('resize', () => updateTotalRowPosition(false));

    // Handle category expansions
    document.querySelectorAll('tr[data-toggle="collapse"]').forEach(row => {
        row.addEventListener('click', function() {
            // Immediately check if we need to make the total row sticky
            updateTotalRowPosition(true);
            // Check again after the animation completes
            setTimeout(() => updateTotalRowPosition(true), 350);
        });
    });

    // Initial position check
    updateTotalRowPosition(false);
});
