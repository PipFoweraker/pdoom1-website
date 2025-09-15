#!/usr/bin/env node

/**
 * Test script to verify header consistency and emoji removal across all HTML pages
 * Usage: node scripts/test-header-consistency.js
 * 
 * This is a simplified version that uses regex parsing instead of DOM parsing
 * to avoid external dependencies.
 */

const fs = require('fs');
const path = require('path');

// Define the expected header structure
const EXPECTED_STRUCTURE = {
  hasDesignerCredit: true,
  hasPipFowerakerText: true,
  hasDropdownNavigation: true,
  requiredDropdowns: ['Community ▾', 'Info ▾'],
  requiredLinks: ['Game', 'Leaderboard'],
  requiredARIAAttributes: ['role="navigation"', 'aria-label="Main navigation"'],
};

// Emoji detection regex
const EMOJI_REGEX = /[\u{1F600}-\u{1F64F}|\u{1F300}-\u{1F5FF}|\u{1F680}-\u{1F6FF}|\u{1F1E0}-\u{1F1FF}|\u{2600}-\u{26FF}|\u{2700}-\u{27BF}]/gu;

// Additional common emojis that might be missed by the main regex
const ADDITIONAL_EMOJIS = ['⚠️', '⬇️', '📰', '🎯', '🔬', '⚡', '🚀', '🛠️', '💻', '📚', '📝', '✨', '✉️', '🏆', '🔍', '📊', '👨‍💻', '🎨', '🎮'];

function findHtmlFiles(dir) {
  const files = [];
  const items = fs.readdirSync(dir, { withFileTypes: true });
  
  for (const item of items) {
    const fullPath = path.join(dir, item.name);
    if (item.isDirectory() && !item.name.startsWith('.') && item.name !== 'node_modules') {
      files.push(...findHtmlFiles(fullPath));
    } else if (item.isFile() && item.name === 'index.html') {
      files.push(fullPath);
    }
  }
  
  return files;
}

function testHeaderStructure(filePath, content) {
  const errors = [];
  
  // Test 1: Check for header element
  if (!content.includes('<header>')) {
    errors.push('Missing <header> element');
    return errors;
  }
  
  // Test 2: Check for navigation with proper ARIA
  if (!content.includes('role="navigation"') || !content.includes('aria-label="Main navigation"')) {
    errors.push('Missing nav with proper ARIA attributes');
  }
  
  // Test 3: Check for designer credit
  if (!content.includes('class="designer-credit"')) {
    errors.push('Missing designer credit (.designer-credit)');
  } else if (!content.includes("Pip Foweraker's")) {
    errors.push('Designer credit does not contain "Pip Foweraker\'s"');
  }
  
  // Test 4: Check for logo container
  if (!content.includes('class="logo-container"')) {
    errors.push('Missing logo container (.logo-container)');
  }
  
  // Test 5: Check for dropdown navigation
  const dropdownMatches = content.match(/class="dropdown"/g);
  if (!dropdownMatches || dropdownMatches.length < 2) {
    errors.push('Missing dropdown navigation elements (expected at least 2)');
  }
  
  // Test 6: Check for required dropdown labels
  for (const requiredDropdown of EXPECTED_STRUCTURE.requiredDropdowns) {
    if (!content.includes(requiredDropdown)) {
      errors.push(`Missing required dropdown: "${requiredDropdown}"`);
    }
  }
  
  // Test 7: Check for required main navigation links
  for (const requiredLink of EXPECTED_STRUCTURE.requiredLinks) {
    // Look for the link in navigation context
    const linkRegex = new RegExp(`role="menuitem"[^>]*>${requiredLink}<`, 'i');
    if (!linkRegex.test(content)) {
      errors.push(`Missing required navigation link: "${requiredLink}"`);
    }
  }
  
  return errors;
}

function testEmojiRemoval(filePath, content) {
  const errors = [];
  
  // Test for Unicode emojis
  const emojiMatches = content.match(EMOJI_REGEX);
  if (emojiMatches) {
    errors.push(`Found Unicode emojis: ${emojiMatches.join(', ')}`);
  }
  
  // Test for additional common emojis
  for (const emoji of ADDITIONAL_EMOJIS) {
    if (content.includes(emoji)) {
      errors.push(`Found emoji: "${emoji}"`);
    }
  }
  
  return errors;
}

function runTests() {
  console.log('Testing header consistency and emoji removal...\n');
  
  const publicDir = path.join(__dirname, '..', 'public');
  const htmlFiles = findHtmlFiles(publicDir);
  
  console.log(`Found ${htmlFiles.length} HTML files to test:\n`);
  
  let totalErrors = 0;
  const results = [];
  
  for (const filePath of htmlFiles) {
    const relativePath = path.relative(publicDir, filePath);
    const content = fs.readFileSync(filePath, 'utf8');
    
    const headerErrors = testHeaderStructure(filePath, content);
    const emojiErrors = testEmojiRemoval(filePath, content);
    const allErrors = [...headerErrors, ...emojiErrors];
    
    results.push({
      file: relativePath,
      errors: allErrors,
      passed: allErrors.length === 0
    });
    
    totalErrors += allErrors.length;
  }
  
  // Display results
  console.log('='.repeat(60));
  console.log('TEST RESULTS');
  console.log('='.repeat(60));
  
  for (const result of results) {
    const status = result.passed ? 'PASS' : 'FAIL';
    console.log(`${status} ${result.file}`);
    
    if (!result.passed) {
      for (const error of result.errors) {
        console.log(`  • ${error}`);
      }
      console.log('');
    }
  }
  
  console.log('='.repeat(60));
  console.log(`SUMMARY: ${results.filter(r => r.passed).length}/${results.length} files passed`);
  console.log(`Total errors: ${totalErrors}`);
  
  if (totalErrors === 0) {
    console.log('All tests passed! Header structure is consistent and emojis have been removed.');
  } else {
    console.log('Some tests failed. Please address the errors above.');
    process.exit(1);
  }
}

// This version uses regex parsing instead of DOM parsing to avoid external dependencies

// Run the tests
if (require.main === module) {
  runTests();
}

module.exports = { testHeaderStructure, testEmojiRemoval, findHtmlFiles };
