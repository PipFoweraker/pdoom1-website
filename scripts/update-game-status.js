#!/usr/bin/env node

/**
 * Update Game Status Script
 * 
 * This script updates the website's game status information.
 * Can be triggered by:
 * 1. GitHub Actions from the main game repository
 * 2. Manual execution for status updates
 * 3. Scheduled updates via cron/GitHub Actions
 */

const fs = require('fs');
const path = require('path');

// Configuration
const STATUS_FILE = path.join(__dirname, '../public/data/status.json');
const GAME_REPO = 'PipFoweraker/pdoom1';

/**
 * Update game status with new information
 * @param {Object} gameInfo - New game information
 */
function updateGameStatus(gameInfo) {
    try {
        // Read current status
        const currentStatus = JSON.parse(fs.readFileSync(STATUS_FILE, 'utf8'));
        
        // Update game section
        currentStatus.game = {
            ...currentStatus.game,
            ...gameInfo,
            lastUpdated: new Date().toISOString()
        };
        
        // Update website version (increment patch)
        const [major, minor, patch] = currentStatus.website.version.split('.').map(Number);
        currentStatus.website.version = `${major}.${minor}.${patch + 1}`;
        currentStatus.website.lastUpdated = new Date().toISOString();
        
        // Write updated status
        fs.writeFileSync(STATUS_FILE, JSON.stringify(currentStatus, null, 2));
        
        console.log('✅ Game status updated successfully');
        console.log(`📦 Website version: ${currentStatus.website.version}`);
        console.log(`🎮 Game version: ${currentStatus.game.latestRelease.version}`);
        
        return currentStatus;
    } catch (error) {
        console.error('❌ Error updating game status:', error);
        process.exit(1);
    }
}

/**
 * Fetch latest release info from GitHub API
 */
async function fetchLatestRelease() {
    try {
        const response = await fetch(`https://api.github.com/repos/${GAME_REPO}/releases/latest`);
        const release = await response.json();
        
        return {
            version: release.tag_name,
            date: release.published_at.split('T')[0],
            downloadUrl: release.html_url,
            changelog: release.name || release.body?.split('\n')[0] || 'Latest release'
        };
    } catch (error) {
        console.warn('⚠️  Could not fetch latest release, using manual data');
        return null;
    }
}

// CLI Usage
if (require.main === module) {
    const args = process.argv.slice(2);
    
    if (args.includes('--help') || args.includes('-h')) {
        console.log(`
Usage: node update-game-status.js [options]

Options:
  --version <version>     Set game version (e.g., v0.4.2)
  --status <status>       Set game status (alpha, beta, release)
  --warning <text>        Set warning message
  --phase <phase>         Set development phase
  --progress <progress>   Set development progress
  --fetch-release         Automatically fetch latest GitHub release
  --help, -h              Show this help

Examples:
  node update-game-status.js --version v0.4.2 --phase "Bug fixing sprint"
  node update-game-status.js --fetch-release
  node update-game-status.js --status beta --warning "Beta version - mostly stable"
        `);
        process.exit(0);
    }
    
    // Parse command line arguments
    const updates = {};
    
    if (args.includes('--fetch-release')) {
        fetchLatestRelease().then(release => {
            if (release) {
                updates.latestRelease = release;
            }
            
            // Apply other arguments
            const versionIndex = args.indexOf('--version');
            const statusIndex = args.indexOf('--status');
            const warningIndex = args.indexOf('--warning');
            const phaseIndex = args.indexOf('--phase');
            const progressIndex = args.indexOf('--progress');
            
            if (versionIndex !== -1 && args[versionIndex + 1]) {
                updates.latestRelease = updates.latestRelease || {};
                updates.latestRelease.version = args[versionIndex + 1];
            }
            
            if (statusIndex !== -1 && args[statusIndex + 1]) {
                updates.status = args[statusIndex + 1];
            }
            
            if (warningIndex !== -1 && args[warningIndex + 1]) {
                updates.warning = args[warningIndex + 1];
            }
            
            if (phaseIndex !== -1 && args[phaseIndex + 1]) {
                updates.development = updates.development || {};
                updates.development.phase = args[phaseIndex + 1];
            }
            
            if (progressIndex !== -1 && args[progressIndex + 1]) {
                updates.development = updates.development || {};
                updates.development.progress = args[progressIndex + 1];
            }
            
            updateGameStatus(updates);
        });
    } else {
        // Manual updates
        const versionIndex = args.indexOf('--version');
        const statusIndex = args.indexOf('--status');
        const warningIndex = args.indexOf('--warning');
        const phaseIndex = args.indexOf('--phase');
        const progressIndex = args.indexOf('--progress');
        
        if (versionIndex !== -1 && args[versionIndex + 1]) {
            updates.latestRelease = { version: args[versionIndex + 1] };
        }
        
        if (statusIndex !== -1 && args[statusIndex + 1]) {
            updates.status = args[statusIndex + 1];
        }
        
        if (warningIndex !== -1 && args[warningIndex + 1]) {
            updates.warning = args[warningIndex + 1];
        }
        
        if (phaseIndex !== -1 && args[phaseIndex + 1]) {
            updates.development = updates.development || {};
            updates.development.phase = args[phaseIndex + 1];
        }
        
        if (progressIndex !== -1 && args[progressIndex + 1]) {
            updates.development = updates.development || {};
            updates.development.progress = args[progressIndex + 1];
        }
        
        if (Object.keys(updates).length === 0) {
            console.log('No updates specified. Use --help for usage information.');
            process.exit(1);
        }
        
        updateGameStatus(updates);
    }
}

module.exports = { updateGameStatus, fetchLatestRelease };
