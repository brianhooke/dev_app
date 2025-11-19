// @ts-check
const { test, expect } = require('@playwright/test');

/**
 * Bills - Inbox Tests
 * 
 * These tests verify the Bills - Inbox functionality to prevent regressions.
 * Tests cover the bugs fixed in v56.
 */

test.describe('Bills - Inbox', () => {
  
  test.beforeEach(async ({ page }) => {
    // Navigate to dashboard and open Bills - Inbox
    await page.goto('/dashboard/');
    
    // Wait for page to load
    await page.waitForLoadState('networkidle');
    
    // Click Bills - Inbox link
    await page.click('#billsInboxLink');
    
    // Wait for bills section to be visible
    await page.waitForSelector('#billsInboxSection', { state: 'visible' });
  });

  test('GST validation: accepts 0 value', async ({ page }) => {
    // This test verifies that GST field accepts 0 (for GST-free invoices)
    // Bug: Previously rejected 0 as invalid
    
    // Wait for a bill row to exist
    await page.waitForSelector('#billsTable tbody tr', { timeout: 10000 });
    
    // Get the first bill row
    const firstRow = page.locator('#billsTable tbody tr').first();
    
    // Fill in all required fields
    await firstRow.locator('.xero-project-select').selectOption({ index: 1 });
    await firstRow.locator('.supplier-select').selectOption({ index: 1 });
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
    
    // Fill in all fields except GST
    await firstRow.locator('.xero-project-select').selectOption({ index: 1 });
    await firstRow.locator('.supplier-select').selectOption({ index: 1 });
    await firstRow.locator('.invoice-number-input').fill('TEST-002');
    await firstRow.locator('.net-input').fill('100.00');
    await firstRow.locator('.gst-input').fill(''); // Empty GST
    
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
    
    // Fill in all required fields
    await firstRow.locator('.xero-project-select').selectOption({ index: 1 });
    await firstRow.locator('.supplier-select').selectOption({ index: 1 });
    await firstRow.locator('.invoice-number-input').fill('TEST-003');
    await firstRow.locator('.net-input').fill('100.00');
    await firstRow.locator('.gst-input').fill('10.00');
    
    await page.waitForTimeout(500);
    
    // Verify allocations section is hidden (this is Bills - Inbox, not Direct)
    const allocationsSection = page.locator('#allocationsSection');
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
    
    // Get initial viewer height
    const viewerSection = page.locator('#viewerSection');
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
    
    // Fill in all fields correctly
    await firstRow.locator('.xero-project-select').selectOption({ index: 1 });
    await firstRow.locator('.supplier-select').selectOption({ index: 1 });
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
});
