import { test, expect } from '@playwright/test';

test('frontend loads without console errors', async ({ page }) => {
  const consoleErrors = [];
  
  // Capture console errors
  page.on('console', msg => {
    if (msg.type() === 'error') {
      consoleErrors.push(msg.text());
    }
  });
  
  // Capture page errors
  page.on('pageerror', error => {
    consoleErrors.push(error.message);
  });
  
  // Load the app
  await page.goto('/');
  
  // Wait for app to be interactive
  await page.waitForLoadState('networkidle');
  
  // Check for successful render
  await expect(page.locator('[data-testid="app"]')).toBeVisible();
  await expect(page.locator('h1')).toContainText('Arkham Assistant');
  
  // Assert no console errors occurred
  expect(consoleErrors).toHaveLength(0);
  
  if (consoleErrors.length > 0) {
    console.error('Console errors detected:', consoleErrors);
  }
});

