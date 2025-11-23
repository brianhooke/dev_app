/**
 * Items Section E2E Tests
 * 
 * Tests for the Items (Categories & Costings) section including:
 * - Navigation and data clearing
 * - Category and item creation
 * - Duplicate validation
 * - Drag-and-drop reordering
 * - Data integrity across project switches
 */

const { test, expect } = require('@playwright/test');

test.describe('Items Section - Navigation & Data Integrity', () => {
    test.beforeEach(async ({ page }) => {
        // Login
        await page.goto('http://127.0.0.1:8000/login/');
        await page.fill('input[name="username"]', 'testuser');
        await page.fill('input[name="password"]', 'testpass123');
        await page.click('button[type="submit"]');
        await page.waitForURL('**/dashboard/');
        
        // Navigate to Projects
        await page.click('#projectsLink');
        await page.waitForTimeout(500);
    });

    test('should load Items section without errors', async ({ page }) => {
        // Click on first active project
        await page.click('#projectsTableBody tr:first-child');
        await page.waitForTimeout(500);
        
        // Click Items tab
        await page.click('.tender-nav-btn:has-text("Items")');
        await page.waitForTimeout(1000);
        
        // Should show Items section
        await expect(page.locator('.items-container')).toBeVisible();
        await expect(page.locator('text=Add Category')).toBeVisible();
        await expect(page.locator('text=Add Item')).toBeVisible();
    });

    test('should show loading state then clear data for project with no items', async ({ page }) => {
        // Click on Active Project 2 (has no items)
        const rows = page.locator('#projectsTableBody tr');
        await rows.nth(1).click();
        await page.waitForTimeout(500);
        
        // Click Items tab
        await page.click('.tender-nav-btn:has-text("Items")');
        
        // Should briefly show "Loading..."
        await expect(page.locator('#itemsDisplayTableBody')).toContainText('Loading...', { timeout: 500 });
        
        // Then show empty state
        await expect(page.locator('#itemsDisplayTableBody')).toContainText('No items yet', { timeout: 3000 });
    });

    test('should reload Items section multiple times without errors', async ({ page }) => {
        // Click on first project with items
        await page.click('#projectsTableBody tr:first-child');
        await page.waitForTimeout(500);
        
        // Load Items section 3 times
        for (let i = 0; i < 3; i++) {
            await page.click('.tender-nav-btn:has-text("Items")');
            await page.waitForTimeout(1000);
            
            // Should show items container
            await expect(page.locator('.items-container')).toBeVisible();
            
            // Go back to overview
            await page.click('.tender-nav-btn:has-text("Overview")');
            await page.waitForTimeout(500);
        }
        
        // Final check - Items should still work
        await page.click('.tender-nav-btn:has-text("Items")');
        await expect(page.locator('.items-container')).toBeVisible();
    });

    test('should clear stale data when switching between projects', async ({ page }) => {
        // Open Project 1 with items
        const rows = page.locator('#projectsTableBody tr');
        await rows.first().click();
        await page.waitForTimeout(500);
        
        await page.click('.tender-nav-btn:has-text("Items")');
        await page.waitForTimeout(1000);
        
        // Should show Project 1 categories
        await expect(page.locator('#itemsDisplayTableBody')).toContainText('Electrical');
        
        // Go back to projects
        await page.click('text=Back to Projects');
        await page.waitForTimeout(500);
        
        // Open Project 2 (no items)
        await rows.nth(1).click();
        await page.waitForTimeout(500);
        
        await page.click('.tender-nav-btn:has-text("Items")');
        await page.waitForTimeout(1000);
        
        // Should NOT show Project 1 data
        await expect(page.locator('#itemsDisplayTableBody')).not.toContainText('Electrical');
        await expect(page.locator('#itemsDisplayTableBody')).toContainText('No items yet');
    });
});

