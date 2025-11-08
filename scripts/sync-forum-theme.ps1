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
