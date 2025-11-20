/**
 * Playwright Global Setup
 * Runs once before all tests to ensure fresh test database
 */

const { execSync } = require('child_process');
const path = require('path');

async function globalSetup() {
  console.log('\n🔄 Setting up test environment...\n');
  
  const projectRoot = path.join(__dirname, '..');
  
  try {
    // Stop any running test server
    console.log('  Stopping any running servers...');
    try {
      execSync('lsof -ti:8000 | xargs kill -9', { stdio: 'ignore' });
    } catch (e) {
      // No server running, that's fine
    }
    
    // Wait a moment for port to be released
    await new Promise(resolve => setTimeout(resolve, 1000));
    
    // Remove old test database
    console.log('  Removing old test database...');
    execSync('rm -f db_test.sqlite3', { cwd: projectRoot, stdio: 'inherit' });
    
    // Run migrations
    console.log('  Running migrations...');
    execSync('python3 manage.py migrate --settings=dev_app.settings.test', {
      cwd: projectRoot,
      stdio: 'inherit'
    });
    
    // Seed test data
    console.log('  Seeding test data...');
    execSync('python3 manage.py shell --settings=dev_app.settings.test < tests/seed_test_data_simple.py', {
      cwd: projectRoot,
      stdio: 'inherit'
    });
    
    // Start test server in background
    console.log('  Starting test server...');
    const { spawn } = require('child_process');
    const server = spawn('python3', ['manage.py', 'runserver', '--settings=dev_app.settings.test'], {
      cwd: projectRoot,
      detached: true,
      stdio: 'ignore'
    });
    server.unref();
    
    // Wait for server to be ready
    console.log('  Waiting for server to be ready...');
    await waitForServer('http://127.0.0.1:8000', 30000);
    
    console.log('\n✅ Test environment ready!\n');
    
  } catch (error) {
    console.error('\n❌ Setup failed:', error.message);
    throw error;
  }
}

async function waitForServer(url, timeout) {
  const start = Date.now();
  while (Date.now() - start < timeout) {
    try {
      const response = await fetch(url);
      if (response.ok || response.status === 302) {
        return;
      }
    } catch (e) {
      // Server not ready yet
    }
    await new Promise(resolve => setTimeout(resolve, 500));
  }
  throw new Error(`Server did not start within ${timeout}ms`);
}

module.exports = globalSetup;
