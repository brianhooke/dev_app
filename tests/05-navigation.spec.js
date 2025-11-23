/**
 * Navigation E2E Tests
 * 
 * Tests for the universal section hiding and navigation between workspace sections
 * These tests validate the fixes for navigation issues where sections were stacking
 * instead of replacing each other.
 */

const { test, expect } = require('@playwright/test');

test.describe('Navigation - Section Hiding', () => {
    test.beforeEach(async ({ page }) => {
        // Login
        await page.goto('http://127.0.0.1:8000/login/');
        await page.fill('input[name="username"]', 'testuser');
        await page.fill('input[name="password"]', 'testpass123');
        await page.click('button[type="submit"]');
        await page.waitForURL('**/dashboard/');
    });

    test('should show only Dashboard (empty state) on initial load', async ({ page }) => {
        // Should show empty state
        await expect(page.locator('#emptyState')).toBeVisible();
        
        // All sections should be hidden
        await expect(page.locator('#projectsSection')).not.toBeVisible();
        await expect(page.locator('#billsInboxSection')).not.toBeVisible();
        await expect(page.locator('#contactsSection')).not.toBeVisible();
        await expect(page.locator('#xeroSection')).not.toBeVisible();
    });

    test('should hide empty state when navigating to Projects', async ({ page }) => {
        await page.click('#projectsLink');
        await page.waitForTimeout(500);
        
        // Projects should be visible
        await expect(page.locator('#projectsSection')).toBeVisible();
        
        // Empty state should be hidden
        await expect(page.locator('#emptyState')).not.toBeVisible();
        
        // Other sections should be hidden
        await expect(page.locator('#billsInboxSection')).not.toBeVisible();
        await expect(page.locator('#contactsSection')).not.toBeVisible();
        await expect(page.locator('#xeroSection')).not.toBeVisible();
    });

    test('should hide Projects when navigating to Bills - Inbox', async ({ page }) => {
        // First go to Projects
        await page.click('#projectsLink');
        await page.waitForTimeout(500);
        await expect(page.locator('#projectsSection')).toBeVisible();
        
        // Then go to Bills - Inbox
        await page.click('#billsInboxLink');
        await page.waitForTimeout(1000);
        
        // Bills should be visible
        await expect(page.locator('#billsInboxSection')).toBeVisible();
        
        // Projects should be hidden
        await expect(page.locator('#projectsSection')).not.toBeVisible();
        
        // Other sections should be hidden
        await expect(page.locator('#contactsSection')).not.toBeVisible();
        await expect(page.locator('#xeroSection')).not.toBeVisible();
    });

    test('should hide Bills when navigating to Contacts', async ({ page }) => {
        // First go to Bills
        await page.click('#billsInboxLink');
        await page.waitForTimeout(1000);
        await expect(page.locator('#billsInboxSection')).toBeVisible();
        
        // Then go to Contacts
        await page.click('#contactsLink');
        await page.waitForTimeout(500);
        
        // Contacts should be visible
        await expect(page.locator('#contactsSection')).toBeVisible();
        
        // Bills should be hidden
        await expect(page.locator('#billsInboxSection')).not.toBeVisible();
        
        // Other sections should be hidden
        await expect(page.locator('#projectsSection')).not.toBeVisible();
        await expect(page.locator('#xeroSection')).not.toBeVisible();
    });

    test('should hide Contacts when navigating to Xero', async ({ page }) => {
        // First go to Contacts
        await page.click('#contactsLink');
        await page.waitForTimeout(500);
        await expect(page.locator('#contactsSection')).toBeVisible();
        
        // Then go to Xero
        await page.click('#xeroLink');
        await page.waitForTimeout(500);
        
        // Xero should be visible
        await expect(page.locator('#xeroSection')).toBeVisible();
        
        // Contacts should be hidden
        await expect(page.locator('#contactsSection')).not.toBeVisible();
        
        // Other sections should be hidden
        await expect(page.locator('#projectsSection')).not.toBeVisible();
        await expect(page.locator('#billsInboxSection')).not.toBeVisible();
    });

    test('should hide all sections when clicking Dashboard', async ({ page }) => {
        // Navigate to Projects
        await page.click('#projectsLink');
        await page.waitForTimeout(500);
        await expect(page.locator('#projectsSection')).toBeVisible();
        
        // Click Dashboard link
        await page.click('#dashboardLink');
        await page.waitForTimeout(500);
        
        // Empty state should be visible
        await expect(page.locator('#emptyState')).toBeVisible();
        
        // All sections should be hidden
        await expect(page.locator('#projectsSection')).not.toBeVisible();
        await expect(page.locator('#billsInboxSection')).not.toBeVisible();
        await expect(page.locator('#contactsSection')).not.toBeVisible();
        await expect(page.locator('#xeroSection')).not.toBeVisible();
    });

    test('should cycle through all sections without overlap', async ({ page }) => {
        const sections = [
            { link: '#projectsLink', section: '#projectsSection', name: 'Projects' },
            { link: '#billsInboxLink', section: '#billsInboxSection', name: 'Bills - Inbox' },
            { link: '#billsDirectLink', section: '#billsInboxSection', name: 'Bills - Direct' },
            { link: '#contactsLink', section: '#contactsSection', name: 'Contacts' },
            { link: '#xeroLink', section: '#xeroSection', name: 'Xero' }
        ];
        
        for (const current of sections) {
            // Navigate to section
            await page.click(current.link);
            await page.waitForTimeout(1000);
            
            // Current section should be visible
            await expect(page.locator(current.section)).toBeVisible();
            
            // All OTHER sections should be hidden
            for (const other of sections) {
                if (other.section !== current.section) {
                    await expect(page.locator(other.section)).not.toBeVisible();
                }
            }
        }
    });

    test('should maintain active nav state when switching sections', async ({ page }) => {
        // Click Projects
        await page.click('#projectsLink');
        await page.waitForTimeout(500);
        
        // Projects link should be active
        await expect(page.locator('#projectsLink')).toHaveClass(/active/);
        
        // Click Bills - Inbox
        await page.click('#billsInboxLink');
        await page.waitForTimeout(1000);
        
        // Bills Inbox link should be active, Projects should not
        await expect(page.locator('#billsInboxLink')).toHaveClass(/active/);
        await expect(page.locator('#projectsLink')).not.toHaveClass(/active/);
    });

    test('should handle rapid navigation without breaking', async ({ page }) => {
        // Rapidly click through sections
        await page.click('#projectsLink');
        await page.click('#billsInboxLink');
        await page.click('#contactsLink');
        await page.click('#xeroLink');
        await page.click('#projectsLink');
        
        await page.waitForTimeout(1500);
        
        // Should end up on Projects
        await expect(page.locator('#projectsSection')).toBeVisible();
        
        // Only Projects should be visible
        await expect(page.locator('#billsInboxSection')).not.toBeVisible();
        await expect(page.locator('#contactsSection')).not.toBeVisible();
        await expect(page.locator('#xeroSection')).not.toBeVisible();
    });

    test('should hide Projects section when navigating to Bills - Direct', async ({ page }) => {
        // Go to Projects first
        await page.click('#projectsLink');
        await page.waitForTimeout(500);
        await expect(page.locator('#projectsSection')).toBeVisible();
        
        // Navigate to Bills - Direct
        await page.click('#billsDirectLink');
        await page.waitForTimeout(1000);
        
        // Bills section should be visible
        await expect(page.locator('#billsInboxSection')).toBeVisible();
        
        // Projects should be hidden
        await expect(page.locator('#projectsSection')).not.toBeVisible();
    });
});

