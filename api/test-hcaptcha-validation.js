#!/usr/bin/env node
// Test hCaptcha validation logic
// This tests the function's behavior with and without hCaptcha configuration

const { handler } = require('../netlify/functions/report-bug.js');

// Mock environment variables
const originalEnv = { ...process.env };

async function testWithoutHCaptcha() {
  console.log('\n=== Test 1: Without hCaptcha (backward compatible) ===');
  
  // Ensure hCaptcha is not configured
  delete process.env.HCAPTCHA_SITEKEY;
  delete process.env.HCAPTCHA_SECRET;
  process.env.DRY_RUN = 'true';
  process.env.GITHUB_DISPATCH_TOKEN = 'test-token';
  process.env.GITHUB_REPO = 'test/repo';
  
  const event = {
    httpMethod: 'POST',
    headers: { origin: '*' },
    body: JSON.stringify({
      title: 'Test bug without hCaptcha',
      description: 'This should work without hCaptcha token',
      type: 'bug',
      source: 'test'
    })
  };
  
  try {
    const response = await handler(event);
    console.log('Status:', response.statusCode);
    console.log('Body:', response.body);
    
    if (response.statusCode === 200) {
      console.log('✓ PASS: Request succeeded without hCaptcha token');
    } else {
      console.log('✗ FAIL: Request should succeed without hCaptcha configured');
    }
  } catch (err) {
    console.log('✗ FAIL: Error occurred:', err.message);
  }
}

async function testWithHCaptchaMissingToken() {
  console.log('\n=== Test 2: With hCaptcha configured, missing token ===');
  
  // Configure hCaptcha
  process.env.HCAPTCHA_SITEKEY = 'test-sitekey';
  process.env.HCAPTCHA_SECRET = 'test-secret';
  process.env.DRY_RUN = 'true';
  process.env.GITHUB_DISPATCH_TOKEN = 'test-token';
  process.env.GITHUB_REPO = 'test/repo';
  
  const event = {
    httpMethod: 'POST',
    headers: { origin: '*' },
    body: JSON.stringify({
      title: 'Test bug with hCaptcha required',
      description: 'This should fail without hCaptcha token',
      type: 'bug',
      source: 'test'
    })
  };
  
  try {
    const response = await handler(event);
    console.log('Status:', response.statusCode);
    console.log('Body:', response.body);
    
    if (response.statusCode === 400) {
      const body = JSON.parse(response.body);
      if (body.error && body.error.includes('hCaptcha')) {
        console.log('✓ PASS: Request rejected with missing hCaptcha token');
      } else {
        console.log('✗ FAIL: Wrong error message:', body.error);
      }
    } else {
      console.log('✗ FAIL: Request should fail with 400 when hCaptcha token is missing');
    }
  } catch (err) {
    console.log('✗ FAIL: Error occurred:', err.message);
  }
}

async function testHealthEndpoint() {
  console.log('\n=== Test 3: GET health check (should always work) ===');
  
  process.env.HCAPTCHA_SITEKEY = 'test-sitekey';
  process.env.DRY_RUN = 'true';
  
  const event = {
    httpMethod: 'GET',
    headers: { origin: '*' }
  };
  
  try {
    const response = await handler(event);
    console.log('Status:', response.statusCode);
    console.log('Body:', response.body);
    
    if (response.statusCode === 200) {
      console.log('✓ PASS: Health check succeeded');
    } else {
      console.log('✗ FAIL: Health check should return 200');
    }
  } catch (err) {
    console.log('✗ FAIL: Error occurred:', err.message);
  }
}

async function runTests() {
  console.log('Testing hCaptcha validation implementation...');
  
  try {
    await testWithoutHCaptcha();
    await testWithHCaptchaMissingToken();
    await testHealthEndpoint();
    
    console.log('\n=== Test Summary ===');
    console.log('Tests completed. Review output above for results.');
  } catch (err) {
    console.error('Fatal error running tests:', err);
    process.exit(1);
  } finally {
    // Restore environment
    process.env = originalEnv;
  }
}

runTests();
