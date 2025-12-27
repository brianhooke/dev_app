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

/**
 * Format a number with thousand separators and 2 decimal places.
 * Handles null, undefined, and NaN gracefully.
 * 
 * @param {number|string} num - Number to format
 * @returns {string} Formatted number string (e.g., "1,234.56")
 */
function formatNumber(num) {
    if (num === null || num === undefined || isNaN(num)) {
        return '0.00';
    }
    return parseFloat(num).toLocaleString('en-US', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    });
}

/**
 * Format amount as currency with $ symbol.
 * 
 * @param {number|string} amount - Amount to format
 * @returns {string} Formatted currency string (e.g., "$1,234.56")
 */
function formatCurrency(amount) {
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
 * Format a number as currency with thousand separators (Australian locale).
 * Used for displaying monetary values consistently across the app.
 * 
 * @param {number|string} num - Number to format
 * @returns {string} Formatted string (e.g., "1,234.56")
 */
function formatMoney(num) {
    return parseFloat(num || 0).toLocaleString('en-AU', { 
        minimumFractionDigits: 2, 
        maximumFractionDigits: 2 
    });
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
    
    // Inject CSS to apply column widths to both thead and tbody
    // (needed because tbody uses display:block for scrolling)
    var styleId = tableId + 'ColumnStyles';
    var styleEl = $('#' + styleId);
    if (styleEl.length === 0) {
        styleEl = $('<style>').attr('id', styleId);
        $('head').append(styleEl);
    }
    var css = '';
    widths.forEach(function(w, i) {
        css += '#' + tableId + ' thead th:nth-child(' + (i + 1) + '),\n';
        css += '#' + tableId + ' tbody td:nth-child(' + (i + 1) + ') { width: ' + w + ' !important; }\n';
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

// Expose as Utils namespace object
window.Utils = {
    getCookie: getCookie,
    formatNumber: formatNumber,
    formatMoney: formatMoney,
    formatCurrency: formatCurrency,
    parseFloatSafe: parseFloatSafe,
    escapeHtml: escapeHtml,
    getProjectPkFromUrl: getProjectPkFromUrl,
    isConstructionProject: isConstructionProject,
    applyColumnStyles: applyColumnStyles,
    recalculateFooterTotals: recalculateFooterTotals,
    formatQty: formatQty,
    getCSRFToken: getCSRFToken,
    getJSONHeaders: getJSONHeaders
};
