// SC Selection Modal for HC Claims

document.addEventListener('DOMContentLoaded', function() {

  // 1) If user chooses "makeClaim" in #hcDropdown => show #hcSelectInvoicesModal
  const hcDropdown = document.getElementById('hcDropdown');
  if (hcDropdown) {
    hcDropdown.addEventListener('change', function(e) {
      if (e.target.value === 'makeClaim') {
        $('#hcSelectInvoicesModal').modal('show');
      }
    });
  }

  // 2) "View PDF link" inside the SC Invoice selections modal
  document.querySelectorAll('.view-pdf-hcClaim').forEach(link => {
    link.addEventListener('click', function(event) {
      event.preventDefault();
      const pdfUrl = this.getAttribute('data-url');
      fetch(pdfUrl, {
        method: 'GET',
        headers: { 'Content-Type': 'application/pdf' }
      })
      .then(response => response.blob())
      .then(blob => {
        const url = URL.createObjectURL(blob);
        const pdfViewer = document.getElementById('hcInvoicesPdfViewer');
        if (pdfViewer) {
          pdfViewer.src = url;
        }
      })
      .catch(error => {
        console.error('Error fetching PDF:', error);
      });
    });
  });

  // 3) "Send Invoices to Xero" => #hcSendInvoicesToXeroButton
  const hcSendInvoicesBtn = document.getElementById('hcSendInvoicesToXeroButton');
  if (hcSendInvoicesBtn) {
    hcSendInvoicesBtn.addEventListener('click', function() {
      const selectedInvoices = [];
      document.querySelectorAll('input[type=checkbox]:checked').forEach(chk => {
        const invoiceId = chk.id.replace('hcIncludeInClaim','');
        selectedInvoices.push(invoiceId);
      });

      // AJAX call to associate SC invoices with new HC claim
      fetch('/associate_sc_claims_with_hc_claim/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({ 'selectedInvoices': selectedInvoices })
      })
      .then(res => {
        if (!res.ok) throw new Error('Network response was not ok');
        return res.text();
      })
      .then(() => {
        alert('New HC Claim started. The selected invoices have been associated.');
        location.reload();
      })
      .catch(err => {
        console.error(err);
        alert('Error associating invoices with HC Claim.');
      });
    });
  }

});
