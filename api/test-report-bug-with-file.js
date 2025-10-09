#!/usr/bin/env node
/**
 * Test script for bug report with file attachment
 * Usage: node api/test-report-bug-with-file.js
 */
const http = require('http');
const fs = require('fs');

// Read test file and encode as base64
const testFileContent = Buffer.from('Test log file content\nError: Sample error\nStack trace...').toString('base64');

const data = JSON.stringify({
  title: 'Test crash with log file',
  description: 'Game crashes after pressing ESC on main screen. Repro 3/3. Log file attached.',
  type: 'bug',
  source: 'web',
  appVersion: '1.0.0',
  buildId: 'local-dev',
  os: 'Windows 11',
  notify: false,
  attachment: {
    filename: 'error.log',
    content: testFileContent,
    size: Buffer.byteLength(testFileContent),
    type: 'text/plain'
  }
});

const req = http.request({
  hostname: '127.0.0.1',
  port: 8888,
  path: '/.netlify/functions/report-bug',
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Content-Length': Buffer.byteLength(data)
  }
}, res => {
  let body = '';
  res.on('data', chunk => body += chunk);
  res.on('end', () => {
    console.log('Status:', res.statusCode);
    console.log('Response:', body);
    try {
      const parsed = JSON.parse(body);
      console.log('Parsed response:', JSON.stringify(parsed, null, 2));
    } catch (e) {
      console.log('Could not parse response as JSON');
    }
  });
});

req.on('error', (e) => {
  console.error('Request error:', e);
  console.log('\nNote: This test requires the Netlify dev server to be running.');
  console.log('Run: netlify dev --port 8888');
  process.exit(1);
});

req.write(data);
req.end();
