var total_claims_array=[];

document.addEventListener('DOMContentLoaded', function() {
    var modal = document.createElement('div');
    console.log("claims are: "+claims);
    console.log("claims are: " + JSON.stringify(claims));
    modal.innerHTML = `
    <div id="myModal" style="display: none; position: fixed; z-index: 1; left: 0; top: 0; width: 100%; height: 100%; overflow: auto; background-color: rgba(0,0,0,0.4);">
      <div style="background-color: #fefefe; margin: auto; padding: 20px; border: 1px solid #888; width: 50%; height: 50%; position: absolute; top: 0; left: 0; bottom: 0; right: 0;">
        <div>
          <h5>Existing Claims</h5>
        </div>
        <div>
          <table style="width:100%; border-collapse: collapse;">
            <thead>
                <tr style="height: 20px; position: sticky; top: 0;">
                    <th style="position: sticky; top: 20px;">Claim</th>
                    <th style="position: sticky; top: 20px;">Supplier</th>
                    <th style="position: sticky; top: 20px;">Total</th>
                    <th style="position: sticky; top: 20px;">In Xero?</th>
                </tr>
            </thead>
            <tbody>
                ${claims.map(claim => `
                    <tr>
                        <td>${claim.claim}</td>
                        <td>${claim.supplier_name}</td>
                        <td>${claim.total}</td>
                        <td>${claim.sent_to_xero ? '<span style="color:green;">✔</span>' : '<input type="checkbox" />'}</td>
                    </tr>
                `).join('')}
            </tbody>
          </table>
          </div>
          <div class="modal-footer" style="display: flex; justify-content: space-between;">
            <button type="button" id="closeModalBtn" class="btn btn-secondary" data-dismiss="modal">Close</button>
            <button type="button" id="sendToXeroBtn" class="btn btn-primary" data-dismiss="modal">Send to Xero</button>
        </div>
        </div>
      </div>
    `;

    document.body.appendChild(modal);
    var myModal = document.getElementById("myModal");

    document.getElementById('dropdown2').addEventListener('change', function() {
        if (this.value === 'committedClaims') {
            myModal.style.display = "block";
        }
    });

    document.getElementById("closeModalBtn").addEventListener('click', function() {
        myModal.style.display = "none";
    })

});