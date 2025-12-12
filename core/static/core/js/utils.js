/**
 * Shared utility functions for the dev_app frontend.
 * 
 * This file consolidates commonly duplicated functions across JS files.
 * Import this file BEFORE other JS files that depend on these utilities.
 * 
 * Functions provided:
 * - getCookie(name) - Get cookie value by name (for CSRF tokens)
 * - formatNumber(num) - Format number with commas and 2 decimal places
 * - formatCurrency(amount) - Format as currency with $ symbol
 * - parseFloatSafe(value) - Parse float, returning 0 for invalid values
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
 * Get CSRF token for fetch/ajax requests.
 * Convenience wrapper around getCookie.
 * 
 * @returns {string} CSRF token value
 */
function getCSRFToken() {
    return getCookie('csrftoken');
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

// Make functions available globally (for backward compatibility)
window.getCookie = getCookie;
window.formatNumber = formatNumber;
window.formatCurrency = formatCurrency;
window.parseFloatSafe = parseFloatSafe;
window.getCSRFToken = getCSRFToken;
window.getJSONHeaders = getJSONHeaders;

// Also export as module if module system is available
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        getCookie,
        formatNumber,
        formatCurrency,
        parseFloatSafe,
        getCSRFToken,
        getJSONHeaders
    };
}
