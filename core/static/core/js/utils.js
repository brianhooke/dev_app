/**
 * Shared utility functions for the dev_app frontend.
 * 
 * This file consolidates commonly duplicated functions across JS files.
 * Import this file BEFORE other JS files that depend on these utilities.
 * 
 * Functions provided:
 * - getCookie(name) - Get cookie value by name (for CSRF tokens)
 * - formatNumber(num) - Format number with commas and 2 decimal places (en-US)
 * - formatMoney(num) - Format number as currency with thousand separators (en-AU)
 * - formatCurrency(amount) - Format as currency with $ symbol
 * - parseFloatSafe(value) - Parse float, returning 0 for invalid values
 * - escapeHtml(text) - Escape HTML special characters to prevent XSS
 * - getProjectPkFromUrl() - Extract project PK from URL path
 * - isConstructionProject(sectionId) - Check if section is in construction mode
 * - applyColumnStyles(sectionId, widths, options) - Apply column width CSS to table
 * - recalculateFooterTotals(sectionId, columnMappings) - Recalculate footer totals from row values
 * - formatQty(num) - Format number as quantity (no decimals, with thousand separators)
 */

/**
 * Get cookie value by name.
 * Used primarily for CSRF token retrieval.
 * 
 * @param {string} name - Cookie name
 * @returns {string|null} Cookie value or null if not found
 */
