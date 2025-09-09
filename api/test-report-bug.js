#!/usr/bin/env node
const http = require('http');

const data = JSON.stringify({
  title: 'Test crash when opening menu',
  description: 'Game crashes after pressing ESC on main screen. Repro 3/3.',
  type: 'bug',
  source: 'game',
  appVersion: '1.0.0',
  buildId: 'local-dev',
  os: 'Windows 11',
  notify: false
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
    console.log(res.statusCode, body);
  });
});

req.on('error', (e) => {
  console.error('Request error:', e);
  process.exit(1);
});

req.write(data);
req.end();
