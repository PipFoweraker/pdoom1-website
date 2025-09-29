#!/usr/bin/env node

/**
 * Updates version information from the pdoom1 game repository
 * Fetches latest release info and updates website data files
 */

const https = require('https');
const fs = require('fs');
const path = require('path');

const GITHUB_API_BASE = 'https://api.github.com';
const REPO_OWNER = 'PipFoweraker';
const REPO_NAME = 'pdoom1';
const DATA_DIR = path.join(__dirname, '..', 'public', 'data');

/**
 * Fetch data from GitHub API
 */
function fetchGitHubData(endpoint) {
    return new Promise((resolve, reject) => {
        const options = {
            hostname: 'api.github.com',
            path: endpoint,
            method: 'GET',
            headers: {
                'User-Agent': 'pdoom1-website-updater',
                'Accept': 'application/vnd.github.v3+json'
            }
        };

        const req = https.request(options, (res) => {
            let data = '';
            res.on('data', chunk => data += chunk);
            res.on('end', () => {
                try {
                    resolve(JSON.parse(data));
                } catch (e) {
                    reject(new Error(`Failed to parse JSON: ${e.message}`));
                }
            });
        });

        req.on('error', reject);
        req.end();
    });
}

/**
 * Get latest release information
 */
async function getLatestRelease() {
    try {
        const release = await fetchGitHubData(`/repos/${REPO_OWNER}/${REPO_NAME}/releases/latest`);
        return {
            version: release.tag_name || release.name,
            name: release.name,
            published_at: release.published_at,
            html_url: release.html_url,
            body: release.body
        };
    } catch (error) {
        console.warn('Could not fetch latest release:', error.message);
        // Fallback to current version if API fails
        return {
            version: 'v0.4.1',
            name: 'Latest Release',
            published_at: new Date().toISOString(),
            html_url: `https://github.com/${REPO_OWNER}/${REPO_NAME}/releases`,
            body: 'Latest development version'
        };
    }
}

/**
 * Get repository statistics
 */
async function getRepoStats() {
    try {
        const repo = await fetchGitHubData(`/repos/${REPO_OWNER}/${REPO_NAME}`);
        return {
            stars: repo.stargazers_count || 0,
            forks: repo.forks_count || 0,
            open_issues: repo.open_issues_count || 0,
            last_updated: repo.updated_at
        };
    } catch (error) {
        console.warn('Could not fetch repo stats:', error.message);
        return {
            stars: 0,
            forks: 0,
            open_issues: 0,
            last_updated: new Date().toISOString()
        };
    }
}

/**
 * Update version data file
 */
async function updateVersionData() {
    console.log('Fetching version information...');
    
    const [release, stats] = await Promise.all([
        getLatestRelease(),
        getRepoStats()
    ]);

    const versionData = {
        latest_release: release,
        repository_stats: stats,
        last_updated: new Date().toISOString(),
        game_stats: {
            // These will be calculated separately or stubbed for now
            baseline_doom_percent: 23,
            frontier_labs_count: 7,
            strategic_possibilities: 10000
        }
    };

    // Ensure data directory exists
    if (!fs.existsSync(DATA_DIR)) {
        fs.mkdirSync(DATA_DIR, { recursive: true });
    }

    // Write version data
    const versionFile = path.join(DATA_DIR, 'version.json');
    fs.writeFileSync(versionFile, JSON.stringify(versionData, null, 2));
    
    console.log(`✓ Version data updated: ${release.version}`);
    console.log(`✓ Written to: ${versionFile}`);
    
    return versionData;
}

/**
 * Update download links in index.html to use dynamic version
 */
function updateDownloadLinks(versionData) {
    const indexFile = path.join(__dirname, '..', 'public', 'index.html');
    
    if (!fs.existsSync(indexFile)) {
        console.warn('index.html not found, skipping link updates');
        return;
    }

    let content = fs.readFileSync(indexFile, 'utf8');
    const version = versionData.latest_release.version;
    
    // Update download button text to show current version
    content = content.replace(
        /Download Latest Release/g,
        `Download ${version} (Latest)`
    );
    
    // Update any hardcoded version references
    content = content.replace(
        /Download v[\d\.]+/g,
        `Download ${version}`
    );
    
    fs.writeFileSync(indexFile, content);
    console.log(`✓ Updated download links to ${version}`);
}

// Main execution
if (require.main === module) {
    updateVersionData()
        .then(versionData => {
            updateDownloadLinks(versionData);
            console.log('Version update complete!');
        })
        .catch(error => {
            console.error('Error updating version:', error);
            process.exit(1);
        });
}

module.exports = { updateVersionData, getLatestRelease, getRepoStats };