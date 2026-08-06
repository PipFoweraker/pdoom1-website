# ============================================================================
# PARKED 2026-08-06 -- RETURN DATE: 2026-09-02
#
# Pip's ruling, 2026-08-06: "Park with a date." Recorded per coordination's
# PRINT_AND_PROCESS_REFERENCE section 5c, binding 2026-08-05: a park REQUIRES a
# return date, and "parking without a date is abandonment with better manners".
#
# WHY IT CANNOT RUN TODAY
#   The three paths below point at C:\Users\gday\Documents\A Local Code\...
#   That directory does not exist -- this repo lives at D:\Local_Code -- so the
#   script exits at its first file read. It has been broken since the repo moved
#   and nobody noticed, because nothing calls it: no workflow, no package.json
#   script, no other script.
#
# WHY IT IS PARKED RATHER THAN DELETED
#   The forum is DORMANT, not dead, and the distinction is load-bearing here.
#   NodeBB is running right now on port 80 of 208.113.200.215. What it lacks is
#   a DNS record for forum.pdoom1.com. So this script targets a LIVE service by
#   a broken LOCAL path -- deleting it would discard the only theming recipe for
#   a forum that still exists. forum-theme.css is still at the repo root,
#   unreferenced by anything else.
#
# WHAT FORCES THE RE-DECISION ON 2026-09-02
#   The forum's keep-or-kill call -- issues #60, #63 and #71, which are one
#   decision wearing three tickets -- is on Pip's outstanding rulings list. On
#   that date one of three things must happen, and drifting past is not one:
#     1. Forum revived  -> fix the three paths and unpark.
#     2. Forum retired  -> delete this and forum-theme.css, close #60/#63/#71.
#     3. Still undecided -> re-park with a NEW date and why the old one lapsed.
#
# DO NOT RUN IT before fixing the paths. The sshKey and server values are still
# CORRECT, so a path fix alone would point it at production NodeBB.
# ============================================================================

# Sync Forum Theme from Main Site CSS
# Run this script after updating main site colors

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "P(Doom)1 Forum Theme Sync" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

$mainCss = "C:\Users\gday\Documents\A Local Code\pdoom1-website\public\css\site.css"
$forumCss = "C:\Users\gday\Documents\A Local Code\pdoom1-website\forum-theme.css"
$sshKey = "C:\Users\gday\.ssh\pdoom-website-instance.pem"
$server = "ubuntu@208.113.200.215"

# Extract colors from main site CSS
Write-Host "[1/4] Reading main site colors..." -ForegroundColor Yellow
if (Test-Path $mainCss) {
    $content = Get-Content $mainCss -Raw
    if ($content -match '--accent-primary:\s*([^;]+)') {
        $primary = $matches[1].Trim()
        Write-Host "  Primary color: $primary" -ForegroundColor Green
    }
    Write-Host "  OK`n" -ForegroundColor Green
} else {
    Write-Host "  ERROR: Main CSS not found!`n" -ForegroundColor Red
    exit 1
}

# Upload theme to server
Write-Host "[2/4] Uploading theme to server..." -ForegroundColor Yellow
scp -i $sshKey -o StrictHostKeyChecking=no $forumCss ${server}:/tmp/forum-theme.css
if ($LASTEXITCODE -eq 0) {
    Write-Host "  OK`n" -ForegroundColor Green
} else {
    Write-Host "  ERROR: Upload failed!`n" -ForegroundColor Red
    exit 1
}

# Apply theme via NodeBB admin panel
Write-Host "[3/4] Installing theme..." -ForegroundColor Yellow
Write-Host "  Manual step required:" -ForegroundColor Yellow
Write-Host "  1. Go to http://208.113.200.215/admin/appearance/customise" -ForegroundColor White
Write-Host "  2. In 'Custom CSS' section, paste contents of forum-theme.css" -ForegroundColor White
Write-Host "  3. Click 'Save'`n" -ForegroundColor White

# Display next steps
Write-Host "[4/4] Next steps:" -ForegroundColor Yellow
Write-Host "  - Visit http://208.113.200.215 to see changes" -ForegroundColor White
Write-Host "  - Set up DNS for forum.pdoom1.com" -ForegroundColor White
Write-Host "  - Configure SSL with Let's Encrypt`n" -ForegroundColor White

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Theme sync complete!" -ForegroundColor Green
Write-Host "========================================`n" -ForegroundColor Cyan

# Open files for manual copying
Write-Host "Opening theme file for you to copy..." -ForegroundColor Yellow
Start-Process notepad $forumCss
Start-Process "http://208.113.200.215/admin/appearance/customise"
