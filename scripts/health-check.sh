#!/bin/bash

# P(DOOM)1 Website Health Check
# Comprehensive validation of site structure and configuration

set -e

echo "============================================================"
echo "P(DOOM)1 WEBSITE HEALTH CHECK"
echo "============================================================"

cd "$(dirname "$0")/.."

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Counters
checks_passed=0
checks_failed=0
total_checks=0

check_result() {
    ((total_checks++))
    if [ "$1" = "PASS" ]; then
        echo -e "${GREEN}✓ PASS${NC} $2"
        ((checks_passed++))
    else
        echo -e "${RED}✗ FAIL${NC} $2"
        if [ -n "$3" ]; then
            echo "    $3"
        fi
        ((checks_failed++))
    fi
}

echo "🔍 Checking core HTML pages..."

# Check all required HTML pages exist
pages=(
    "public/index.html:Main homepage"
    "public/about/index.html:About page"
    "public/blog/index.html:Blog index"
    "public/changelog/index.html:Changelog page"
    "public/leaderboard/index.html:Leaderboard page"
    "public/dev-notes/index.html:Dev notes page"
    "public/docs/index.html:Documentation page"
    "public/press/index.html:Press kit page"
)

for page_info in "${pages[@]}"; do
    IFS=':' read -r file desc <<< "$page_info"
    if [ -f "$file" ] && [ -s "$file" ]; then
        check_result "PASS" "$desc exists and is not empty"
    else
        check_result "FAIL" "$desc missing or empty" "File: $file"
    fi
done

echo
echo "📁 Checking asset files..."

# Check key assets exist
assets=(
    "public/assets/pdoom_logo_1.png:Main logo"
    "public/assets/8-bit-effect.gif:8-bit effect animation"
    "public/robots.txt:Robots.txt file"
    "public/sitemap.xml:XML sitemap"
    "public/config.json:Configuration file"
)

for asset_info in "${assets[@]}"; do
    IFS=':' read -r file desc <<< "$asset_info"
    if [ -f "$file" ]; then
        check_result "PASS" "$desc exists"
    else
        check_result "FAIL" "$desc missing" "File: $file"
    fi
done

echo
echo "🔧 Checking configuration files..."

# Check configuration files
configs=(
    "netlify.toml:Netlify configuration"
    "vercel.json:Vercel configuration"  
    "package.json:NPM package file"
    "README.md:Project README"
)

for config_info in "${configs[@]}"; do
    IFS=':' read -r file desc <<< "$config_info"
    if [ -f "$file" ]; then
        check_result "PASS" "$desc exists"
    else
        check_result "FAIL" "$desc missing" "File: $file"
    fi
done

echo
echo "📊 Checking data files..."

# Check data files
data_files=(
    "public/data/blog.json:Blog data"
    "public/data/changes.json:Changelog data"
    "public/design/tokens.json:Design tokens"
)

for data_info in "${data_files[@]}"; do
    IFS=':' read -r file desc <<< "$data_info"
    if [ -f "$file" ]; then
        check_result "PASS" "$desc exists"
    else
        check_result "FAIL" "$desc missing" "File: $file"
    fi
done

echo
echo "🌐 Checking HTML structure..."

# Check for critical HTML elements in main pages
html_checks=(
    "public/index.html:<title>:Page title"
    "public/index.html:<meta name=\"description\":Meta description"
    "public/index.html:role=\"navigation\":Navigation ARIA"
    "public/index.html:Pip Foweraker's:Designer attribution"
)

for check_info in "${html_checks[@]}"; do
    IFS=':' read -r file pattern desc <<< "$check_info"
    if [ -f "$file" ] && grep -q "$pattern" "$file"; then
        check_result "PASS" "$desc found in $(basename "$file")"
    else
        check_result "FAIL" "$desc missing in $(basename "$file")" "Pattern: $pattern"
    fi
done

echo
echo "📝 Checking documentation..."

# Check documentation files
docs=(
    "docs/DEV_NOTES.md:Development notes"
    "docs/roadmap.md:Project roadmap"
    "docs/deployment-guide.md:Deployment guide"
    "docs/INDEX.md:Documentation index"
)

for doc_info in "${docs[@]}"; do
    IFS=':' read -r file desc <<< "$doc_info"
    if [ -f "$file" ]; then
        check_result "PASS" "$desc exists"
    else
        check_result "FAIL" "$desc missing" "File: $file"
    fi
done

echo
echo "🔍 Checking for common issues..."

# Check for development artifacts
if grep -r "TODO\|FIXME\|XXX" public/ --include="*.html" >/dev/null 2>&1; then
    check_result "FAIL" "No development artifacts in production files" "Found TODO/FIXME/XXX comments"
else
    check_result "PASS" "No development artifacts in production files"
fi

# Check for localhost references
if grep -r "localhost\|127.0.0.1" public/ --include="*.html" --include="*.json" >/dev/null 2>&1; then
    check_result "FAIL" "No localhost references in production files" "Found localhost URLs"
else
    check_result "PASS" "No localhost references in production files"
fi

# Check for broken internal links (basic check)
if grep -r "href=\"#\"" public/ --include="*.html" | grep -v "dropdown-toggle" >/dev/null 2>&1; then
    check_result "FAIL" "No broken internal links" "Found href='#' links (excluding dropdowns)"
else
    check_result "PASS" "No obvious broken internal links"
fi

echo
echo "============================================================"
echo "HEALTH CHECK SUMMARY"
echo "============================================================"

if [ $checks_failed -eq 0 ]; then
    echo -e "${GREEN}🎉 ALL CHECKS PASSED!${NC}"
    echo "✅ $checks_passed/$total_checks checks successful"
    echo "🚀 Website is production-ready!"
    exit_code=0
else
    echo -e "${RED}⚠️  SOME CHECKS FAILED${NC}"
    echo "✅ $checks_passed/$total_checks checks passed"
    echo "❌ $checks_failed/$total_checks checks failed"
    echo "🔧 Please address the issues above before deployment"
    exit_code=1
fi

echo
echo "📊 Site Statistics:"
echo "   - HTML pages: $(find public -name "*.html" | wc -l)"
echo "   - Documentation files: $(find docs -name "*.md" | wc -l)"
echo "   - Asset files: $(find public/assets -type f | wc -l)"
echo "   - Total project files: $(find . -type f -not -path './.git/*' -not -path './node_modules/*' | wc -l)"

exit $exit_code
