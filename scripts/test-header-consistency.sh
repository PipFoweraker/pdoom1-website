#!/usr/bin/env bash

# Test script to verify header consistency and emoji removal across all HTML pages
# Usage: bash scripts/test-header-consistency.sh

echo "Testing header consistency and emoji removal..."
echo

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Counters
total_files=0
passed_files=0
total_errors=0

# Find all HTML files
html_files=$(find public -name "index.html" -type f)

echo "Found HTML files to test:"
for file in $html_files; do
    echo "  $file"
    ((total_files++))
done
echo

echo "============================================================"
echo "TEST RESULTS"
echo "============================================================"

# Test each file
for file in $html_files; do
    errors=()
    
    # Test 1: Check for header element
    if ! grep -q '<header>' "$file"; then
        errors+=("Missing <header> element")
    fi
    
    # Test 2: Check for navigation with proper ARIA
    if ! grep -q 'role="navigation"' "$file" || ! grep -q 'aria-label="Main navigation"' "$file"; then
        errors+=("Missing nav with proper ARIA attributes")
    fi
    
    # Test 3: Check for designer credit
    if ! grep -q 'class="designer-credit"' "$file"; then
        errors+=("Missing designer credit (.designer-credit)")
    elif ! grep -q "Pip Foweraker's" "$file"; then
        errors+=("Designer credit does not contain 'Pip Foweraker's'")
    fi
    
    # Test 4: Check for logo container
    if ! grep -q 'class="logo-container"' "$file"; then
        errors+=("Missing logo container (.logo-container)")
    fi
    
    # Test 5: Check for dropdown navigation
    dropdown_count=$(grep -c 'class="dropdown"' "$file" || echo 0)
    if [ "$dropdown_count" -lt 2 ]; then
        errors+=("Missing dropdown navigation elements (expected at least 2, found $dropdown_count)")
    fi
    
    # Test 6: Check for required dropdown labels
    if ! grep -q 'Community ▾' "$file"; then
        errors+=("Missing required dropdown: 'Community ▾'")
    fi
    if ! grep -q 'Info ▾' "$file"; then
        errors+=("Missing required dropdown: 'Info ▾'")
    fi
    
    # Test 7: Check for required main navigation links
    if ! grep -q 'role="menuitem"[^>]*>Game<' "$file"; then
        errors+=("Missing required navigation link: 'Game'")
    fi
    if ! grep -q 'role="menuitem"[^>]*>Leaderboard<' "$file"; then
        errors+=("Missing required navigation link: 'Leaderboard'")
    fi
    
    # Test 8: Check for emojis (common ones)
    emojis=(
        "🎮" "🏆" "📊" "💡" "🔧" "🎯" "📈" "🚀" "⚡" "🌟" "📝" "💻" "🔍" "🎲" "📞" "🛡️" "✨" "📰" 
        "🎭" "🔬" "🎨" "🏅" "⭐" "🎪" "📚" "🔥" "💥" "⚠️" "⬇️" "👨‍💻" "✉️"
    )
    
    for emoji in "${emojis[@]}"; do
        if grep -q "$emoji" "$file"; then
            errors+=("Found emoji: '$emoji'")
        fi
    done
    
    # Display results for this file
    relative_path=$(echo "$file" | sed 's|^public/||')
    if [ ${#errors[@]} -eq 0 ]; then
        echo -e "${GREEN}PASS${NC} $relative_path"
        ((passed_files++))
    else
        echo -e "${RED}FAIL${NC} $relative_path"
        for error in "${errors[@]}"; do
            echo "  • $error"
            ((total_errors++))
        done
        echo
    fi
done

echo "============================================================"
echo "SUMMARY: $passed_files/$total_files files passed"
echo "Total errors: $total_errors"

if [ $total_errors -eq 0 ]; then
    echo -e "${GREEN}All tests passed! Header structure is consistent and emojis have been removed.${NC}"
    exit 0
else
    echo -e "${RED}Some tests failed. Please address the errors above.${NC}"
    exit 1
fi
