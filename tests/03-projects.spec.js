// @ts-check
const { test, expect } = require('@playwright/test');

/**
 * Projects Tests
 * 
 * Test Summary:
 * 1. Projects table displays active projects on load
 * 2. Projects table shows correct columns and data
 * 3. Background images display as thumbnails
 * 4. Archive button archives a project
 * 5. Toggle to archived view shows archived projects
 * 6. Unarchive button restores a project
 * 7. Add Project functionality creates new project
 * 8. Update Project functionality modifies existing project
 */

test.describe.configure({ mode: 'serial' });

test.describe('Projects Management', () => {
    test.beforeEach(async ({ page }) => {
        // Login (this happens fresh for each test due to test isolation)
        await page.goto('http://localhost:8000/accounts/login/');
        await page.fill('input[name="username"]', 'testuser');
        await page.fill('input[name="password"]', 'testpass123');
        await page.click('button[type="submit"]');
        
        // Wait for dashboard to load
        await page.waitForURL('http://localhost:8000/');
        
        // Click Projects in navbar
        await page.click('#projectsLink');
        await page.waitForSelector('#projectsSection', { state: 'visible' });
        
        // Wait for projects to load
        await page.waitForTimeout(500);
    });

    test('should display active projects on load', async ({ page }) => {
        // Should show 2 active projects
        const rows = await page.locator('#projectsTableBody tr:not(.add-project-row)').count();
        expect(rows).toBe(2);
        
        // Should show "Active Project 1" and "Active Project 2"
        await expect(page.locator('text=Active Project 1')).toBeVisible();
        await expect(page.locator('text=Active Project 2')).toBeVisible();
        
        // Should NOT show archived projects
        await expect(page.locator('text=Archived Project 1')).not.toBeVisible();
        await expect(page.locator('text=Archived Project 2')).not.toBeVisible();
    });

    test('should display correct table columns and data', async ({ page }) => {
        // Check table headers - scope to Projects table only
        const projectsTable = page.locator('#projectsTable');
        const headers = projectsTable.locator('thead th');
        await expect(headers.nth(0)).toHaveText('Project');
        await expect(headers.nth(1)).toHaveText('Status');
        await expect(headers.nth(2)).toHaveText('Type');
        await expect(headers.nth(3)).toHaveText('Xero Instance');
        await expect(headers.nth(4)).toHaveText('Sales Account');
        await expect(headers.nth(5)).toHaveText('Background Image');
        await expect(headers.nth(10)).toHaveText('Archive');
        
        // Check first project data - Column order: Project, Status, Type, Xero Instance, Sales Account...
        const firstRow = page.locator('#projectsTableBody tr').first();
        await expect(firstRow.locator('td').nth(0)).toContainText('Active Project 1');
        await expect(firstRow.locator('td').nth(1)).toContainText('Tender'); // Status column
        await expect(firstRow.locator('td').nth(2)).toContainText('Development'); // Type column
        await expect(firstRow.locator('td').nth(3)).toContainText('Test Xero');
        await expect(firstRow.locator('td').nth(4)).toContainText('4000 - Sales Revenue');
        
        // Check Update button exists
        await expect(firstRow.locator('button.update-project-btn')).toBeVisible();
        
        // Check Archive button exists and is red (btn-danger)
        const archiveBtn = firstRow.locator('button.archive-project-btn');
        await expect(archiveBtn).toBeVisible();
        await expect(archiveBtn).toHaveClass(/btn-danger/);
    });

    test('should display background images as thumbnails', async ({ page }) => {
        // Active Project 1 has a background image
        // Column order: Project(0), Status(1), Type(2), Xero Instance(3), Sales Account(4), Background Image(5)
        const firstRow = page.locator('#projectsTableBody tr').first();
        const bgCell = firstRow.locator('td').nth(5); // Background Image is column 5
        
        // Should have an img tag
        const img = bgCell.locator('img');
        await expect(img).toBeVisible();
        
        // Should have correct styles
        await expect(img).toHaveAttribute('style', /max-width: 60px/);
        await expect(img).toHaveAttribute('style', /max-height: 40px/);
        
        // Active Project 2 has no background
        const secondRow = page.locator('#projectsTableBody tr').nth(1);
        const bgCell2 = secondRow.locator('td').nth(5); // Background Image is column 5
        await expect(bgCell2).toContainText('-');
    });

    test('should archive a project when archive button clicked', async ({ page }) => {
        // Click archive button on first project
        const firstRow = page.locator('#projectsTableBody tr').first();
        const projectName = await firstRow.locator('td').first().textContent();
        
        // Click archive button
        await firstRow.locator('button.archive-project-btn').click();
        
        // Confirm dialog
        page.on('dialog', dialog => dialog.accept());
        await page.waitForTimeout(100);
        await firstRow.locator('button.archive-project-btn').click();
        
        // Wait for reload
        await page.waitForTimeout(500);
        
        // Project should disappear from active list
        await expect(page.locator(`text=${projectName}`)).not.toBeVisible();
        
        // Should now have only 1 active project
        const rows = await page.locator('#projectsTableBody tr:not(.add-project-row)').count();
        expect(rows).toBe(1);
    });

    test('should toggle to archived view and show archived projects', async ({ page }) => {
        // Click "Show Archived" button
        await page.click('#toggleArchiveBtn');
        
        // Wait for data to load and table to update
        await page.waitForTimeout(1000);
        
        // Button should change to "Show Active"
        await expect(page.locator('#toggleArchiveBtn')).toContainText('Show Active');
        await expect(page.locator('#toggleArchiveBtn')).toHaveClass(/btn-secondary/);
        
        // Archive column header should change to "Unarchive"
        await expect(page.locator('#archiveColumnHeader')).toHaveText('Unarchive');
        
        // Should show 3 archived projects (2 original + 1 from previous test)
        const rows = await page.locator('#projectsTableBody tr:not(.add-project-row)').count();
        expect(rows).toBe(3);
        
        // Should show archived projects in the table (including the one archived in previous test)
        await expect(page.locator('#projectsTableBody').locator('text=Archived Project 1')).toBeVisible();
        await expect(page.locator('#projectsTableBody').locator('text=Archived Project 2')).toBeVisible();
        await expect(page.locator('#projectsTableBody').locator('text=Active Project 1')).toBeVisible(); // This was archived in test 4
        
        // Should NOT show Active Project 2 (still active)
        await expect(page.locator('#projectsTableBody').locator('text=Active Project 2')).not.toBeVisible();
        
        // Should have unarchive buttons (btn-info)
        const unarchiveBtn = page.locator('button.unarchive-project-btn').first();
        await expect(unarchiveBtn).toBeVisible();
        await expect(unarchiveBtn).toHaveClass(/btn-info/);
    });

    test('should unarchive a project when unarchive button clicked', async ({ page }) => {
        // Switch to archived view
        await page.click('#toggleArchiveBtn');
        await page.waitForTimeout(500);
        
        // Click unarchive button on first archived project
        const firstRow = page.locator('#projectsTableBody tr').first();
        const projectName = await firstRow.locator('td').first().textContent();
        
        // Click unarchive button
        await firstRow.locator('button.unarchive-project-btn').click();
        
        // Confirm dialog
        page.on('dialog', dialog => dialog.accept());
        await page.waitForTimeout(100);
        await firstRow.locator('button.unarchive-project-btn').click();
        
        // Wait for reload
        await page.waitForTimeout(500);
        
        // Project should disappear from archived list
        await expect(page.locator(`text=${projectName}`)).not.toBeVisible();
        
        // Should now have 2 archived projects remaining (started with 3, unarchived 1)
        const rowsAfter = await page.locator('#projectsTableBody tr:not(.add-project-row)').count();
        expect(rowsAfter).toBe(2);
        
        // Switch back to active view
        await page.click('#toggleArchiveBtn');
        await page.waitForTimeout(500);
        
        // Unarchived project should now appear in active list
        await expect(page.locator(`text=${projectName}`)).toBeVisible();
    });

    test('should add a new project', async ({ page }) => {
        // Click Add Project button
        await page.click('#addProjectBtn');
        
        // Should show add row
        await expect(page.locator('.add-project-row')).toBeVisible();
        
        // Fill in project details
        await page.fill('.project-name-input', 'New Test Project');
        
        // Select project type
        await page.selectOption('.project-type-select', 'construction');
        
        // Select Xero instance (select first option that's not the placeholder)
        const xeroOptions = await page.locator('.xero-instance-select option').allTextContents();
        const xeroValue = await page.locator('.xero-instance-select option:not([value=""])').first().getAttribute('value');
        if (xeroValue) {
            await page.selectOption('.xero-instance-select', xeroValue);
        }
        
        // Wait for sales accounts to load
        await page.waitForTimeout(500);
        
        // Select sales account
        await page.selectOption('.sales-account-select', '4000');
        
        // Click Add button
        page.on('dialog', dialog => dialog.accept());
        await page.click('.add-new-project-btn');
        
        // Wait for reload
        await page.waitForTimeout(1000);
        
        // New project should appear in list
        await expect(page.locator('text=New Test Project')).toBeVisible();
        
        // Should have 3 active projects now (Active Project 2 + unarchived from test 6 + this new one)
        const finalRows = await page.locator('#projectsTableBody tr:not(.add-project-row)').count();
        expect(finalRows).toBe(3);
    });

    test('should update an existing project', async ({ page }) => {
        // Click Update button on first project
        const firstRow = page.locator('#projectsTableBody tr').first();
        await firstRow.locator('button.update-project-btn').click();
        
        // Should show input fields
        await expect(firstRow.locator('.project-name-input')).toBeVisible();
        await expect(firstRow.locator('.sales-account-select')).toBeVisible();
        
        // Wait for sales accounts to load
        await page.waitForTimeout(500);
        
        // Change project name
        await firstRow.locator('.project-name-input').fill('Updated Project Name');
        
        // Click Save button
        page.on('dialog', dialog => dialog.accept());
        await firstRow.locator('button.save-project-btn').click();
        
        // Wait for reload and table to update
        await page.waitForTimeout(1500);
        
        // Updated name should appear in the table
        await expect(page.locator('#projectsTableBody').locator('text=Updated Project Name')).toBeVisible();
        await expect(page.locator('#projectsTableBody').locator('text=Active Project 1')).not.toBeVisible();
    });

    test('should cancel add project operation', async ({ page }) => {
        // Click Add Project button
        await page.click('#addProjectBtn');
        await expect(page.locator('.add-project-row')).toBeVisible();
        
        // Fill in some data
        await page.fill('.project-name-input', 'Cancelled Project');
        
        // Click Cancel button
        await page.click('.cancel-add-project-btn');
        
        // Add row should disappear
        await expect(page.locator('.add-project-row')).not.toBeVisible();
        
        // Should have 3 active projects (Active Project 2 + unarchived from test 6 + new from test 7)
        const rows = await page.locator('#projectsTableBody tr:not(.add-project-row)').count();
        expect(rows).toBe(3);
    });

    test('should cancel update project operation', async ({ page }) => {
        // Get original name
        const firstRow = page.locator('#projectsTableBody tr').first();
        const originalName = await firstRow.locator('td').first().textContent();
        
        // Click Update button
        await firstRow.locator('button.update-project-btn').click();
        
        // Change name
        await firstRow.locator('.project-name-input').fill('Changed Name');
        
        // Click Cancel button
        await firstRow.locator('button.cancel-update-project-btn').click();
        
        // Wait for reload
        await page.waitForTimeout(500);
        
        // Original name should still be there
        await expect(page.locator(`text=${originalName}`)).toBeVisible();
        await expect(page.locator('text=Changed Name')).not.toBeVisible();
    });

    test('should validate required project name on add', async ({ page }) => {
        // Click Add Project button
        await page.click('#addProjectBtn');
        
        // Try to add without name
        page.on('dialog', dialog => {
            expect(dialog.message()).toContain('Project name is required');
            dialog.accept();
        });
        
        await page.click('.add-new-project-btn');
        
        // Add row should still be visible
        await expect(page.locator('.add-project-row')).toBeVisible();
    });

    test('should prevent multiple add rows', async ({ page }) => {
        // Click Add Project button
        await page.click('#addProjectBtn');
        await expect(page.locator('.add-project-row')).toBeVisible();
        
        // Try to click Add Project again
        page.on('dialog', dialog => {
            expect(dialog.message()).toContain('Please complete or cancel the current add operation');
            dialog.accept();
        });
        
        await page.click('#addProjectBtn');
        
        // Should still have only one add row
        const addRows = await page.locator('.add-project-row').count();
        expect(addRows).toBe(1);
    });
});
