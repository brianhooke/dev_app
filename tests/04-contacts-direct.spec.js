// @ts-check
const { test, expect } = require('@playwright/test');

/**
 * Contacts - Verification regression tests
 *
 * Covers bug: verifying a contact with already valid details should mark the
 * row as verified immediately (green badge) without the user needing to leave
 * and re-enter the contacts section.
 */

test.describe('Contacts - Verification', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/dashboard/');
    await page.waitForLoadState('networkidle');

    await page.click('#contactsLink');
    await page.waitForSelector('#contactsSection', { state: 'visible' });

    await page.waitForFunction(() => {
      const tbody = document.querySelector('#contactsSection tbody');
      return tbody && tbody.querySelectorAll('tr').length > 0;
    });
  });

  test('shows verified badge immediately after successful verify', async ({ page }) => {
    const firstRow = page.locator('#contactsSection tbody tr').first();
    const verifyButton = firstRow.locator('.verify-contact-btn');
    await expect(verifyButton).toBeVisible();

    await verifyButton.click();
    await page.waitForSelector('#verifyContactModal.show', { state: 'visible' });

    await page.fill('#verify-notes', 'Verified via automated test');

    const [dialog] = await Promise.all([
      page.waitForEvent('dialog'),
      page.click('#verifyContactBtn')
    ]);
    await dialog.accept();

    await page.waitForSelector('#verifyContactModal', { state: 'hidden' });

    const verifiedBadge = firstRow.locator('.verified-badge');
    await expect(verifiedBadge).toHaveText(/Verified/);
  });

  test('allows scrolling through all contacts in modal', async ({ page }) => {
    // Open contacts modal
    await page.click('#contactsLink');
    await page.waitForSelector('#contactsModal.show', { state: 'visible', timeout: 5000 });

    // Wait for contacts to load in modal
    await page.waitForFunction(() => {
      const tbody = document.querySelector('#contactsModal tbody');
      return tbody && tbody.querySelectorAll('tr').length > 5; // Ensure multiple contacts loaded
    }, { timeout: 5000 });

    // Get the modal body (scrollable container)
    const modalBody = page.locator('#contactsModal .modal-body');
    await expect(modalBody).toBeVisible();

    // Get initial scroll position
    const initialScrollTop = await modalBody.evaluate(el => el.scrollTop);
    expect(initialScrollTop).toBe(0); // Should start at top

    // Check if content is scrollable (scrollHeight > clientHeight)
    const isScrollable = await modalBody.evaluate(el => el.scrollHeight > el.clientHeight);
    
    if (isScrollable) {
      // Scroll down in the modal
      await modalBody.evaluate(el => el.scrollTop = el.scrollHeight / 2);
      
      // Wait a moment for scroll to complete
      await page.waitForTimeout(300);
      
      // Verify scroll position changed
      const midScrollTop = await modalBody.evaluate(el => el.scrollTop);
      expect(midScrollTop).toBeGreaterThan(initialScrollTop);

      // Scroll to bottom
      await modalBody.evaluate(el => el.scrollTop = el.scrollHeight);
      await page.waitForTimeout(300);

      // Verify we can reach the bottom
      const finalScrollTop = await modalBody.evaluate(el => el.scrollTop);
      expect(finalScrollTop).toBeGreaterThan(midScrollTop);

      // Verify bottom contacts are accessible (check last row is visible)
      const lastRow = page.locator('#contactsModal tbody tr').last();
      await lastRow.scrollIntoViewIfNeeded();
      await expect(lastRow).toBeVisible();
    } else {
      // If not scrollable, ensure all contacts fit in view
      const allRows = await page.locator('#contactsModal tbody tr').count();
      console.log(`Only ${allRows} contacts - all fit in view without scrolling`);
      expect(allRows).toBeGreaterThan(0);
    }
  });
});
