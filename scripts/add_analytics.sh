#!/bin/bash
# Add Plausible Analytics script to all HTML files

ANALYTICS_SCRIPT='	<!-- Plausible Analytics - Privacy-first, self-hosted analytics -->
	<script defer data-domain="pdoom1.com" src="https://analytics.pdoom1.com/js/script.js"></script>
'

# Find all HTML files in public/ (excluding includes/)
find public -name "*.html" ! -path "*/includes/*" | while read -r file; do
	# Skip if already has analytics
	if grep -q "analytics.pdoom1.com" "$file"; then
		echo "✓ $file (already has analytics)"
		continue
	fi

	# Check if file has <style> tag
	if grep -q "<style>" "$file"; then
		# Insert analytics before <style> tag
		sed -i "/<style>/i\\
$ANALYTICS_SCRIPT
" "$file"
		echo "✓ $file (added analytics)"
	else
		echo "- $file (no <style> tag found)"
	fi
done

echo ""
echo "Done! Verify analytics tracking:"
echo "1. Deploy to production"
echo "2. Visit https://analytics.pdoom1.com"
echo "3. Browse pages and check real-time dashboard"
