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
});
