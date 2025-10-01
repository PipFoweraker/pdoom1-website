#!/usr/bin/env python3
"""Test the new changelog structure"""

import os
import json

def test_changelog_files():
    """Test that both changelog files exist and have correct data structure"""
    base_path = "public"
    
    # Test website changelog
    website_changelog = os.path.join(base_path, "website-changelog", "index.html")
    website_data = os.path.join(base_path, "data", "website-changes.json")
    
    # Test game changelog
    game_changelog = os.path.join(base_path, "game-changelog", "index.html")
    game_data = os.path.join(base_path, "data", "game-changes.json")
    
    print("Testing changelog structure...")
    
    # Test file existence
    for file_path, name in [
        (website_changelog, "Website changelog HTML"),
        (website_data, "Website changelog data"),
        (game_changelog, "Game changelog HTML"),
        (game_data, "Game changelog data")
    ]:
        if os.path.exists(file_path):
            print(f"✓ {name} exists")
        else:
            print(f"✗ {name} missing")
            return False
    
    # Test data structure
    for data_file, name in [(website_data, "Website"), (game_data, "Game")]:
        try:
            with open(data_file, 'r') as f:
                data = json.load(f)
            
            if 'entries' in data and isinstance(data['entries'], list):
                print(f"✓ {name} data structure valid ({len(data['entries'])} entries)")
            else:
                print(f"✗ {name} data structure invalid")
                return False
                
        except json.JSONDecodeError:
            print(f"✗ {name} data invalid JSON")
            return False
        except Exception as e:
            print(f"✗ {name} data error: {e}")
            return False
    
    print("✓ All changelog tests passed!")
    return True

if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    success = test_changelog_files()
    exit(0 if success else 1)