/**
 * Playwright Global Teardown
 * Runs once after all tests to clean up
 */

const { execSync } = require('child_process');

async function globalTeardown() {
  console.log('\n🧹 Cleaning up test environment...\n');
  
  try {
    // Stop test server
    console.log('  Stopping test server...');
    try {
      execSync('lsof -ti:8000 | xargs kill -9', { stdio: 'ignore' });
    } catch (e) {
      // Server already stopped
    }
    
    console.log('\n✅ Cleanup complete!\n');
    
  } catch (error) {
    console.error('\n❌ Teardown failed:', error.message);
    // Don't throw - we want tests to complete even if teardown fails
  }
}

module.exports = globalTeardown;
