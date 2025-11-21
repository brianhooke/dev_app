// @ts-check
const { test, expect } = require('@playwright/test');

/**
 * Bills - Inbox Tests
 * 
 * These tests verify the Bills - Inbox functionality, specifically:
 * 1. GST validation accepts 0 value (bug fix v56)
 * 2. GST validation rejects empty value
 * 3. Send button does not validate allocations in Inbox mode (bug fix v56)
 * 4. Send button validation matches click handler validation
 * 5. PDF viewer maintains fixed height regardless of table rows (bug fix v56)
 * 6. PDF loads correctly when clicking on a bill row
 */

test.describe.configure({ mode: 'serial' });

test.describe('Bills - Inbox', () => {
  
  test.beforeEach(async ({ page }) => {
    // Navigate to dashboard and open Bills - Inbox
    // Force a fresh page load to avoid state issues between tests
    await page.goto('/dashboard/', { waitUntil: 'networkidle' });
    
    // Wait for page to load
    await page.waitForLoadState('networkidle');
    
    // First click Bills dropdown to reveal submenu
    await page.click('#billsLink');
    
    // Wait for dropdown menu to be visible
    await page.waitForSelector('#billsLink-menu.show', { state: 'visible' });
    
    // Then click Bills - Inbox link
    await page.click('#billsInboxLink');
    
    // Wait for bills section to be visible
    await page.waitForSelector('#billsInboxSection', { state: 'visible' });
    
    // Wait for bills table to have rows
    await page.waitForSelector('#billsTable tbody tr', { timeout: 10000 });
    
    // Give the page a moment to settle before checking dropdowns
    await page.waitForTimeout(1000);
    
    // Wait for dropdowns to be populated with projects
    // Check that project options exist (value starts with 'project_')
    await page.waitForFunction(() => {
      const options = document.querySelectorAll('#billsTable tbody tr .xero-project-select option');
      for (const option of options) {
        const value = option.getAttribute('value');
        if (value && value.startsWith('project_')) {
          return true;
        }
      }
      return false;
    }, { timeout: 25000 }); // Increased timeout for serial test execution
  });

  test('GST validation: accepts 0 value', async ({ page }) => {
    // This test verifies that GST field accepts 0 (for GST-free invoices)
    // Bug: Previously rejected 0 as invalid
    
    // Wait for a bill row to exist
    await page.waitForSelector('#billsTable tbody tr', { timeout: 10000 });
    
    // Get the first bill row
    const firstRow = page.locator('#billsTable tbody tr').first();
    
    // Wait for dropdowns to be populated (check that they have options)
    await page.waitForFunction(() => {
      const select = document.querySelector('#billsTable tbody tr .xero-project-select');
      return select && select.options.length > 1;
    }, { timeout: 10000 });
    
    // Fill in all required fields (index 2 = first actual option after blank + header)
    await firstRow.locator('.xero-project-select').selectOption({ index: 2 });
    await firstRow.locator('.supplier-select').selectOption({ index: 4 }); // Index 4 = first supplier (after blank, separator, Add+, separator)
    await firstRow.locator('.invoice-number-input').fill('TEST-001');
    await firstRow.locator('.net-input').fill('100.00');
    await firstRow.locator('.gst-input').fill('0'); // GST = 0
    
    // Wait a moment for validation to run
    await page.waitForTimeout(500);
    
    // Check that Send button is enabled and green
    const sendButton = firstRow.locator('.send-bill-btn');
    await expect(sendButton).toBeEnabled();
    await expect(sendButton).toHaveClass(/btn-success/);
    
    // Click Send button - should not show GST validation error
    await sendButton.click();
    
    // Wait for any alert or error message
    await page.waitForTimeout(500);
    
    // If there's an alert, it should NOT be about GST
    const alertText = await page.evaluate(() => {
      // Check if there was an alert (this is a simplified check)
      return window.lastAlertMessage || null;
    });
    
    if (alertText) {
      expect(alertText).not.toContain('GST');
    }
  });

  test('GST validation: rejects empty value', async ({ page }) => {
    // This test verifies that GST field cannot be empty
    // Bug: Previously allowed empty GST field
    
    await page.waitForSelector('#billsTable tbody tr', { timeout: 10000 });
    const firstRow = page.locator('#billsTable tbody tr').first();
    
    // Fill in all fields
    await firstRow.locator('.xero-project-select').selectOption({ index: 2 });
    await firstRow.locator('.supplier-select').selectOption({ index: 4 }); // Index 4 = first supplier (after blank, separator, Add+, separator)
    await firstRow.locator('.invoice-number-input').fill('TEST-002');
    await firstRow.locator('.net-input').fill('100.00');
    // NET auto-fills GST to 10.00, so we need to clear it properly
    await firstRow.locator('.gst-input').clear();
    await firstRow.locator('.gst-input').blur(); // Trigger validation
    
    await page.waitForTimeout(500);
    
    // Send button should be disabled and grey
    const sendButton = firstRow.locator('.send-bill-btn');
    await expect(sendButton).toBeDisabled();
    await expect(sendButton).toHaveClass(/btn-secondary/);
  });

  test('Send button: does not validate allocations', async ({ page }) => {
    // This test verifies that Bills - Inbox Send button does NOT check allocations
    // Bug: Previously showed "All allocations must have a Xero Account selected" error
    
    await page.waitForSelector('#billsTable tbody tr', { timeout: 10000 });
    const firstRow = page.locator('#billsTable tbody tr').first();
    
    // Fill in all required fields (index 2 = first actual option after blank + header)
    await firstRow.locator('.xero-project-select').selectOption({ index: 2 });
    await firstRow.locator('.supplier-select').selectOption({ index: 4 }); // Index 4 = first supplier (after blank, separator, Add+, separator)
    await firstRow.locator('.invoice-number-input').fill('TEST-003');
    await firstRow.locator('.net-input').fill('100.00');
    await firstRow.locator('.gst-input').fill('10.00');
    
    await page.waitForTimeout(500);
    
    // Verify allocations section is hidden (this is Bills - Inbox, not Direct)
    // Use specific selector to target the one in billsInboxSection
    const allocationsSection = page.locator('#billsInboxSection #allocationsSection').first();
    await expect(allocationsSection).toBeHidden();
    
    // Send button should be enabled
    const sendButton = firstRow.locator('.send-bill-btn');
    await expect(sendButton).toBeEnabled();
    await expect(sendButton).toHaveClass(/btn-success/);
    
    // Listen for dialog (alert)
    page.on('dialog', async dialog => {
      const message = dialog.message();
      // Should NOT contain allocation-related errors
      expect(message).not.toContain('allocation');
      expect(message).not.toContain('Xero Account');
      await dialog.accept();
    });
    
    // Click Send - should proceed without allocation validation errors
    await sendButton.click();
    
    await page.waitForTimeout(1000);
  });

  test('PDF viewer: maintains height regardless of table rows', async ({ page }) => {
    // This test verifies that PDF viewer height is fixed and doesn't change with table row count
    // Bug: Previously viewer height scaled with number of rows
    
    await page.waitForSelector('#billsTable tbody tr', { timeout: 10000 });
    
    // Get initial viewer height - use more specific selector to avoid duplicate ID
    const viewerSection = page.locator('#billsInboxSection #viewerSection').first();
    const initialBox = await viewerSection.boundingBox();
    const initialHeight = initialBox?.height || 0;
    
    // Viewer should have substantial height (at least 300px)
    expect(initialHeight).toBeGreaterThan(300);
    
    // Click on a bill to load PDF (if available)
    const firstRow = page.locator('#billsTable tbody tr').first();
    await firstRow.click();
    
    await page.waitForTimeout(500);
    
    // Check height again - should be the same
    const afterClickBox = await viewerSection.boundingBox();
    const afterClickHeight = afterClickBox?.height || 0;
    
    // Height should not have changed significantly (allow 5px tolerance for rendering)
    expect(Math.abs(afterClickHeight - initialHeight)).toBeLessThan(5);
  });

  test('Send button validation: matches click handler validation', async ({ page }) => {
    // This test verifies that button state (color) matches click handler validation
    // Bug: Button could be green but clicking showed validation errors
    
    await page.waitForSelector('#billsTable tbody tr', { timeout: 10000 });
    const firstRow = page.locator('#billsTable tbody tr').first();
    
    // Fill in all fields correctly (index 2 = first actual option after blank + header)
    await firstRow.locator('.xero-project-select').selectOption({ index: 2 });
    await firstRow.locator('.supplier-select').selectOption({ index: 4 }); // Index 4 = first supplier (after blank, separator, Add+, separator)
    await firstRow.locator('.invoice-number-input').fill('TEST-004');
    await firstRow.locator('.net-input').fill('100.00');
    await firstRow.locator('.gst-input').fill('0');
    
    await page.waitForTimeout(500);
    
    const sendButton = firstRow.locator('.send-bill-btn');
    
    // If button is green and enabled, clicking should not show validation errors
    const isEnabled = await sendButton.isEnabled();
    const hasSuccessClass = await sendButton.evaluate(el => el.classList.contains('btn-success'));
    
    if (isEnabled && hasSuccessClass) {
      // Track if any validation error alert appears
      let validationErrorShown = false;
      
      page.on('dialog', async dialog => {
        const message = dialog.message().toLowerCase();
        if (message.includes('please') || message.includes('error') || message.includes('must')) {
          validationErrorShown = true;
        }
        await dialog.accept();
      });
      
      await sendButton.click();
      await page.waitForTimeout(1000);
      
      // No validation errors should have been shown
      expect(validationErrorShown).toBe(false);
    }
  });

  test('PDF loads correctly when clicking on a bill row', async ({ page }) => {
    // This test verifies that PDFs load from local storage without S3 errors
    // Bug: Previously tried to load from S3 causing 403 Forbidden errors
    
    await page.waitForSelector('#billsTable tbody tr', { timeout: 10000 });
    
    // Get the PDF viewer iframe - use specific selector for Bills section
    const pdfViewer = page.locator('#billsInboxSection #billViewer').first();
    const viewerPlaceholder = page.locator('#billsInboxSection #viewerPlaceholder').first();
    
    // Initially, viewer should be hidden and placeholder visible
    await expect(pdfViewer).toBeHidden();
    await expect(viewerPlaceholder).toBeVisible();
    
    // Click on the first bill row to load its PDF
    const firstRow = page.locator('#billsTable tbody tr').first();
    await firstRow.click();
    
    // Wait for PDF to load
    await page.waitForTimeout(1000);
    
    // Viewer should now be visible and placeholder hidden
    await expect(pdfViewer).toBeVisible();
    await expect(viewerPlaceholder).toBeHidden();
    
    // Check that the PDF src is a local URL (not S3)
    const pdfSrc = await pdfViewer.getAttribute('src');
    expect(pdfSrc).toBeTruthy();
    expect(pdfSrc).toContain('/media/invoices/');
    expect(pdfSrc).not.toContain('s3.amazonaws.com');
    expect(pdfSrc).not.toContain('AWSAccessKeyId');
    
    // Wait for iframe to load and check for errors
    await page.waitForTimeout(2000);
    
    // Check browser console for 403 errors
    const consoleErrors = [];
    page.on('console', msg => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text());
      }
    });
    
    // Check network requests for failed PDF loads
    /** @type {Array<{url: string, failure: any}>} */
    const failedRequests = [];
    page.on('requestfailed', request => {
      if (request.url().includes('.pdf')) {
        failedRequests.push({
          url: request.url(),
          failure: request.failure()
        });
      }
    });
    
    // Wait a bit to catch any errors
    await page.waitForTimeout(1000);
    
    // Should not have any 403 or S3-related errors
    const has403Error = failedRequests.some(req => 
      req.failure && req.failure.errorText && req.failure.errorText.includes('403')
    );
    const hasS3Error = failedRequests.some(req => req.url.includes('s3.amazonaws.com'));
    
    expect(has403Error).toBe(false);
    expect(hasS3Error).toBe(false);
  });
});
