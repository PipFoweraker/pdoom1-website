#!/usr/bin/env node

const fs = require('fs');
const path = require('path');

// Configuration
const BASE_URL = 'https://pdoom1.com';
const PUBLIC_DIR = path.join(__dirname, '..', 'public');
const SITEMAP_PATH = path.join(PUBLIC_DIR, 'sitemap.xml');

// Route definitions with priority and change frequency
const routes = [
  { path: '/', priority: '1.0', changefreq: 'weekly' },
  { path: '/about/', priority: '0.9', changefreq: 'monthly' },
  { path: '/blog/', priority: '0.8', changefreq: 'weekly' },
  { path: '/changelog/', priority: '0.8', changefreq: 'weekly' },
  { path: '/press/', priority: '0.8', changefreq: 'monthly' },
  { path: '/leaderboard/', priority: '0.8', changefreq: 'daily' },
  { path: '/resources/', priority: '0.7', changefreq: 'monthly' },
  { path: '/game-stats/', priority: '0.7', changefreq: 'weekly' },
  { path: '/docs/', priority: '0.7', changefreq: 'weekly' },
  // Static markdown files
  { path: '/docs/roadmap.md', priority: '0.6', changefreq: 'weekly' },
  { path: '/docs/pdoom1-open-issues.md', priority: '0.6', changefreq: 'daily' },
  { path: '/docs/DEV_NOTES.md', priority: '0.5', changefreq: 'weekly' },
  { path: '/docs/how-leaderboards-work.md', priority: '0.6', changefreq: 'monthly' },
  { path: '/docs/steam-readiness.md', priority: '0.6', changefreq: 'weekly' },
];

function generateSitemap() {
  const now = new Date().toISOString().split('T')[0]; // YYYY-MM-DD format
  
  let xml = '<?xml version="1.0" encoding="UTF-8"?>\n';
  xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n';
  
  for (const route of routes) {
    xml += '  <url>\n';
    xml += `    <loc>${BASE_URL}${route.path}</loc>\n`;
    xml += `    <changefreq>${route.changefreq}</changefreq>\n`;
    xml += `    <priority>${route.priority}</priority>\n`;
    xml += '  </url>\n';
  }
  
  xml += '</urlset>\n';
  
  return xml;
}

function main() {
  try {
    const sitemap = generateSitemap();
    fs.writeFileSync(SITEMAP_PATH, sitemap, 'utf8');
    console.log(`✅ Sitemap generated successfully at ${SITEMAP_PATH}`);
    console.log(`📊 Generated ${routes.length} URLs`);
  } catch (error) {
    console.error('❌ Error generating sitemap:', error);
    process.exit(1);
  }
}

if (require.main === module) {
  main();
}

module.exports = { generateSitemap, routes };