test.describe('Items Section - Category Creation', () => {
    test.beforeEach(async ({ page }) => {
        // Login and navigate to Items section
        await page.goto('http://127.0.0.1:8000/login/');
        await page.fill('input[name="username"]', 'testuser');
        await page.fill('input[name="password"]', 'testpass123');
        await page.click('button[type="submit"]');
        await page.waitForURL('**/dashboard/');
        
        await page.click('#projectsLink');
        await page.waitForTimeout(500);
        
        // Click on first project
        await page.click('#projectsTableBody tr:first-child');
        await page.waitForTimeout(500);
        
        await page.click('.tender-nav-btn:has-text("Items")');
        await page.waitForTimeout(1000);
    });

    test('should validate category form and enable Add button', async ({ page }) => {
        // Initially button should be disabled
        const addBtn = page.locator('#addCategoryBtn');
        await expect(addBtn).toBeDisabled();
        await expect(addBtn).toHaveClass(/disabled/);
        
        // Fill category name only
        await page.fill('#categoryNameInput', 'Test Category');
        await expect(addBtn).toBeDisabled(); // Still disabled without order
        
        // Select order
        await page.selectOption('#categoryOrderSelect', '1');
        
        // Button should be enabled
        await expect(addBtn).toBeEnabled();
        await expect(addBtn).toHaveClass(/enabled/);
    });

    test('should prevent duplicate category names (case-insensitive)', async ({ page }) => {
        // Try to create category with existing name
        await page.fill('#categoryNameInput', 'electrical'); // lowercase of existing "Electrical"
        await page.selectOption('#categoryOrderSelect', '1');
        
        // Click Add
        await page.click('#addCategoryBtn');
        await page.waitForTimeout(500);
        
        // Should show descriptive error
        await expect(page.locator('text=/already exists/i')).toBeVisible({ timeout: 2000 });
    });

    test('should create new category and update table', async ({ page }) => {
        // Fill form
        await page.fill('#categoryNameInput', 'New Test Category');
        await page.selectOption('#categoryOrderSelect', '1');
        
        // Click Add
        await page.click('#addCategoryBtn');
        
        // Wait for success message
        await expect(page.locator('text=/added successfully/i')).toBeVisible({ timeout: 2000 });
        
        // Dismiss alert
        await page.click('button:has-text("OK")');
        
        // Form should be cleared
        await expect(page.locator('#categoryNameInput')).toHaveValue('');
        
        // Table should show new category
        await expect(page.locator('#itemsDisplayTableBody')).toContainText('New Test Category');
    });

    test('should update category order dropdown after adding category', async ({ page }) => {
        // Check initial max order
        const initialOptions = await page.locator('#categoryOrderSelect option').count();
        
        // Add new category
        await page.fill('#categoryNameInput', 'Test Category');
        await page.selectOption('#categoryOrderSelect', '1');
        await page.click('#addCategoryBtn');
        await page.waitForTimeout(1500);
        
        // Dismiss alert
        await page.click('button:has-text("OK")').catch(() => {});
        
        // Dropdown should have one more option
        const newOptions = await page.locator('#categoryOrderSelect option').count();
        expect(newOptions).toBe(initialOptions + 1);
    });
});

test.describe('Items Section - Item Creation', () => {
    test.beforeEach(async ({ page }) => {
        // Login and navigate to Items section
        await page.goto('http://127.0.0.1:8000/login/');
        await page.fill('input[name="username"]', 'testuser');
        await page.fill('input[name="password"]', 'testpass123');
        await page.click('button[type="submit"]');
        await page.waitForURL('**/dashboard/');
        
        await page.click('#projectsLink');
        await page.waitForTimeout(500);
        
        await page.click('#projectsTableBody tr:first-child');
        await page.waitForTimeout(500);
        
        await page.click('.tender-nav-btn:has-text("Items")');
        await page.waitForTimeout(1000);
    });

    test('should validate item form and enable Add button', async ({ page }) => {
        const addBtn = page.locator('#addItemBtn');
        await expect(addBtn).toBeDisabled();
        
        // Fill item name only
        await page.fill('#itemNameInput', 'Test Item');
        await expect(addBtn).toBeDisabled();
        
        // Select category
        await page.selectOption('#itemCategorySelect', { index: 1 });
        await page.waitForTimeout(300);
        await expect(addBtn).toBeDisabled();
        
        // Select order
        await page.selectOption('#itemOrderSelect', '1');
        
        // Button should be enabled
        await expect(addBtn).toBeEnabled();
        await expect(addBtn).toHaveClass(/enabled/);
    });

    test('should enable item order dropdown when category selected', async ({ page }) => {
        const orderSelect = page.locator('#itemOrderSelect');
        
        // Initially disabled
        await expect(orderSelect).toBeDisabled();
        
        // Select category
        await page.selectOption('#itemCategorySelect', { index: 1 });
        await page.waitForTimeout(300);
        
        // Should be enabled
        await expect(orderSelect).toBeEnabled();
    });

    test('should create new item and update table', async ({ page }) => {
        // Fill form
        await page.fill('#itemNameInput', 'New Test Item');
        await page.selectOption('#itemCategorySelect', { index: 1 });
        await page.waitForTimeout(300);
        await page.selectOption('#itemOrderSelect', '1');
        
        // Click Add
        await page.click('#addItemBtn');
        
        // Wait for success
        await expect(page.locator('text=/added successfully/i')).toBeVisible({ timeout: 2000 });
        await page.click('button:has-text("OK")');
        
        // Table should show new item
        await expect(page.locator('#itemsDisplayTableBody')).toContainText('New Test Item');
    });
});