test.describe('Navigation - Tender View Integration', () => {
    test.beforeEach(async ({ page }) => {
        await page.goto('http://127.0.0.1:8000/login/');
        await page.fill('input[name="username"]', 'testuser');
        await page.fill('input[name="password"]', 'testpass123');
        await page.click('button[type="submit"]');
        await page.waitForURL('**/dashboard/');
    });

    test('should hide tender view when navigating away from Projects', async ({ page }) => {
        // Go to Projects and open a tender
        await page.click('#projectsLink');
        await page.waitForTimeout(500);
        await page.click('#projectsTableBody tr:first-child');
        await page.waitForTimeout(500);
        
        // Tender view should be visible
        await expect(page.locator('#tenderView')).toBeVisible();
        
        // Navigate to Bills
        await page.click('#billsInboxLink');
        await page.waitForTimeout(1000);
        
        // Bills should be visible, Projects and tender view should be hidden
        await expect(page.locator('#billsInboxSection')).toBeVisible();
        await expect(page.locator('#projectsSection')).not.toBeVisible();
    });

    test('should reset tender view when returning to Projects list', async ({ page }) => {
        // Open a tender
        await page.click('#projectsLink');
        await page.waitForTimeout(500);
        await page.click('#projectsTableBody tr:first-child');
        await page.waitForTimeout(500);
        
        // Navigate away
        await page.click('#dashboardLink');
        await page.waitForTimeout(500);
        
        // Go back to Projects
        await page.click('#projectsLink');
        await page.waitForTimeout(500);
        
        // Should show projects table, not tender view
        await expect(page.locator('#projectsTable')).toBeVisible();
        await expect(page.locator('#tenderView')).not.toBeVisible();
    });
});
