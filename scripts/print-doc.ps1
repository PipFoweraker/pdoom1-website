<#
.SYNOPSIS
  Print an HTML file silently. No browser window, no PDF viewer window.

.WHY
  Pip works from paper during critical hours and does not want an Edge window opening
  every time. Windows has no direct HTML-to-printer path, so this does it in two silent
  hops:

      Edge --headless=new  ->  a PDF in %TEMP%     (renders the @media print CSS)
      SumatraPDF -silent   ->  the default printer (no viewer, exits when done)

  Both are already installed on this machine. SumatraPDF is the piece that makes it
  genuinely silent -- `Start-Process -Verb Print` flashes the associated app, which is
  what we are avoiding.

  Every page under public/_review/ is written print-first: black on white, 12.5pt serif
  minimum (Pip has an unfilled glasses prescription and an earlier print came back too
  small), and 6mm tick boxes that a pen can actually land in.

.EXAMPLE
  .\scripts\print-doc.ps1 runsheet-tonight
  .\scripts\print-doc.ps1 ceremony-checklist
  .\scripts\print-doc.ps1 -List
  .\scripts\print-doc.ps1 walk-read -PdfOnly     # build the PDF, do not print
#>
[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [string]$Name,
    [switch]$List,
    [switch]$PdfOnly,
    [string]$Printer,
    # The system queue on this box is set to Letter, which is wrong for an AU user --
    # coordination/PRINT_AND_PROCESS_REFERENCE says force the size per job rather than
    # change Pip's queue default. Letter is 6mm narrower and 18mm shorter than A4, so a
    # sheet laid out to @page{size:A4} gets scaled down -- which silently defeats the
    # 12.5pt minimum the glasses prescription requires.
    [string]$Paper = 'A4'
)

$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$reviewDir = Join-Path $repo 'public\_review'

if ($List -or -not $Name) {
    Write-Host "Printable documents in public\_review\ :" -ForegroundColor Cyan
    Get-ChildItem $reviewDir -Filter *.html | ForEach-Object {
        "  {0,-24} {1,6:N0} KB   {2}" -f $_.BaseName, ($_.Length / 1KB), $_.LastWriteTime.ToString('HH:mm')
    }
    Write-Host "`nUsage:  .\scripts\print-doc.ps1 <name>" -ForegroundColor Cyan
    return
}

# Accept a bare name, a filename, or a full path.
$src = if (Test-Path $Name) { (Resolve-Path $Name).Path }
       elseif (Test-Path (Join-Path $reviewDir $Name)) { Join-Path $reviewDir $Name }
       # The concatenation MUST be parenthesised before Join-Path sees it, or PowerShell
       # reads `+ '.html'` as a second positional argument and fails with
       # "A positional parameter cannot be found that accepts argument '+'".
       else { Join-Path $reviewDir (($Name -replace '\.html$', '') + '.html') }

if (-not (Test-Path $src)) {
    Write-Error "Not found: $src`nRun with -List to see what is available."
}

# --- locate the two tools -------------------------------------------------------
$edge = @(
    "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe",
    "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe",
    "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
    "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1

$sumatra = @(
    "$env:LOCALAPPDATA\SumatraPDF\SumatraPDF.exe",
    "$env:ProgramFiles\SumatraPDF\SumatraPDF.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $edge) { Write-Error "No Edge or Chrome found -- needed to render HTML to PDF." }

# --- hop 1: HTML -> PDF, headless ----------------------------------------------
# -LeafBase is PowerShell 6+; this box runs Windows PowerShell 5.1, where it throws
# "A parameter cannot be found that matches parameter name 'LeafBase'".
$pdf = Join-Path $env:TEMP ([IO.Path]::GetFileNameWithoutExtension($src) + '.pdf')
if (Test-Path $pdf) { Remove-Item $pdf -Force }

$uri = 'file:///' + ($src -replace '\\', '/')
# --no-pdf-header-footer drops the URL/date furniture Edge adds by default; the pages
# carry their own dateline and it is not worth a line of the margin.
# Start-Process, NOT the call operator. Edge writes harmless chatter to stderr, and in
# Windows PowerShell 5.1 a native command's stderr becomes ErrorRecords -- which under
# $ErrorActionPreference='Stop' aborts the script even though Edge exited 0 and wrote a
# perfectly good PDF. Start-Process keeps stderr out of the error stream entirely.
$args = @('--headless=new', '--disable-gpu', '--no-pdf-header-footer',
          "--print-to-pdf=$pdf", $uri)
Start-Process -FilePath $edge -ArgumentList $args -NoNewWindow -Wait -ErrorAction SilentlyContinue

$deadline = (Get-Date).AddSeconds(25)
while (-not (Test-Path $pdf) -and (Get-Date) -lt $deadline) { Start-Sleep -Milliseconds 400 }
if (-not (Test-Path $pdf)) { Write-Error "Edge did not produce a PDF for $src" }

"{0} -> PDF ({1:N0} KB)" -f (Split-Path $src -Leaf), ((Get-Item $pdf).Length / 1KB) | Write-Host

if ($PdfOnly) {
    Write-Host "PDF only, not printed: $pdf" -ForegroundColor Yellow
    return
}

# --- hop 2: PDF -> printer, silent ----------------------------------------------
$target = if ($Printer) { $Printer }
          else { (Get-CimInstance Win32_Printer -Filter 'Default=True').Name }

if (-not $sumatra) {
    # Fallback still avoids a *browser* window, but the PDF handler may flash briefly.
    Write-Warning "SumatraPDF not found -- falling back to the shell Print verb, which may flash a window."
    Start-Process -FilePath $pdf -Verb PrintTo -ArgumentList "`"$target`"" -WindowStyle Hidden
} else {
    # -print-settings applies to THIS job only; it does not touch the queue default.
    $settings = "paper=$Paper"
    if ($Printer) { & $sumatra -print-to "$Printer" -print-settings $settings -silent -exit-when-done "$pdf" }
    else          { & $sumatra -print-to-default    -print-settings $settings -silent -exit-when-done "$pdf" }
}

Start-Sleep -Seconds 2
$queued = (Get-PrintJob -PrinterName $target -ErrorAction SilentlyContinue | Measure-Object).Count
Write-Host ("sent to {0}  |  {1}" -f $target,
    $(if ($queued -eq 0) { 'queue empty (spooled through)' } else { "$queued job(s) still queued" })
) -ForegroundColor Green