test.describe('Items Section - Drag and Drop Reordering', () => {
    test.beforeEach(async ({ page }) => {
        // Login and navigate to Items section with data
        await page.goto('http://127.0.0.1:8000/login/');
        await page.fill('input[name="username"]', 'testuser');
        await page.fill('input[name="password"]', 'testpass123');
        await page.click('button[type="submit"]');
        await page.waitForURL('**/dashboard/');
        
        await page.click('#projectsLink');
        await page.waitForTimeout(500);
        
        await page.click('#projectsTableBody tr:first-child');
        await page.waitForTimeout(500);
        
        await page.click('.tender-nav-btn:has-text("Items")');
        await page.waitForTimeout(1000);
    });

    test('should display categories with folder icon and items with tree icon', async ({ page }) => {
        // Check for category rows with folder icon
        const categoryRows = page.locator('.category-row');
        await expect(categoryRows.first()).toContainText('📁');
        
        // Check for item rows with tree icon
        const itemRows = page.locator('.item-row');
        await expect(itemRows.first()).toContainText('└─');
    });

    test('should make category rows draggable', async ({ page }) => {
        const categoryRow = page.locator('.category-row').first();
        await expect(categoryRow).toHaveAttribute('draggable', 'true');
    });

    test('should make item rows draggable', async ({ page }) => {
        const itemRow = page.locator('.item-row').first();
        await expect(itemRow).toHaveAttribute('draggable', 'true');
    });

    test('should show move cursor on hover over draggable elements', async ({ page }) => {
        const categoryRow = page.locator('.category-row').first();
        await expect(categoryRow).toHaveCSS('cursor', 'move');
        
        const itemRow = page.locator('.item-row').first();
        await expect(itemRow).toHaveCSS('cursor', 'move');
    });

    test('should reorder category when dragged', async ({ page }) => {
        // Get initial order
        const categories = await page.locator('.category-row').allTextContents();
        const firstCategory = categories[0];
        const secondCategory = categories[1];
        
        // Drag first category to second position
        const source = page.locator('.category-row').first();
        const target = page.locator('.category-row').nth(1);
        
        await source.dragTo(target);
        await page.waitForTimeout(1500); // Wait for AJAX and reload
        
        // Check new order
        const newCategories = await page.locator('.category-row').allTextContents();
        expect(newCategories[0]).toContain(secondCategory.replace('📁 ', ''));
        expect(newCategories[1]).toContain(firstCategory.replace('📁 ', ''));
    });

    test('should reorder item within same category', async ({ page }) => {
        // Get first category's items
        const firstCategoryRow = page.locator('.category-row').first();
        const categoryPk = await firstCategoryRow.getAttribute('data-category-pk');
        
        // Find items in this category
        const itemsInCategory = page.locator(`.item-row[data-category-pk="${categoryPk}"]`);
        const itemCount = await itemsInCategory.count();
        
        if (itemCount >= 2) {
            // Get initial order
            const items = await itemsInCategory.allTextContents();
            const firstItem = items[0];
            const secondItem = items[1];
            
            // Drag first item to second position
            await itemsInCategory.first().dragTo(itemsInCategory.nth(1));
            await page.waitForTimeout(1500);
            
            // Check new order
            const newItems = await itemsInCategory.allTextContents();
            expect(newItems[0]).toContain(secondItem.replace('└─ ', ''));
            expect(newItems[1]).toContain(firstItem.replace('└─ ', ''));
        }
    });
});

test.describe('Items Section - Data Persistence', () => {
    test.beforeEach(async ({ page }) => {
        await page.goto('http://127.0.0.1:8000/login/');
        await page.fill('input[name="username"]', 'testuser');
        await page.fill('input[name="password"]', 'testpass123');
        await page.click('button[type="submit"]');
        await page.waitForURL('**/dashboard/');
    });

    test('should persist order after page refresh', async ({ page }) => {
        // Navigate to Items
        await page.click('#projectsLink');
        await page.waitForTimeout(500);
        await page.click('#projectsTableBody tr:first-child');
        await page.waitForTimeout(500);
        await page.click('.tender-nav-btn:has-text("Items")');
        await page.waitForTimeout(1000);
        
        // Get current order
        const categories = await page.locator('.category-row').allTextContents();
        
        // Go back to dashboard
        await page.click('#dashboardLink');
        await page.waitForTimeout(500);
        
        // Navigate back to Items
        await page.click('#projectsLink');
        await page.waitForTimeout(500);
        await page.click('#projectsTableBody tr:first-child');
        await page.waitForTimeout(500);
        await page.click('.tender-nav-btn:has-text("Items")');
        await page.waitForTimeout(1000);
        
        // Order should be the same
        const newCategories = await page.locator('.category-row').allTextContents();
        expect(newCategories).toEqual(categories);
    });

    test('should maintain separate data for different projects', async ({ page }) => {
        await page.click('#projectsLink');
        await page.waitForTimeout(500);
        
        // Get Project 1 items
        await page.click('#projectsTableBody tr:first-child');
        await page.waitForTimeout(500);
        await page.click('.tender-nav-btn:has-text("Items")');
        await page.waitForTimeout(1000);
        
        const project1HasData = await page.locator('.category-row').count() > 0;
        
        // Go back and check Project 2
        await page.click('text=Back to Projects');
        await page.waitForTimeout(500);
        
        await page.click('#projectsTableBody tr:nth-child(2)');
        await page.waitForTimeout(500);
        await page.click('.tender-nav-btn:has-text("Items")');
        await page.waitForTimeout(1000);
        
        const project2HasData = await page.locator('.category-row').count() > 0;
        
        // Projects should have different data states
        expect(project1HasData).not.toBe(project2HasData);
    });
});
