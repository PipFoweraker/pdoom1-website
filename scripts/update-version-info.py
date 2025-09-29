#!/usr/bin/env python3
"""
Updates version information from the pdoom1 game repository
Fetches latest release info and updates website data files
"""

import json
import os
import re
import urllib.request
from datetime import datetime
from typing import Dict, Any, Optional

GITHUB_API_BASE = 'https://api.github.com'
REPO_OWNER = 'PipFoweraker'
REPO_NAME = 'pdoom1'
DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'public', 'data')


def fetch_github_data(endpoint: str) -> Optional[Dict[str, Any]]:
    """Fetch data from GitHub API"""
    url = f"{GITHUB_API_BASE}{endpoint}"
    
    try:
        req = urllib.request.Request(url)
        req.add_header('User-Agent', 'pdoom1-website-updater')
        req.add_header('Accept', 'application/vnd.github.v3+json')
        
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read())
    except Exception as e:
        print(f"Warning: Could not fetch {endpoint}: {e}")
        return None


def get_latest_release() -> Dict[str, Any]:
    """Get latest release information"""
    data = fetch_github_data(f"/repos/{REPO_OWNER}/{REPO_NAME}/releases/latest")
    
    if data:
        return {
            'version': data.get('tag_name') or data.get('name'),
            'name': data.get('name'),
            'published_at': data.get('published_at'),
            'html_url': data.get('html_url'),
            'body': data.get('body', '')
        }
    else:
        # Fallback if API fails
        return {
            'version': 'v0.4.1',
            'name': 'Latest Release',
            'published_at': datetime.now().isoformat(),
            'html_url': f'https://github.com/{REPO_OWNER}/{REPO_NAME}/releases',
            'body': 'Latest development version'
        }


def get_repo_stats() -> Dict[str, Any]:
    """Get repository statistics"""
    data = fetch_github_data(f"/repos/{REPO_OWNER}/{REPO_NAME}")
    
    if data:
        return {
            'stars': data.get('stargazers_count', 0),
            'forks': data.get('forks_count', 0),
            'open_issues': data.get('open_issues_count', 0),
            'last_updated': data.get('updated_at')
        }
    else:
        return {
            'stars': 0,
            'forks': 0,
            'open_issues': 0,
            'last_updated': datetime.now().isoformat()
        }


def update_version_data() -> Dict[str, Any]:
    """Update version data file"""
    print('Fetching version information...')
    
    release = get_latest_release()
    stats = get_repo_stats()
    
    version_data: Dict[str, Any] = {
        'latest_release': release,
        'repository_stats': stats,
        'last_updated': datetime.now().isoformat(),
        'game_stats': {
            # These will be calculated separately or stubbed for now
            'baseline_doom_percent': 23,
            'frontier_labs_count': 7,
            'strategic_possibilities': 10000
        }
    }
    
    # Ensure data directory exists
    os.makedirs(DATA_DIR, exist_ok=True)
    
    # Write version data
    version_file = os.path.join(DATA_DIR, 'version.json')
    with open(version_file, 'w') as f:
        json.dump(version_data, f, indent=2)
    
    print(f"✓ Version data updated: {release['version']}")
    print(f"✓ Written to: {version_file}")
    
    return version_data


def update_download_links(version_data: Dict[str, Any]) -> None:
    """Update download links in index.html to use dynamic version"""
    index_file = os.path.join(os.path.dirname(__file__), '..', 'public', 'index.html')
    
    if not os.path.exists(index_file):
        print('index.html not found, skipping link updates')
        return
    
    with open(index_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    version = version_data['latest_release']['version']
    
    # Update download button text to show current version
    content = re.sub(
        r'Download Latest Release',
        f'Download {version} (Latest)',
        content
    )
    
    # Update any hardcoded version references
    content = re.sub(
        r'Download v[\d\.]+',
        f'Download {version}',
        content
    )
    
    with open(index_file, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"✓ Updated download links to {version}")


if __name__ == '__main__':
    try:
        version_data = update_version_data()
        update_download_links(version_data)
        print('Version update complete!')
    except Exception as error:
        print(f'Error updating version: {error}')
        exit(1)