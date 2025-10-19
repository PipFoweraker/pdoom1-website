// Syndication Helper Utilities
// Common functions for extracting content and formatting posts for social media

const fs = require('fs');
const path = require('path');

/**
 * Extract metadata from markdown blog post
 * @param {string} filePath - Path to markdown file
 * @returns {object} - Extracted metadata and content
 */
function extractBlogMetadata(filePath) {
  const content = fs.readFileSync(filePath, 'utf8');
  const lines = content.split('\n');
  
  // Extract title (first # heading)
  const titleMatch = content.match(/^#\s+(.+)$/m);
  const title = titleMatch ? titleMatch[1] : 'New Update';
  
  // Extract date
  const dateMatch = content.match(/\*\*Date\*\*:\s*(\d{4}-\d{2}-\d{2})/);
  const date = dateMatch ? dateMatch[1] : new Date().toISOString().split('T')[0];
  
  // Extract tags
  const tagsMatch = content.match(/\*\*Tags\*\*:\s*\[([^\]]+)\]/);
  const tags = tagsMatch ? tagsMatch[1].split(',').map(t => t.trim()) : [];
  
  // Extract summary
  const summaryMatch = content.match(/##\s+Summary\s+(.+?)(?=\n##|\n\n##|$)/s);
  let summary = summaryMatch ? summaryMatch[1].trim() : '';
  
  // If no summary section, try to get first paragraph after title
  if (!summary) {
    const firstParaMatch = content.match(/^#.+?\n\n(.+?)(?=\n\n|$)/s);
    summary = firstParaMatch ? firstParaMatch[1].trim() : '';
  }
  
  // Truncate summary if too long
  if (summary.length > 280) {
    summary = summary.substring(0, 277) + '...';
  }
  
  return {
    title,
    date,
    tags,
    summary,
    content
  };
}

/**
 * Generate URL for blog post
 * @param {string} filename - Blog post filename
 * @param {string} baseUrl - Base URL of website
 * @returns {string} - Full URL to blog post
 */
function generateBlogUrl(filename, baseUrl = 'https://pdoom1.com') {
  // Extract slug from filename (remove date prefix and .md extension)
  const slug = filename.replace(/^\d{4}-\d{2}-\d{2}-/, '').replace(/\.md$/, '');
  return `${baseUrl}/blog/#${slug}`;
}

/**
 * Format content for different platforms
 * @param {object} metadata - Extracted metadata
 * @param {string} url - Full URL to content
 * @param {string} platform - Target platform (bluesky, twitter, linkedin, discord)
 * @returns {string} - Formatted post content
 */
function formatPostContent(metadata, url, platform = 'bluesky') {
  const { title, summary, tags } = metadata;
  
  switch (platform) {
    case 'bluesky':
      // Bluesky allows 300 characters
      const bskyContent = `🎮 ${title}\n\n${summary}\n\n🔗 ${url}`;
      return bskyContent.length > 300 ? bskyContent.substring(0, 297) + '...' : bskyContent;
      
    case 'twitter':
    case 'x':
      // Twitter allows 280 characters
      const twitterContent = `🎮 ${title}\n\n${summary}\n\n${url}`;
      return twitterContent.length > 280 ? twitterContent.substring(0, 277) + '...' : twitterContent;
      
    case 'linkedin':
      // LinkedIn allows more text, so we can be more verbose
      return `${title}\n\n${summary}\n\nRead more: ${url}\n\n${tags.map(t => `#${t.replace(/\s+/g, '')}`).join(' ')}`;
      
    case 'discord':
      // Discord embeds
      return {
        embeds: [{
          title: title,
          description: summary,
          url: url,
          color: 0x00FF00, // Green color
          footer: {
            text: tags.join(', ')
          },
          timestamp: new Date().toISOString()
        }]
      };
      
    default:
      return `${title}\n\n${summary}\n\n${url}`;
  }
}

/**
 * Detect changed blog/changelog files from git diff
 * @param {string} repoPath - Path to repository
 * @param {string} beforeSha - Commit SHA before changes
 * @param {string} afterSha - Commit SHA after changes  
 * @returns {Array<string>} - Array of changed file paths
 */
function detectChangedContent(repoPath, beforeSha = 'HEAD~1', afterSha = 'HEAD') {
  const { execSync } = require('child_process');
  
  try {
    // Get list of changed files in blog and changelog directories
    const diffOutput = execSync(
      `git diff --name-only ${beforeSha} ${afterSha} -- "public/blog/*.md" "public/*-changelog/*.md"`,
      { cwd: repoPath, encoding: 'utf8' }
    );
    
    return diffOutput.trim().split('\n').filter(Boolean);
  } catch (error) {
    console.error('Error detecting changed content:', error.message);
    return [];
  }
}

/**
 * Check if file is a new blog post (not just an edit)
 * @param {string} repoPath - Path to repository
 * @param {string} filePath - Relative path to file
 * @param {string} beforeSha - Commit SHA before changes
 * @returns {boolean} - True if file is new
 */
function isNewPost(repoPath, filePath, beforeSha = 'HEAD~1') {
  const { execSync } = require('child_process');
  
  try {
    // Check if file existed in previous commit
    execSync(
      `git cat-file -e ${beforeSha}:${filePath}`,
      { cwd: repoPath, stdio: 'ignore' }
    );
    return false; // File existed, so it's an edit
  } catch (error) {
    return true; // File didn't exist, so it's new
  }
}

module.exports = {
  extractBlogMetadata,
  generateBlogUrl,
  formatPostContent,
  detectChangedContent,
  isNewPost
};
