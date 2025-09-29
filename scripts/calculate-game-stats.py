#!/usr/bin/env python3
"""
Calculates real frontier labs count from the AI Safety Resources section
and updates game stats accordingly
"""

import json
import os
from datetime import datetime
from typing import Dict, Any, List


def count_frontier_labs() -> int:
    """Count frontier labs mentioned in the resources section"""
    
    # Define known frontier AI labs/organizations
    frontier_labs: List[str] = [
        'OpenAI',
        'Anthropic', 
        'DeepMind',
        'Google DeepMind',
        'Meta AI',
        'Inflection AI',
        'Cohere',
        'AI21 Labs',
        'Stability AI',
        'Midjourney',
        'Character.AI',
        'Hugging Face',
        'Adept',
        'Mistral AI',
        'Runway',
        'Scale AI'
    ]
    
    # Read the index.html file to check which ones are mentioned
    index_file = os.path.join(os.path.dirname(__file__), '..', 'public', 'index.html')
    
    if not os.path.exists(index_file):
        print('index.html not found')
        return 7  # fallback
    
    with open(index_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Count mentions in the AI Safety Resources section
    mentioned_labs: List[str] = []
    for lab in frontier_labs:
        if lab.lower() in content.lower():
            mentioned_labs.append(lab)
    
    # Add research organizations that are doing frontier work
    research_orgs: List[str] = [
        'Machine Intelligence Research Institute',
        'Center for AI Safety', 
        'Center for Human-Compatible AI',
        'Future of Humanity Institute'
    ]
    
    for org in research_orgs:
        if org.lower() in content.lower():
            mentioned_labs.append(org)
    
    print(f"Found {len(mentioned_labs)} frontier organizations mentioned:")
    for lab in mentioned_labs:
        print(f"  - {lab}")
    
    # Return the count, with a minimum of 5 to represent major players
    return max(len(mentioned_labs), 5)


def update_game_stats() -> Dict[str, Any]:
    """Update the game stats with calculated values"""
    
    data_dir = os.path.join(os.path.dirname(__file__), '..', 'public', 'data')
    version_file = os.path.join(data_dir, 'version.json')
    
    # Load existing version data
    if os.path.exists(version_file):
        with open(version_file, 'r') as f:
            version_data: Dict[str, Any] = json.load(f)
    else:
        print('version.json not found, creating basic structure')
        version_data = {
            'game_stats': {},
            'last_updated': datetime.now().isoformat()
        }
    
    # Calculate real values
    frontier_count = count_frontier_labs()
    
    # Update game stats
    if 'game_stats' not in version_data:
        version_data['game_stats'] = {}
        
    version_data['game_stats'].update({
        'frontier_labs_count': frontier_count,
        'baseline_doom_percent': 23,  # Keep stubbed for now
        'strategic_possibilities': 10000,  # Keep large number for now
        'last_calculated': datetime.now().isoformat()
    })
    
    version_data['last_updated'] = datetime.now().isoformat()
    
    # Save updated data
    os.makedirs(data_dir, exist_ok=True)
    with open(version_file, 'w') as f:
        json.dump(version_data, f, indent=2)
    
    print(f"✓ Updated frontier labs count to: {frontier_count}")
    print(f"✓ Saved to: {version_file}")
    
    return version_data


if __name__ == '__main__':
    try:
        update_game_stats()
        print('Game stats calculation complete!')
    except Exception as error:
        print(f'Error calculating game stats: {error}')
        exit(1)