// SC Selection Modal for HC Claims

document.addEventListener('DOMContentLoaded', function() {

  function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
      const cookies = document.cookie.split(';');
      for (let i = 0; i < cookies.length; i++) {
        const cookie = cookies[i].trim();
        // Does this cookie string begin with the name we want?
        if (cookie.substring(0, name.length + 1) === (name + '=')) {
          cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
          break;
        }
      }
    }
    return cookieValue;
  }

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
      // Convert array to multiple URLSearchParams entries
      const formData = new FormData();
      selectedInvoices.forEach(id => {
        formData.append('selectedInvoices[]', id);
      });

      fetch('/associate_sc_claims_with_hc_claim/', {
        method: 'POST',
        headers: {
          'X-CSRFToken': getCookie('csrftoken')
        },
        body: formData
      })
      .then(async response => {
        const contentType = response.headers.get('content-type');
        if (contentType && contentType.includes('application/json')) {
          const data = await response.json();
          if (!response.ok) {
            throw new Error(data.error || 'Server returned an error');
          }
          return data;
        } else {
          throw new Error('Server returned an invalid response. Please try again or contact support.');
        }
      })
      .then(data => {
        alert('New HC Claim started. The selected invoices have been associated.');
        location.reload();
      })
      .catch(err => {
        console.error('Error:', err);
        alert('Error: ' + err.message);
      });
      
    });
  }

});
