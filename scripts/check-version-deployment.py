#!/usr/bin/env python3
"""
Version Change Detection Script for GitHub Actions

This script checks for version changes and determines deployment approval requirements.
"""

import json
import sys
import os
import subprocess
from typing import Dict, Tuple, Optional

def get_current_version() -> str:
    """Get current version from package.json"""
    try:
        with open('package.json', 'r') as f:
            data = json.load(f)
            return data.get('version', '0.0.0')
    except FileNotFoundError:
        print("❌ package.json not found")
        sys.exit(1)

def get_previous_version() -> Optional[str]:
    """Get the previous version from git tags"""
    try:
        # Get all version tags sorted by version
        result = subprocess.run(
            ['git', 'tag', '-l', 'v*', '--sort=-version:refname'],
            capture_output=True,
            text=True,
            check=True
        )
        tags = result.stdout.strip().split('\n')
        if tags and tags[0]:
            # Return the latest tag without the 'v' prefix
            return tags[0].lstrip('v')
        return None
    except subprocess.CalledProcessError:
        return None

def parse_version(version: str) -> Tuple[int, int, int]:
    """Parse semantic version string into tuple"""
    try:
        parts = version.split('.')
        return (int(parts[0]), int(parts[1]), int(parts[2]))
    except (ValueError, IndexError):
        print(f"❌ Invalid version format: {version}")
        sys.exit(1)

def get_version_change_type(current: str, previous: Optional[str]) -> str:
    """Determine the type of version change"""
    if not previous:
        return "initial"
    
    curr_parts = parse_version(current)
    prev_parts = parse_version(previous)
    
    if curr_parts[0] > prev_parts[0]:
        return "major"
    elif curr_parts[1] > prev_parts[1]:
        return "minor"
    elif curr_parts[2] > prev_parts[2]:
        return "patch"
    elif curr_parts == prev_parts:
        return "none"
    else:
        return "downgrade"

def check_deployment_requirements(change_type: str, current_version: str) -> Dict:
    """Check what approvals are required for deployment"""
    requirements = {
        "can_auto_deploy": True,
        "requires_manual_approval": False,
        "requires_review": False,
        "requires_changelog": False,
        "requires_blog_post": False,
        "warning_message": "",
        "approval_message": ""
    }
    
    if change_type == "major":
        requirements.update({
            "can_auto_deploy": False,
            "requires_manual_approval": True,
            "requires_review": True,
            "requires_changelog": True,
            "requires_blog_post": True,
            "warning_message": f"🚨 MAJOR VERSION CHANGE: v{current_version}",
            "approval_message": "Major version changes require manual approval, changelog updates, and blog post documentation."
        })
    elif change_type == "minor":
        requirements.update({
            "requires_review": True,
            "requires_changelog": True,
            "requires_blog_post": True,
            "warning_message": f"⚠️  MINOR VERSION CHANGE: v{current_version}",
            "approval_message": "Minor version changes should include changelog updates and blog post documentation."
        })
    elif change_type == "patch":
        requirements.update({
            "requires_changelog": True,
            "warning_message": f"📝 PATCH VERSION CHANGE: v{current_version}",
            "approval_message": "Patch version changes should include changelog updates."
        })
    elif change_type == "downgrade":
        requirements.update({
            "can_auto_deploy": False,
            "requires_manual_approval": True,
            "warning_message": f"🚨 VERSION DOWNGRADE DETECTED: v{current_version}",
            "approval_message": "Version downgrades require manual approval and investigation."
        })
    elif change_type == "none":
        requirements.update({
            "warning_message": f"ℹ️  NO VERSION CHANGE: v{current_version}",
            "approval_message": "No version change detected. Deploying current version."
        })
    elif change_type == "initial":
        requirements.update({
            "warning_message": f"🎉 INITIAL VERSION: v{current_version}",
            "approval_message": "Initial version deployment."
        })
    
    return requirements

def check_file_requirements(requirements: Dict) -> Dict:
    """Check if required files exist for the version change"""
    checks = {
        "changelog_updated": False,
        "blog_post_exists": False,
        "version_files_synced": False
    }
    
    current_version = get_current_version()
    
    # Check if changelog is updated
    try:
        with open('public/data/website-changes.json', 'r') as f:
            changelog = json.load(f)
            latest_entry = changelog.get('entries', [{}])[0]
            if latest_entry.get('version') == current_version:
                checks["changelog_updated"] = True
    except FileNotFoundError:
        pass
    
    # Check if blog post exists for this version
    try:
        with open('public/blog/index.json', 'r') as f:
            blog_data = json.load(f)
            for post in blog_data.get('posts', []):
                if 'website' in post.get('tags', []) and current_version in post.get('title', ''):
                    checks["blog_post_exists"] = True
                    break
    except FileNotFoundError:
        pass
    
    # Check if version files are synced
    try:
        with open('public/data/status.json', 'r') as f:
            status = json.load(f)
            if status.get('website', {}).get('version') == current_version:
                checks["version_files_synced"] = True
    except FileNotFoundError:
        pass
    
    return checks

def main():
    """Main function"""
    print("🔍 Checking version changes for deployment...")
    
    current_version = get_current_version()
    previous_version = get_previous_version()
    change_type = get_version_change_type(current_version, previous_version)
    
    print(f"📦 Current Version: v{current_version}")
    if previous_version:
        print(f"📦 Previous Version: v{previous_version}")
    else:
        print("📦 Previous Version: None (initial deployment)")
    print(f"📊 Change Type: {change_type}")
    
    requirements = check_deployment_requirements(change_type, current_version)
    file_checks = check_file_requirements(requirements)
    
    print(f"\n{requirements['warning_message']}")
    print(f"💬 {requirements['approval_message']}")
    
    # Check file requirements
    if requirements['requires_changelog'] and not file_checks['changelog_updated']:
        print("❌ Changelog not updated for this version")
        requirements['can_auto_deploy'] = False
    
    if requirements['requires_blog_post'] and not file_checks['blog_post_exists']:
        print("⚠️  Blog post recommended for this version change")
    
    if not file_checks['version_files_synced']:
        print("❌ Version files not synced (status.json)")
        requirements['can_auto_deploy'] = False
    
    # Output for GitHub Actions
    if os.getenv('GITHUB_ACTIONS'):
        print(f"\n::set-output name=can_auto_deploy::{str(requirements['can_auto_deploy']).lower()}")
        print(f"::set-output name=requires_manual_approval::{str(requirements['requires_manual_approval']).lower()}")
        print(f"::set-output name=change_type::{change_type}")
        print(f"::set-output name=current_version::{current_version}")
        print(f"::set-output name=warning_message::{requirements['warning_message']}")
    
    # Exit with appropriate code
    if not requirements['can_auto_deploy']:
        print("\n🛑 DEPLOYMENT BLOCKED: Manual approval required")
        sys.exit(1)
    else:
        print("\n✅ DEPLOYMENT APPROVED: Can proceed automatically")
        sys.exit(0)

if __name__ == "__main__":
    main()