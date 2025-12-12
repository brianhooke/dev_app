/**
 * Smoke Tests
 * 
 * Basic tests to verify the app loads and core navigation works.
 * These are intentionally simple and should always pass.
 */

const { test, expect } = require('@playwright/test');

test.describe('Smoke Tests', () => {
    
    test('Dashboard loads successfully', async ({ page }) => {
        // Navigate to dashboard
        await page.goto('/dashboard/', { waitUntil: 'networkidle' });
        
        // Page should have loaded (check for navbar)
        await expect(page.locator('.reusable-navbar')).toBeVisible();
        
        // Should see the version number in the page
        await expect(page.locator('text=/v\\d+/')).toBeVisible();
    });

    test('Projects section loads when clicked', async ({ page }) => {
        await page.goto('/dashboard/', { waitUntil: 'networkidle' });
        
        // Click Projects link in navbar
        await page.click('#projectsLink');
        await page.waitForTimeout(500);
        
        // Projects section should be visible
        await expect(page.locator('#projectsSection')).toBeVisible();
    });

    test('Bills section loads when clicked', async ({ page }) => {
        await page.goto('/dashboard/', { waitUntil: 'networkidle' });
        
        // Click Bills link in navbar
        await page.click('#billsLink');
        await page.waitForTimeout(500);
        
        // Bills section should be visible
        await expect(page.locator('#billsInboxSection')).toBeVisible();
    });

    test('Contacts section loads when clicked', async ({ page }) => {
        await page.goto('/dashboard/', { waitUntil: 'networkidle' });
        
        // Click Contacts link in navbar
        await page.click('#contactsLink');
        await page.waitForTimeout(500);
        
        // Contacts section should be visible
        await expect(page.locator('#contactsSection')).toBeVisible();
    });

    test('Projects grid shows test data', async ({ page }) => {
        await page.goto('/dashboard/', { waitUntil: 'networkidle' });
        
        // Go to Projects
        await page.click('#projectsLink');
        await page.waitForTimeout(1000);
        
        // Should have project cards in the grid
        const projectCards = page.locator('#projectsGridContainer .project-card');
        await expect(projectCards.first()).toBeVisible({ timeout: 10000 });
        
        // Should have at least one project
        const count = await projectCards.count();
        expect(count).toBeGreaterThan(0);
    });

});
