/* Money / GST helpers — single source of truth for the front end.
 *
 * Mirrors core/formulas.py. If GST_RATE ever changes, update both. The
 * Australian GST is currently 10%.
 *
 * Exposes a global Money object so legacy templates that don't use modules
 * can call Money.formatAUD(...) without a build step.
 */
(function (global) {
    var GST_RATE = 0.10;

    function toNumber(value, fallback) {
        if (fallback === undefined) fallback = 0;
        if (value === null || value === undefined || value === '') return fallback;
        var n = typeof value === 'number' ? value : parseFloat(String(value).replace(/,/g, ''));
        return isNaN(n) ? fallback : n;
    }

    function round2(value) {
        // Round half away from zero (matches Decimal HALF_UP for positives,
        // and for negatives matches Python core/formulas.py quantize_money).
        var sign = value < 0 ? -1 : 1;
        return sign * Math.round(Math.abs(value) * 100) / 100;
    }

    function gstFromNet(net) {
        return round2(toNumber(net) * GST_RATE);
    }

    function grossFromNet(net) {
        var n = toNumber(net);
        return round2(n + n * GST_RATE);
    }

    function netFromGross(gross) {
        return round2(toNumber(gross) / (1 + GST_RATE));
    }

    var formatter = (typeof Intl !== 'undefined' && Intl.NumberFormat)
        ? new Intl.NumberFormat('en-AU', {
            style: 'currency',
            currency: 'AUD',
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        })
        : null;

    function formatAUD(value) {
        var n = toNumber(value, 0);
        if (formatter) return formatter.format(n);
        return '$' + n.toFixed(2);
    }

    function parseAUD(value) {
        if (value === null || value === undefined) return 0;
        return toNumber(String(value).replace(/[^0-9.\-]/g, ''));
    }

    global.Money = {
        GST_RATE: GST_RATE,
        toNumber: toNumber,
        round2: round2,
        gstFromNet: gstFromNet,
        grossFromNet: grossFromNet,
        netFromGross: netFromGross,
        formatAUD: formatAUD,
        parseAUD: parseAUD,
    };
})(window);
