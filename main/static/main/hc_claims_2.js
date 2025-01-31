// Existing HC Claims Modal

document.addEventListener('DOMContentLoaded', function() {
  // 1) If user chooses "existingClaims" in #hcDropdown => show #existingClaimsModal
  const hcDropdown = document.getElementById('hcDropdown');
  if (hcDropdown) {
    hcDropdown.addEventListener('change', function(e) {
      if (e.target.value === 'existingClaims') {
        $('#existingClaimsModal').modal('show');
      }
    });
  }

  // 2) If there's a "claimsDropdownInvoices" that triggers #unallocatedInvoicesModal (optional use-case)
  const claimsDropdown = document.getElementById('claimsDropdownInvoices');
  if (claimsDropdown) {
    claimsDropdown.addEventListener('change', function(e) {
      if (e.target.value === 'existingClaims') {
        $('#unallocatedInvoicesModal').modal('show');
      }
    });
  }

  // 3) “Preview” links => shows an inline placeholder or message in the #existingClaimsPdfViewer
  document.querySelectorAll('.preview-table-link').forEach(function(element) {
    element.addEventListener('click', function(event) {
      event.preventDefault();
      let claimId = this.getAttribute('data-preview-claim-id');
      let iframe = document.getElementById('existingClaimsPdfViewer');
      if (iframe && claimId) {
        // For demonstration, show some placeholder text in the iframe
        iframe.contentDocument.body.innerHTML = `
          <div style="font-size: medium; text-align: center; margin-top: 2rem;">
            You clicked on HC Claim #${claimId} (PREVIEW)
          </div>`;
      }
      // Show the existingClaimsModal
      $('#existingClaimsModal').modal('show');
    });
  });

  // 4) “View” links => load the real claim PDF or table into #existingClaimsPdfViewer
  document.querySelectorAll('.view-table-link').forEach(function(element) {
    element.addEventListener('click', function(event) {
      event.preventDefault();
      let claimId = this.getAttribute('data-view-claim-id');
      let iframe = document.getElementById('existingClaimsPdfViewer');
      if (iframe && claimId) {
        // Example: load a claim table or PDF from your server
        // e.g. /get_claim_table/<claimId> or /some_pdf/<claimId>
        iframe.src = '/get_claim_table/' + claimId + '/';
      }
      $('#existingClaimsModal').modal('show');
    });
  });

  // 5) Optionally, you might also have a generic “.view-pdf-link” approach
  //    If so, uncomment or adapt the snippet below:
  /*
  let pdfLinks = document.querySelectorAll('.view-pdf-link');
  pdfLinks.forEach(function(link) {
    link.addEventListener('click', function(event) {
      event.preventDefault();
      let claimId = this.getAttribute('data-claim-id');
      if (claimId) {
        let iframe = document.getElementById('existingClaimsPdfViewer');
        if (iframe) {
          iframe.src = '/get_claim_table/' + claimId + '/';
        }
        $('#existingClaimsModal').modal('show');
      } else {
        alert('Invalid claim ID.');
      }
    });
  });
  */
});