function getCookie(name) {
    var cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        var cookies = document.cookie.split(';');
        for (var i = 0; i < cookies.length; i++) {
            var cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// D.F-C-06: every money formatter on the page uses the AUSTRALIAN locale.
// Previously `formatNumber` defaulted to `en-US`, while `formatMoney`
// defaulted to `en-AU`, and `formatCurrency` used `formatNumber` (US)
// then prepended a `$`. The same screen could show inconsistent
// thousand-separators depending on which helper a caller happened to
// pick. Both helpers now route through `Money.formatAUD` (see
// core/static/core/js/money.js) so there is exactly one currency pipeline.

/**
 * Format a number with AU thousand separators and 2 decimal places.
 * Handles null, undefined, and NaN gracefully.
 *
 * @param {number|string} num - Number to format
 * @returns {string} Formatted number string (e.g., "1,234.56")
 */
function formatNumber(num) {
    if (num === null || num === undefined || isNaN(parseFloat(num))) {
        return '0.00';
    }
    return parseFloat(num).toLocaleString('en-AU', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
    });
}

/**
 * Format amount as currency with $ symbol (AU locale). Uses Money.formatAUD
 * when available so the symbol/locale stay in lock-step with the canonical
 * money pipeline.
 *
 * @param {number|string} amount - Amount to format
 * @returns {string} Formatted currency string (e.g., "$1,234.56")
 */
function formatCurrency(amount) {
    if (window.Money && typeof window.Money.formatAUD === 'function') {
        return window.Money.formatAUD(amount);
    }
    return '$' + formatNumber(amount);
}

/**
 * Safely parse a float value, returning 0 for invalid inputs.
 *
 * @param {any} value - Value to parse
 * @returns {number} Parsed float or 0
 */
function parseFloatSafe(value) {
    var parsed = parseFloat(value);
    return isNaN(parsed) ? 0 : parsed;
}

/**
 * Alias for formatNumber. Kept so existing callers don't break. New code
 * should call `Utils.formatNumber` (or Money.formatAUD) directly.
 *
 * @param {number|string} num - Number to format
 * @returns {string} Formatted string (e.g., "1,234.56")
 */
function formatMoney(num) {
    return formatNumber(num);
}

/**
 * Format a date string as dd-mmm-yy (e.g., "31-Jan-26")
 * 
 * @param {string} dateStr - Date string in YYYY-MM-DD format
 * @returns {string} Formatted date string
 */
function formatDateDMY(dateStr) {
    if (!dateStr) return '-';
    var months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    var date = new Date(dateStr);
    if (isNaN(date.getTime())) return '-';
    var day = String(date.getDate()).padStart(2, '0');
    var month = months[date.getMonth()];
    var year = String(date.getFullYear()).slice(-2);
    return day + '-' + month + '-' + year;
}

/**
 * Escape HTML special characters to prevent XSS attacks.
 * Converts &, <, >, ", ' to their HTML entity equivalents.
 * 
 * @param {string} text - Text to escape
 * @returns {string} Escaped text safe for HTML insertion
 */
function escapeHtml(text) {
    if (!text) return '';
    var map = {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;'};
    return String(text).replace(/[&<>"']/g, function(m) { return map[m]; });
}

/**
 * Extract project PK from URL path.
 * Matches URLs like /project/123/ or /core/project/123/
 * 
 * @returns {string|null} Project PK or null if not found
 */
function getProjectPkFromUrl() {
    var match = window.location.pathname.match(/\/project\/(\d+)/);
    return match ? match[1] : null;
}

/**
 * Check if a section is in construction mode.
 * Reads from AllocationsManager config if available.
 * 
 * @param {string} sectionId - Section identifier (e.g., 'quote', 'bill', 'po')
 * @returns {boolean} True if construction mode is enabled
 */
function isConstructionProject(sectionId) {
    // Try to get from AllocationsManager config
    if (window.AllocationsManager && window.AllocationsManager.getConfig) {
        var cfg = window.AllocationsManager.getConfig(sectionId);
        if (cfg && cfg.features) {
            return cfg.features.constructionMode || false;
        }
    }
    // Fallback: check window variables set by templates
    if (sectionId === 'bill') return window.billIsConstruction || false;
    if (sectionId === 'quote') return window.quoteIsConstruction || window.isConstruction || false;
    return false;
}

/**
 * Apply column width styles to a table.
 * Handles the display:block tbody scrolling alignment issue.
 * 
 * @param {string} sectionId - Section identifier (used to build table ID)
 * @param {Array} widths - Array of width strings (e.g., ['40%', '20%', '35%', '5%'])
 * @param {Object} options - Optional settings { addEditableClass: true }
 */
function applyColumnStyles(sectionId, widths, options) {
    var tableId = sectionId + 'AllocationsTable';
    var opts = options || {};
    
    // Add editable-allocations class for tighter padding if requested
    if (opts.addEditableClass) {
        $('#' + tableId).addClass('editable-allocations');
    }
    
    // Get the actual table width for precise pixel calculations
    var $table = $('#' + tableId);
    var tableWidth = $table.width();
    
    // Calculate pixel widths using the table's actual width (not available space)
    // This ensures perfect alignment by using the same calculation the browser uses
    var pixelWidths = [];
    widths.forEach(function(w, i) {
        // Use the table's actual width for calculation (like browser does for percentages)
        var pixelWidth = Math.round(tableWidth * parseFloat(w) / 100);
        pixelWidths.push(pixelWidth);
    });
    
    // Ensure table fits within container by using available width for calculations
    var containerWidth = $('#' + tableId).parent().width();
    
    // Recalculate pixel widths based on container width (not table width)
    pixelWidths = [];
    widths.forEach(function(w, i) {
        var pixelWidth = Math.round(containerWidth * parseFloat(w) / 100);
        pixelWidths.push(pixelWidth);
    });
    
    // Ensure table fits perfectly
    $('#' + tableId).css('width', '100%');
    
    // Inject CSS to apply column widths to both thead and tbody
    // (needed because tbody uses display:block for scrolling)
    var styleId = tableId + 'ColumnStyles';
    var styleEl = $('#' + styleId);
    if (styleEl.length === 0) {
        styleEl = $('<style>').attr('id', styleId);
        $('head').append(styleEl);
    }
    var css = '';
    pixelWidths.forEach(function(pixelWidth, i) {
        // Use precise pixel widths for both th and td, overriding inline styles
        css += '#' + tableId + ' thead th:nth-child(' + (i + 1) + '),\n';
        css += '#' + tableId + ' tbody td:nth-child(' + (i + 1) + ') { width: ' + pixelWidth + 'px !important; min-width: ' + pixelWidth + 'px !important; max-width: ' + pixelWidth + 'px !important; box-sizing: border-box !important; padding: 8px !important; margin: 0 !important; border: 1px solid #ddd !important; }\n';
    });
    styleEl.text(css);
}

/**
 * Recalculate footer totals from current row values.
 * 
 * @param {string} sectionId - Section identifier
 * @param {Array} columnMappings - Array of {colIndex, inputSelector} or {colIndex, cellIndex}
 * @returns {Object} Totals object keyed by colIndex
 */
function recalculateFooterTotals(sectionId, columnMappings) {
    var totals = {};
    
    $('#' + sectionId + 'MainTableBody tr').each(function() {
        var row = $(this);
        columnMappings.forEach(function(mapping) {
            var value = 0;
            if (mapping.inputSelector) {
                value = parseFloat(row.find(mapping.inputSelector).val()) || 0;
            } else if (mapping.cellIndex !== undefined) {
                var text = row.find('td:eq(' + mapping.cellIndex + ')').text().replace(/[$,]/g, '');
                value = parseFloat(text) || 0;
            }
            totals[mapping.colIndex] = (totals[mapping.colIndex] || 0) + value;
        });
    });
    
    columnMappings.forEach(function(mapping) {
        var value = totals[mapping.colIndex] || 0;
        $('#' + sectionId + 'FooterCol' + mapping.colIndex).text('$' + formatMoney(value));
    });
    
    return totals;
}

/**
 * Get CSRF token for fetch/ajax requests.
 * Convenience wrapper around getCookie.
 * 
 * @returns {string} CSRF token value
 */
function getCSRFToken() {
    return getCookie('csrftoken');
}

/**
 * Format a number as quantity (no decimals, with thousand separators).
 * Used for displaying quantities consistently across the app.
 * 
 * @param {number|string} num - Number to format
 * @returns {string} Formatted string (e.g., "1,234")
 */
function formatQty(num) {
    return parseFloat(num || 0).toLocaleString('en-AU', { 
        minimumFractionDigits: 0, 
        maximumFractionDigits: 0 
    });
}

/**
 * Standard headers for JSON POST requests.
 * 
 * @returns {Object} Headers object with Content-Type and CSRF token
 */
function getJSONHeaders() {
    return {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCSRFToken()
    };
}

/**
 * Unified HTTP client for the dev_app frontend.
 *
 * Wraps `fetch` so callers don't have to reinvent CSRF, JSON parsing, or
 * status/error handling on every call site. Pairs with the server-side
 * `json_ok` / `json_err` envelopes in `core/views/_helpers.py`:
 *
 *     {status: "success", ...}        -> resolves with the parsed JSON
 *     {status: "error", message, ...} -> rejects with an Error whose
 *                                        `.message`, `.status`, and `.body`
 *                                        carry the server payload
 *
 * Usage:
 *
 *     Utils.api('/api/foo/', { method: 'POST', body: { x: 1 } })
 *         .then(function(data) { ... })
 *         .catch(function(err) { showToast(err.message); });
 *
 * Options:
 *   - method:  HTTP verb (default 'GET')
 *   - body:    plain object (auto JSON.stringify-ed) OR FormData/string
 *              (passed through; CSRF header still added)
 *   - headers: extra headers merged on top of defaults
 *   - signal:  AbortSignal (optional)
 *
 * Notes:
 *   - GET requests do NOT set Content-Type and do NOT send a body.
 *   - Non-2xx responses always reject; the server's JSON `message` is
 *     surfaced if available, otherwise `HTTP <status>`.
 *   - Network failures reject with a synthetic `{status:0}` error so
 *     callers can branch on offline/CORS independently of API errors.
 */
function apiRequest(url, options) {
    var opts = options || {};
    var method = (opts.method || 'GET').toUpperCase();
    var headers = { 'X-Requested-With': 'XMLHttpRequest' };

    // CSRF for any state-changing verb (Django checks SAFE_METHODS)
    if (['POST', 'PUT', 'PATCH', 'DELETE'].indexOf(method) !== -1) {
        headers['X-CSRFToken'] = getCSRFToken();
    }

    // Body handling: plain object -> JSON; FormData/string -> pass-through
    var fetchInit = { method: method, credentials: 'same-origin' };
    var body = opts.body;
    if (body !== undefined && body !== null && method !== 'GET' && method !== 'HEAD') {
        if (typeof FormData !== 'undefined' && body instanceof FormData) {
            // Let the browser set the Content-Type with the multipart boundary.
            fetchInit.body = body;
        } else if (typeof body === 'string') {
            fetchInit.body = body;
        } else {
            headers['Content-Type'] = 'application/json';
            fetchInit.body = JSON.stringify(body);
        }
    }

    // Merge user headers last so callers can override anything above.
    if (opts.headers) {
        Object.keys(opts.headers).forEach(function (k) { headers[k] = opts.headers[k]; });
    }
    fetchInit.headers = headers;
    if (opts.signal) fetchInit.signal = opts.signal;

    return fetch(url, fetchInit).then(function (resp) {
        var contentType = resp.headers.get('Content-Type') || '';
        var parser = contentType.indexOf('application/json') !== -1
            ? resp.json()
            : resp.text();
        return parser.then(function (parsed) {
            if (!resp.ok) {
                var msg = (parsed && parsed.message)
                    ? parsed.message
                    : ('HTTP ' + resp.status);
                var err = new Error(msg);
                err.status = resp.status;
                err.body = parsed;
                throw err;
            }
            // Server-side json_err uses 4xx/5xx, but defensively also reject
            // {status:"error"} responses that slipped through with HTTP 200.
            if (parsed && parsed.status === 'error') {
                var err2 = new Error(parsed.message || 'Request failed');
                err2.status = resp.status;
                err2.body = parsed;
                throw err2;
            }
            return parsed;
        });
    }, function (networkErr) {
        // Convert AbortError / TypeError into our error shape.
        var err = new Error(networkErr.message || 'Network error');
        err.status = 0;
        err.cause = networkErr;
        throw err;
    });
}

// Convenience verbs.
function apiGet(url, opts)         { return apiRequest(url, Object.assign({}, opts, { method: 'GET' })); }
function apiPost(url, body, opts)  { return apiRequest(url, Object.assign({}, opts, { method: 'POST',  body: body })); }
function apiPut(url, body, opts)   { return apiRequest(url, Object.assign({}, opts, { method: 'PUT',   body: body })); }
function apiPatch(url, body, opts) { return apiRequest(url, Object.assign({}, opts, { method: 'PATCH', body: body })); }
function apiDelete(url, opts)      { return apiRequest(url, Object.assign({}, opts, { method: 'DELETE' })); }

/**
 * Initialize sortable table functionality.
 * Adds click handlers to th.sortable headers to sort table rows.
 * Safe to call multiple times - removes old handlers before adding new ones.
 * 
 * @param {string} tableId - ID of the table element (without #)
 * @param {Object} options - Optional settings
 * @param {string} options.tbodyId - ID of tbody if different from default (tableId + 'Body')
 * @param {Function} options.onSort - Callback after sort completes (columnIndex, direction)
 */
function initSortableTable(tableId, options) {
    var opts = options || {};
    var table = document.getElementById(tableId);
    if (!table) {
        console.warn('initSortableTable: table not found:', tableId);
        return;
    }
    
    var headers = table.querySelectorAll('thead th.sortable');
    if (headers.length === 0) {
        return; // No sortable columns
    }
    
    // Determine tbody - try options.tbodyId, then tableId + 'Body', then first tbody
    var tbody = opts.tbodyId ? document.getElementById(opts.tbodyId) : 
                document.getElementById(tableId + 'Body') ||
                table.querySelector('tbody');
    
    if (!tbody) {
        console.warn('initSortableTable: tbody not found for table:', tableId);
        return;
    }
    
    // Remove any existing sort handlers to prevent duplicates on re-init
    headers.forEach(function(header) {
        // Clone and replace to remove all event listeners
        var newHeader = header.cloneNode(true);
        header.parentNode.replaceChild(newHeader, header);
    });
    
    // Re-query headers after replacement
    headers = table.querySelectorAll('thead th.sortable');
    
    headers.forEach(function(header, index) {
        header.addEventListener('click', function() {
            var columnIndex = Array.from(header.parentNode.children).indexOf(header);
            var currentDirection = header.classList.contains('sort-asc') ? 'asc' : 
                                   header.classList.contains('sort-desc') ? 'desc' : null;
            var newDirection = currentDirection === 'asc' ? 'desc' : 'asc';
            
            // Remove sort classes from all headers
            headers.forEach(function(h) {
                h.classList.remove('sort-asc', 'sort-desc');
            });
            
            // Add sort class to clicked header
            header.classList.add('sort-' + newDirection);
            
            // Get rows and sort
            var rows = Array.from(tbody.querySelectorAll('tr:not(.add-contact-row)'));
            
            rows.sort(function(a, b) {
                var cellA = a.children[columnIndex];
                var cellB = b.children[columnIndex];
                
                if (!cellA || !cellB) return 0;
                
                var valueA = cellA.textContent.trim();
                var valueB = cellB.textContent.trim();
                
                // Try to parse as number (remove $ and , for currency)
                var numA = parseFloat(valueA.replace(/[$,]/g, ''));
                var numB = parseFloat(valueB.replace(/[$,]/g, ''));
                
                var comparison;
                if (!isNaN(numA) && !isNaN(numB)) {
                    // Numeric sort
                    comparison = numA - numB;
                } else {
                    // String sort (case-insensitive)
                    comparison = valueA.toLowerCase().localeCompare(valueB.toLowerCase());
                }
                
                return newDirection === 'asc' ? comparison : -comparison;
            });
            
            // Re-append sorted rows
            rows.forEach(function(row) {
                tbody.appendChild(row);
            });
            
            // Call onSort callback if provided
            if (opts.onSort) {
                opts.onSort(columnIndex, newDirection);
            }
        });
    });
    
    // Automatically add truncation tooltips after sort initialization
    addTruncationTooltips(tableId);
}

/**
 * Add tooltips to table cells that have truncated text.
 * Automatically detects cells where content overflows and adds title attribute.
 * Safe to call multiple times - updates tooltips based on current state.
 * 
 * @param {string} tableId - ID of the table element (without #)
 */
function addTruncationTooltips(tableId) {
    var table = document.getElementById(tableId);
    if (!table) return;
    
    // Process all td cells in the table
    table.querySelectorAll('td').forEach(function(cell) {
        // Skip cells with buttons/inputs (action columns)
        if (cell.querySelector('button, input, select, a')) {
            cell.removeAttribute('title');
            return;
        }
        
        // Check if content is truncated (scrollWidth > clientWidth)
        if (cell.scrollWidth > cell.clientWidth) {
            cell.setAttribute('title', cell.textContent.trim());
        } else {
            // Remove title if no longer truncated (e.g., after resize)
            cell.removeAttribute('title');
        }
    });
}

/**
 * Convert a select element into a searchable dropdown.
 * Features:
 * - Type-ahead search filtering
 * - Pinned items stay at top (e.g., "+ New Supplier")
 * - Keyboard navigation (arrows, enter, escape)
 * - Click outside to close
 * 
 * @param {jQuery|HTMLElement|string} selectElement - Select element, jQuery object, or selector
 * @param {Object} options - Configuration options
 * @param {Array} options.pinnedValues - Values that should stay pinned at top (e.g., ['__new__'])
 * @param {string} options.placeholder - Placeholder text for search input
 * @param {Function} options.onChange - Callback when value changes (value, text, $select)
 * @returns {Object} Controller object with methods: refresh(), destroy(), getValue(), setValue(val)
 */
function createSearchableDropdown(selectElement, options) {
    var $select = $(selectElement);
    if (!$select.length) return null;
    
    var opts = $.extend({
        pinnedValues: [],
        placeholder: 'Search...',
        onChange: null
    }, options);
    
    // Skip if already initialized
    if ($select.data('searchable-dropdown')) {
        return $select.data('searchable-dropdown');
    }
    
    // Hide original select
    $select.hide();
    
    // Create wrapper - dropdown appended to body to escape overflow constraints
    var $wrapper = $('<div class="searchable-dropdown-wrapper"></div>');
    var $trigger = $('<div class="searchable-dropdown-trigger form-control form-control-sm"></div>');
    var $dropdown = $('<div class="searchable-dropdown-menu"></div>');
    var $searchInput = $('<input type="text" class="searchable-dropdown-search form-control form-control-sm" placeholder="' + opts.placeholder + '">');
    var $pinnedList = $('<div class="searchable-dropdown-pinned"></div>');
    var $optionsList = $('<div class="searchable-dropdown-options"></div>');
    
    $dropdown.append($searchInput).append($pinnedList).append($optionsList);
    $wrapper.append($trigger);
    $select.after($wrapper);
    // Append dropdown to body so it escapes table row overflow
    $('body').append($dropdown);
    
    // Build options from select
    function buildOptions() {
        $pinnedList.empty();
        $optionsList.empty();
        
        $select.find('option').each(function() {
            var $opt = $(this);
            var val = $opt.val();
            var text = $opt.text();
            var disabled = $opt.prop('disabled');
            
            if (!val && !disabled) {
                // Skip empty placeholder option
                return;
            }
            
            var $item = $('<div class="searchable-dropdown-item"></div>')
                .attr('data-value', val)
                .text(text);
            
            if (disabled) {
                $item.addClass('disabled');
            }
            
            if (opts.pinnedValues.indexOf(val) !== -1) {
                $item.addClass('pinned');
                $pinnedList.append($item);
            } else {
                $optionsList.append($item);
            }
        });
        
        updateTriggerText();
    }
    
    // Update trigger text based on selected value
    function updateTriggerText() {
        var selectedOption = $select.find('option:selected');
        var text = selectedOption.length && selectedOption.val() ? selectedOption.text() : $select.find('option:first').text();
        $trigger.text(text);
        
        if (!selectedOption.val()) {
            $trigger.addClass('placeholder');
        } else {
            $trigger.removeClass('placeholder');
        }
    }
    
    // Filter options based on search
    function filterOptions(query) {
        var q = query.toLowerCase().trim();
        var visibleCount = 0;
        
        // Remove existing no-results message
        $optionsList.find('.searchable-dropdown-no-results').remove();
        
        $optionsList.find('.searchable-dropdown-item').each(function() {
            var $item = $(this);
            var text = $item.text().toLowerCase();
            
            if (!q || text.indexOf(q) !== -1) {
                $item.show();
                visibleCount++;
            } else {
                $item.hide();
            }
        });
        
        // Show "no results" if nothing matches
        if (visibleCount === 0 && q) {
            $optionsList.append('<div class="searchable-dropdown-no-results">No matches found</div>');
        }
        
        // Pinned items always visible
        $pinnedList.find('.searchable-dropdown-item').show();
        
        // Auto-highlight first visible item
        $dropdown.find('.searchable-dropdown-item').removeClass('highlighted');
        $dropdown.find('.searchable-dropdown-item:visible:not(.disabled):first').addClass('highlighted');
    }
    
    // Open dropdown
    function open() {
        $trigger.addClass('open');
        $dropdown.addClass('open');
        
        // Position dropdown below trigger (since dropdown is in body)
        var triggerOffset = $trigger.offset();
        var triggerHeight = $trigger.outerHeight();
        var triggerWidth = $trigger.outerWidth();
        
        $dropdown.css({
            position: 'fixed',
            top: triggerOffset.top + triggerHeight - $(window).scrollTop(),
            left: triggerOffset.left - $(window).scrollLeft(),
            width: triggerWidth,
            minWidth: 200
        });
        
        $searchInput.val('').focus();
        filterOptions('');
    }
    
    // Close dropdown
    function close() {
        $trigger.removeClass('open');
        $dropdown.removeClass('open');
        $searchInput.val('');
        filterOptions('');
        $dropdown.find('.searchable-dropdown-item').removeClass('highlighted');
    }
    
    // Select an option
    function selectOption(value) {
        $select.val(value).trigger('change');
        updateTriggerText();
        close();
        
        if (opts.onChange) {
            var text = $select.find('option:selected').text();
            opts.onChange(value, text, $select);
        }
    }
    
    // Event handlers
    $trigger.on('click', function(e) {
        e.stopPropagation();
        if ($dropdown.hasClass('open')) {
            close();
        } else {
            open();
        }
    });
    
    $searchInput.on('input', function() {
        filterOptions($(this).val());
    });
    
    $searchInput.on('keydown', function(e) {
        var $visible = $dropdown.find('.searchable-dropdown-item:visible:not(.disabled)');
        var $highlighted = $dropdown.find('.searchable-dropdown-item.highlighted');
        var idx = $visible.index($highlighted);
        
        if (e.key === 'ArrowDown') {
            e.preventDefault();
            $visible.removeClass('highlighted');
            var nextIdx = idx < $visible.length - 1 ? idx + 1 : 0;
            $visible.eq(nextIdx).addClass('highlighted');
            scrollToHighlighted();
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            $visible.removeClass('highlighted');
            var prevIdx = idx > 0 ? idx - 1 : $visible.length - 1;
            $visible.eq(prevIdx).addClass('highlighted');
            scrollToHighlighted();
        } else if (e.key === 'Enter') {
            e.preventDefault();
            if ($highlighted.length) {
                selectOption($highlighted.attr('data-value'));
            }
        } else if (e.key === 'Escape') {
            close();
        }
    });
    
    function scrollToHighlighted() {
        var $highlighted = $dropdown.find('.searchable-dropdown-item.highlighted');
        if ($highlighted.length) {
            $highlighted[0].scrollIntoView({ block: 'nearest' });
        }
    }
    
    $dropdown.on('click', '.searchable-dropdown-item:not(.disabled)', function(e) {
        e.stopPropagation();
        selectOption($(this).attr('data-value'));
    });
    
    $dropdown.on('mouseenter', '.searchable-dropdown-item', function() {
        $dropdown.find('.searchable-dropdown-item').removeClass('highlighted');
        $(this).addClass('highlighted');
    });
    
    // Close on click outside (check both wrapper and dropdown since dropdown is in body)
    $(document).on('click.searchableDropdown', function(e) {
        var clickedWrapper = $wrapper.is(e.target) || $wrapper.has(e.target).length > 0;
        var clickedDropdown = $dropdown.is(e.target) || $dropdown.has(e.target).length > 0;
        if (!clickedWrapper && !clickedDropdown) {
            close();
        }
    });
    
    // Build initial options
    buildOptions();
    
    // Controller object
    var controller = {
        refresh: function() {
            buildOptions();
        },
        destroy: function() {
            $(document).off('click.searchableDropdown');
            $dropdown.remove();  // Remove from body
            $wrapper.remove();
            $select.show().removeData('searchable-dropdown');
        },
        getValue: function() {
            return $select.val();
        },
        setValue: function(val) {
            $select.val(val);
            updateTriggerText();
        }
    };
    
    $select.data('searchable-dropdown', controller);
    
    return controller;
}

// Expose as Utils namespace object
window.Utils = {
    getCookie: getCookie,
    formatNumber: formatNumber,
    formatMoney: formatMoney,
    formatDateDMY: formatDateDMY,
    formatCurrency: formatCurrency,
    parseFloatSafe: parseFloatSafe,
    escapeHtml: escapeHtml,
    getProjectPkFromUrl: getProjectPkFromUrl,
    isConstructionProject: isConstructionProject,
    applyColumnStyles: applyColumnStyles,
    recalculateFooterTotals: recalculateFooterTotals,
    formatQty: formatQty,
    getCSRFToken: getCSRFToken,
    getJSONHeaders: getJSONHeaders,
    api: apiRequest,
    apiGet: apiGet,
    apiPost: apiPost,
    apiPut: apiPut,
    apiPatch: apiPatch,
    apiDelete: apiDelete,
    initSortableTable: initSortableTable,
    addTruncationTooltips: addTruncationTooltips,
    createSearchableDropdown: createSearchableDropdown
};

// Inject CSS for searchable dropdown (only once)
(function() {
    if (document.getElementById('searchable-dropdown-styles')) return;
    
    var css = `
        .searchable-dropdown-wrapper {
            position: relative;
            display: inline-block;
            width: 100%;
        }
        .searchable-dropdown-trigger {
            cursor: pointer;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            padding: 2px 20px 2px 6px !important;
            font-size: 12px;
            height: 24px;
            border: 1px solid var(--color-border, #ced4da);
            border-radius: 3px;
            background: #fff url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12'%3E%3Cpath fill='%23333' d='M2 4l4 4 4-4z'/%3E%3C/svg%3E") no-repeat right 6px center;
        }
        .searchable-dropdown-trigger.placeholder {
            color: #6c757d;
        }
        .searchable-dropdown-trigger.open {
            border-bottom-left-radius: 0;
            border-bottom-right-radius: 0;
            border-bottom-color: transparent;
        }
        .searchable-dropdown-menu {
            display: none;
            position: fixed;
            z-index: 9999;
            background: #fff;
            border: 1px solid black;
            border-radius: 6px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            max-height: 400px;
            overflow: hidden;
        }
        .searchable-dropdown-menu.open {
            display: flex;
            flex-direction: column;
        }
        .searchable-dropdown-search {
            margin: 6px;
            width: calc(100% - 12px) !important;
            flex-shrink: 0;
            font-size: 12px;
            padding: 2px 6px;
            height: 24px;
            border: 1px solid var(--color-border, #ced4da);
            border-radius: 3px;
        }
        .searchable-dropdown-search:focus {
            outline: none;
            border-color: #80bdff;
            box-shadow: 0 0 0 0.2rem rgba(0,123,255,.25);
        }
        .searchable-dropdown-pinned {
            flex-shrink: 0;
            border-bottom: 1px solid #e9ecef;
            background: var(--color-bg-muted, #f8f9fa);
        }
        .searchable-dropdown-pinned:empty {
            display: none;
        }
        .searchable-dropdown-options {
            overflow-y: auto;
            flex: 1;
            max-height: 320px;
        }
        .searchable-dropdown-item {
            padding: 4px 8px;
            cursor: pointer;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            font-size: 12px;
        }
        .searchable-dropdown-item:hover,
        .searchable-dropdown-item.highlighted {
            background: #007bff;
            color: #fff;
        }
        .searchable-dropdown-item.pinned {
            font-weight: 600;
            color: #28a745;
        }
        .searchable-dropdown-item.pinned:hover,
        .searchable-dropdown-item.pinned.highlighted {
            background: #28a745;
            color: #fff;
        }
        .searchable-dropdown-item.disabled {
            color: #6c757d;
            cursor: default;
            font-style: italic;
            font-size: 11px;
        }
        .searchable-dropdown-item.disabled:hover {
            background: transparent;
            color: #6c757d;
        }
        .searchable-dropdown-no-results {
            padding: 6px 8px;
            color: #6c757d;
            font-style: italic;
            text-align: center;
            font-size: 12px;
        }
    `;
    
    var style = document.createElement('style');
    style.id = 'searchable-dropdown-styles';
    style.textContent = css;
    document.head.appendChild(style);
})();


// ============================================================================
// FX (Foreign Currency) Utilities
// See FX_IMPLEMENTATION_PLAN.md for full spec.
// ============================================================================

/**
 * Supported currencies for FX bills.
 * ISO 4217 codes.
 */
var FX_CURRENCIES = ['AUD', 'USD', 'EUR', 'GBP', 'NZD', 'SGD'];

/**
 * Check if a bill is a foreign currency (FX) bill.
 * @param {Object} bill - Bill object with currency field
 * @returns {boolean} True if currency is not AUD
 */
function isFxBill(bill) {
    return bill && bill.currency && bill.currency !== 'AUD';
}

/**
 * Check if a bill is unfixed (FX bill that hasn't been fixed yet).
 * @param {Object} bill - Bill object with currency and is_fx_fixed fields
 * @returns {boolean} True if FX bill and not fixed
 */
function isUnfixedFxBill(bill) {
    return isFxBill(bill) && !bill.is_fx_fixed;
}

/**
 * Format currency amount with currency code.
 * @param {number} amount - Amount to format
 * @param {string} currency - ISO 4217 currency code (default: 'AUD')
 * @returns {string} Formatted string like "$1,234.56 USD" or "$1,234.56"
 */
function formatFxAmount(amount, currency) {
    var formatted = formatCurrency(amount);
    if (currency && currency !== 'AUD') {
        return formatted + ' ' + currency;
    }
    return formatted;
}

/**
 * Calculate estimated AUD from foreign amount and exchange rate.
 * @param {number} foreignAmount - Amount in foreign currency
 * @param {number} exchangeRate - Exchange rate (1 foreign = X AUD)
 * @returns {number|null} Estimated AUD amount or null if can't calculate
 */
function calculateEstimatedAud(foreignAmount, exchangeRate) {
    if (foreignAmount && exchangeRate) {
        return foreignAmount * exchangeRate;
    }
    return null;
}




// Make FX utilities globally available
window.FX_CURRENCIES = FX_CURRENCIES;
window.isFxBill = isFxBill;
window.isUnfixedFxBill = isUnfixedFxBill;
window.formatFxAmount = formatFxAmount;
window.calculateEstimatedAud = calculateEstimatedAud;

// Add to Utils namespace if it exists
if (typeof Utils !== 'undefined') {
    Utils.FX_CURRENCIES = FX_CURRENCIES;
    Utils.isFxBill = isFxBill;
    Utils.isUnfixedFxBill = isUnfixedFxBill;
    Utils.formatFxAmount = formatFxAmount;
    Utils.calculateEstimatedAud = calculateEstimatedAud;
}

