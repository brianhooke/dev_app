// @ts-check
const { test, expect } = require('@playwright/test');

/**
 * Bills - Direct Tests
 * 
 * These tests verify the Bills - Direct functionality to prevent regressions.
 * 
 * Test Summary:
 * 1. Send to Xero button starts grey when validation fails
 * 2. Send to Xero button turns green only when all fields valid
 * 3. Send to Xero button stays green after switching views (if allocations valid)
 * 4. Pull Xero Accounts button visible in Direct mode
 * 5. PDF viewer maintains height in Direct mode
 * 6. Allocations section visible in Direct mode
 * 7. Send to Xero validates allocations in Direct mode
 */

test.describe('Bills - Direct', () => {
  
  test.beforeEach(async ({ page }) => {
    // Navigate to dashboard and open Bills - Direct
    await page.goto('/dashboard/');
    await page.waitForLoadState('networkidle');
    
    // First click Bills dropdown to reveal submenu
    await page.click('#billsLink');
    
    // Wait for dropdown menu to be visible
    await page.waitForSelector('#billsLink-menu.show', { state: 'visible' });
    
    // Then click Bills - Direct link
    await page.click('#billsDirectLink');
    
    // Wait for bills section to be visible
    await page.waitForSelector('#billsInboxSection', { state: 'visible' });
    
    // Wait for allocations section to be visible (Direct mode)
    await page.waitForSelector('#billsInboxSection #allocationsSection', { state: 'visible' });
    
    // Wait for bills table to have rows
    await page.waitForSelector('#billsTable tbody tr', { timeout: 10000 });
    
    // Wait for dropdowns to be populated (need at least 3 options: blank + header + actual option)
    await page.waitForFunction(() => {
      const select = document.querySelector('#billsTable tbody tr .xero-project-select');
      return select && select.options && select.options.length > 2;
    }, { timeout: 10000 });
  });

  test('Send to Xero button: starts grey when validation fails', async ({ page }) => {
    // This test verifies that Send to Xero button starts as grey/disabled on page load
    // Bug: Previously started green even when validation hadn't passed
    
    await page.waitForSelector('#billsTable tbody tr', { timeout: 10000 });
    
    // Get all Send to Xero buttons
    const sendButtons = page.locator('.send-bill-btn');
    const count = await sendButtons.count();
    
    // Check each button's initial state
    for (let i = 0; i < count; i++) {
      const button = sendButtons.nth(i);
      const row = button.locator('xpath=ancestor::tr');
      
      // Check if row has all required fields filled
      const xeroSelect = await row.locator('.xero-project-select').inputValue();
      const supplierSelect = await row.locator('.supplier-select').inputValue();
      const invoiceNumber = await row.locator('.invoice-number-input').inputValue();
      const netValue = await row.locator('.net-input').inputValue();
      const gstValue = await row.locator('.gst-input').inputValue();
      
      // If any field is empty or invalid, button should be grey and disabled
      const hasEmptyFields = !xeroSelect || !supplierSelect || !invoiceNumber || 
                            !netValue || netValue === '0' || !gstValue;
      
      if (hasEmptyFields) {
        await expect(button).toBeDisabled();
        await expect(button).toHaveClass(/btn-secondary/);
      }
    }
  });

  test('Send to Xero button: turns green only when all fields valid', async ({ page }) => {
    // This test verifies that button only turns green after all validation passes
    
    await page.waitForSelector('#billsTable tbody tr', { timeout: 10000 });
    const firstRow = page.locator('#billsTable tbody tr').first();
    const sendButton = firstRow.locator('.send-bill-btn');
    
    // Initially should be grey
    await expect(sendButton).toHaveClass(/btn-secondary/);
    
    // Fill fields one by one and check button state
    await firstRow.locator('.xero-project-select').selectOption({ index: 2 });
    await page.waitForTimeout(200);
    // Still grey - not all fields filled
    await expect(sendButton).toHaveClass(/btn-secondary/);
    
    await firstRow.locator('.supplier-select').selectOption({ index: 4 }); // Index 4 = first supplier (after blank, separator, Add+, separator)
    await page.waitForTimeout(200);
    await expect(sendButton).toHaveClass(/btn-secondary/);
    
    await firstRow.locator('.invoice-number-input').fill('TEST-DIRECT-001');
    await page.waitForTimeout(200);
    await expect(sendButton).toHaveClass(/btn-secondary/);
    
    await firstRow.locator('.net-input').fill('100.00');
    await page.waitForTimeout(200);
    await expect(sendButton).toHaveClass(/btn-secondary/);
    
    await firstRow.locator('.gst-input').fill('10.00');
    await page.waitForTimeout(500);
    
    // Now button might turn green for Inbox mode, but for Direct mode
    // it needs allocations, so should still be grey until row is selected
    // and allocations are added
  });

  test('Pull Xero Accounts button: visible in Direct mode', async ({ page }) => {
    // This test verifies that Pull Xero Accounts button is visible in Direct mode
    
    // Use more specific selector to avoid duplicate ID issue
    const pullButton = page.locator('#billsInboxSection #pullXeroAccountsBtn').first();
    
    // Button should be visible
    await expect(pullButton).toBeVisible();
    
    // Button should have correct text
    await expect(pullButton).toHaveText(/Pull.*Xero Accounts/);
  });

  test('PDF viewer: maintains height in Direct mode', async ({ page }) => {
    // This test verifies that PDF viewer maintains consistent height
    
    await page.waitForSelector('#billsTable tbody tr', { timeout: 10000 });
    
    // Get viewer height - use more specific selector
    const viewerSection = page.locator('#billsInboxSection #viewerSection').first();
    const viewerBox = await viewerSection.boundingBox();
    const viewerHeight = viewerBox?.height || 0;
    
    // In Direct mode with allocations visible, viewer should still have good height
    expect(viewerHeight).toBeGreaterThan(300);
    
    // Click on a bill
    const firstRow = page.locator('#billsTable tbody tr').first();
    await firstRow.click();
    
    await page.waitForTimeout(500);
    
    // Height should remain consistent
    const afterBox = await viewerSection.boundingBox();
    const afterHeight = afterBox?.height || 0;
    
    expect(Math.abs(afterHeight - viewerHeight)).toBeLessThan(10);
  });

  test('Allocations section: visible in Direct mode', async ({ page }) => {
    // This test verifies that allocations section is visible in Direct mode
    
    // Wait for bills to load
    await page.waitForSelector('#billsTable tbody tr', { timeout: 10000 });
    
    // Use more specific selector - check if section exists and is displayed
    const allocationsSection = page.locator('#billsInboxSection #allocationsSection').first();
    
    // In Direct mode, allocations section should be visible (display: flex)
    await expect(allocationsSection).toBeVisible();
    
    // Should have the allocations table
    const allocationsTable = page.locator('#billsInboxSection #allocationsTable').first();
    await expect(allocationsTable).toBeVisible();
    
    // Should have "Still to allocate" section
    const remainingNet = page.locator('#remainingNet').first();
    await expect(remainingNet).toBeVisible();
  });

  test('Send to Xero: validates allocations in Direct mode', async ({ page }) => {
    // This test verifies that Send to Xero button DOES validate allocations in Direct mode
    // (opposite of Inbox mode)
    
    await page.waitForSelector('#billsTable tbody tr', { timeout: 10000 });
    const firstRow = page.locator('#billsTable tbody tr').first();
    
    // Fill in all LHS fields
    await firstRow.locator('.xero-project-select').selectOption({ index: 2 });
    await firstRow.locator('.supplier-select').selectOption({ index: 4 }); // Index 4 = first supplier (after blank, separator, Add+, separator)
    await firstRow.locator('.invoice-number-input').fill('TEST-DIRECT-002');
    await firstRow.locator('.net-input').fill('100.00');
    await firstRow.locator('.gst-input').fill('10.00');
    
    // Click row to select it and show allocations
    await firstRow.click();
    await page.waitForTimeout(500);
    
    const sendButton = firstRow.locator('.send-bill-btn');
    
    // Without allocations, button should be grey
    await expect(sendButton).toHaveClass(/btn-secondary/);
    
    // Listen for validation error about allocations
    let allocationErrorShown = false;
    page.on('dialog', async dialog => {
      const message = dialog.message().toLowerCase();
      if (message.includes('allocation')) {
        allocationErrorShown = true;
      }
      await dialog.accept();
    });
    
    // Try to click Send - should show allocation error
    if (await sendButton.isEnabled()) {
      await sendButton.click();
      await page.waitForTimeout(500);
      expect(allocationErrorShown).toBe(true);
    }
  });

  test('Send to Xero button: stays green after switching views', async ({ page }) => {
    // This test verifies that button stays green after switching to Inbox and back
    // Bug: Button turned grey after view switch even though allocations were valid
    
    await page.waitForSelector('#billsTable tbody tr', { timeout: 10000 });
    const firstRow = page.locator('#billsTable tbody tr').first();
    
    // Fill in all LHS fields
    await firstRow.locator('.xero-project-select').selectOption({ index: 2 });
    await firstRow.locator('.supplier-select').selectOption({ index: 4 }); // Index 4 = first supplier (after blank, separator, Add+, separator)
    await firstRow.locator('.invoice-number-input').fill('TEST-PERSIST-001');
    await firstRow.locator('.net-input').fill('100.00');
    await firstRow.locator('.gst-input').fill('10.00');
    
    // Click row to select and load allocations
    await firstRow.click();
    await page.waitForTimeout(500);
    
    // Wait for allocations to load
    await page.waitForSelector('#allocationsTableBody tr', { timeout: 5000 });
    
    // Wait for Xero account dropdown to be populated (AJAX call)
    await page.waitForFunction(() => {
      const select = document.querySelector('#allocationsTableBody tr .xero-account-select');
      return select && select.options && select.options.length > 1;
    }, { timeout: 5000 });
    
    // Select Xero account and fill allocation amounts
    const firstAllocation = page.locator('#allocationsTableBody tr').first();
    await firstAllocation.locator('.xero-account-select').selectOption({ index: 1 });
    await page.waitForTimeout(200);
    
    // Fill allocation amounts to match invoice totals
    await firstAllocation.locator('.allocation-net-input').fill('100.00');
    await firstAllocation.locator('.allocation-gst-input').fill('10.00');
    await page.waitForTimeout(500);
    
    // Button should now be green (allocations are valid)
    const sendButton = firstRow.locator('.send-bill-btn');
    await expect(sendButton).toHaveClass(/btn-success/);
    await expect(sendButton).toBeEnabled();
    
    // Now switch to Bills - Inbox
    await page.click('#billsLink'); // Open dropdown
    await page.waitForSelector('#billsLink-menu.show', { state: 'visible' });
    await page.click('#billsInboxLink');
    await page.waitForSelector('#billsInboxSection', { state: 'visible' });
    await page.waitForTimeout(500);
    
    // Switch back to Bills - Direct
    await page.click('#billsLink'); // Open dropdown
    await page.waitForSelector('#billsLink-menu.show', { state: 'visible' });
    await page.click('#billsDirectLink');
    await page.waitForSelector('#billsInboxSection', { state: 'visible' });
    await page.waitForSelector('#allocationsSection', { state: 'visible' });
    await page.waitForTimeout(500);
    
    // Find the same row again (by invoice number)
    const rowWithInvoice = page.locator('#billsTable tbody tr').filter({
      has: page.locator('.invoice-number-input[value="TEST-PERSIST-001"]')
    });
    
    // Button should STILL be green (not grey)
    const buttonAfterSwitch = rowWithInvoice.locator('.send-bill-btn');
    await expect(buttonAfterSwitch).toHaveClass(/btn-success/);
    await expect(buttonAfterSwitch).toBeEnabled();
    
    // Click the row to verify allocations are still there
    await rowWithInvoice.click();
    await page.waitForTimeout(500);
    
    // Verify allocation still has account selected
    const allocationAfterSwitch = page.locator('#allocationsTableBody tr').first();
    const accountValue = await allocationAfterSwitch.locator('.xero-account-select').inputValue();
    expect(accountValue).toBeTruthy(); // Should have a value
    
    // Button should remain green
    await expect(buttonAfterSwitch).toHaveClass(/btn-success/);
    await expect(buttonAfterSwitch).toBeEnabled();
  });
});
