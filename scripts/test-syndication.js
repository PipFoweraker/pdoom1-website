#!/usr/bin/env node
// Test script for syndication helper functions

const helpers = require('./syndication-helpers.js');
const path = require('path');

console.log('🧪 Testing Syndication Helper Functions\n');

// Test 1: Extract metadata from an existing blog post
console.log('Test 1: Extract Blog Metadata');
console.log('='.repeat(50));

const testBlogPath = path.join(__dirname, '../public/blog/2025-10-09-website-development-sprint-complete-v0-2-0.md');

try {
  const metadata = helpers.extractBlogMetadata(testBlogPath);
  console.log('✅ Successfully extracted metadata:');
  console.log('   Title:', metadata.title);
  console.log('   Date:', metadata.date);
  console.log('   Tags:', metadata.tags.join(', '));
  console.log('   Summary length:', metadata.summary.length);
  console.log('   Summary preview:', metadata.summary.substring(0, 100) + '...');
} catch (error) {
  console.error('❌ Failed to extract metadata:', error.message);
}

console.log('\n');

// Test 2: Generate blog URL
console.log('Test 2: Generate Blog URL');
console.log('='.repeat(50));

const testFilename = '2025-10-09-website-development-sprint-complete-v0-2-0.md';
const url = helpers.generateBlogUrl(testFilename);
console.log('✅ Generated URL:', url);

console.log('\n');

// Test 3: Format content for different platforms
console.log('Test 3: Format Content for Platforms');
console.log('='.repeat(50));

const sampleMetadata = {
  title: 'Test Blog Post: Amazing New Feature',
  summary: 'This is a test blog post about an amazing new feature that we have implemented. It includes several improvements and bug fixes.',
  tags: ['feature', 'update', 'milestone']
};

const sampleUrl = 'https://pdoom1.com/blog/#test-post';

console.log('Bluesky format:');
console.log('-'.repeat(50));
const bskyContent = helpers.formatPostContent(sampleMetadata, sampleUrl, 'bluesky');
console.log(bskyContent);
console.log('Character count:', bskyContent.length);

console.log('\nTwitter format:');
console.log('-'.repeat(50));
const twitterContent = helpers.formatPostContent(sampleMetadata, sampleUrl, 'twitter');
console.log(twitterContent);
console.log('Character count:', twitterContent.length);

console.log('\nLinkedIn format:');
console.log('-'.repeat(50));
const linkedinContent = helpers.formatPostContent(sampleMetadata, sampleUrl, 'linkedin');
console.log(linkedinContent);
console.log('Character count:', linkedinContent.length);

console.log('\nDiscord format:');
console.log('-'.repeat(50));
const discordContent = helpers.formatPostContent(sampleMetadata, sampleUrl, 'discord');
console.log(JSON.stringify(discordContent, null, 2));

console.log('\n');

// Test 4: Test with very long summary (should truncate)
console.log('Test 4: Long Summary Truncation');
console.log('='.repeat(50));

const longSummary = 'A'.repeat(500);
const longMetadata = {
  title: 'Test',
  summary: longSummary,
  tags: []
};

const bskyLong = helpers.formatPostContent(longMetadata, sampleUrl, 'bluesky');
console.log('✅ Bluesky content length:', bskyLong.length, '(should be <= 300)');
console.log('   Is within limit:', bskyLong.length <= 300 ? '✅' : '❌');

const twitterLong = helpers.formatPostContent(longMetadata, sampleUrl, 'twitter');
console.log('✅ Twitter content length:', twitterLong.length, '(should be <= 280)');
console.log('   Is within limit:', twitterLong.length <= 280 ? '✅' : '❌');

console.log('\n');
console.log('✅ All tests completed!');
console.log('\nNote: Git-related functions (detectChangedContent, isNewPost) require');
console.log('      a git repository context and are tested via the GitHub workflow.');
