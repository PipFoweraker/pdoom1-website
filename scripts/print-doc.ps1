<#
.SYNOPSIS
  Print an HTML file silently, double-sided. No browser window, no PDF viewer window.

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

.WHY DUPLEX IS THE DEFAULT
  Pip's convention, 2026-08-02: duplex for reading documents, simplex only for clipboard
  checklists. He is tracking which sheets come out single-sided, so a SILENT downgrade to
  one side is the exact failure he is trying to detect -- worse than not printing at all,
  because the stack looks fine and the convention looks followed. Hence the capability
  check below, and hence the mode is stated on the last line of every run.

.EXAMPLE
  .\scripts\print-doc.ps1 runsheet-tonight              # duplex, long edge (default)
  .\scripts\print-doc.ps1 ceremony-checklist -Simplex   # clipboard checklist, one side
  .\scripts\print-doc.ps1 -List
  .\scripts\print-doc.ps1 walk-read -PdfOnly            # build the PDF, do not print
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
    [string]$Paper = 'A4',
    # Opt OUT of double-sided. For clipboard checklists, where the back of a sheet you
    # are writing on is unreachable. Everything else is a reading document and duplexes.
    [switch]$Simplex,
    # Long edge is right for portrait reading documents: the sheet flips like a book.
    # -ShortEdge flips like a notepad; only wanted for landscape.
    [switch]$ShortEdge
)

$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$reviewDir = Join-Path $repo 'public\_review'

if ($List -or -not $Name) {
    Write-Host "Printable documents in public\_review\ :" -ForegroundColor Cyan
    Get-ChildItem $reviewDir -Filter *.html | ForEach-Object {
        "  {0,-24} {1,6:N0} KB   {2}" -f $_.BaseName, ($_.Length / 1KB), $_.LastWriteTime.ToString('HH:mm')
    }
    Write-Host "`nUsage:  .\scripts\print-doc.ps1 <name>          (duplex, long edge)" -ForegroundColor Cyan
    Write-Host "        .\scripts\print-doc.ps1 <name> -Simplex  (single-sided)" -ForegroundColor Cyan
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

# --- decide the duplex mode BEFORE rendering ------------------------------------
# Fail fast: a printer that cannot duplex should stop the run in a tenth of a second,
# not after five seconds of Edge.
#
# TRAP: Win32_Printer.Capabilities is a uint16[] of enum values, NOT descriptions.
#   3 = Duplex. (Cross-checked on this box: Brother HL-L2460DW reports 4,3,5 whose
#   CapabilityDescriptions are Copies,Duplex,Collate; "Microsoft Print to PDF" reports
#   4,2 = Copies,Color and no 3.) Match on the NUMBER, not on the description string --
#   CapabilityDescriptions is driver-supplied and localised, so a non-English driver
#   would silently stop matching and hand Pip single-sided sheets.
# TRAP: do NOT look the printer up with -Filter "Name='$target'". Printer names contain
#   spaces and network queues contain backslashes, which WQL treats as escapes. Where-Object
#   compares the string as a string.
$target = $null
$duplexSupport = 'unknown'   # supported | unsupported | unknown
$duplexWhy = ''

if ($Printer) { $target = $Printer }
else {
    $def = Get-CimInstance Win32_Printer -Filter 'Default=True' -ErrorAction SilentlyContinue
    if ($def) { $target = $def.Name }
}

if (-not $target) {
    $duplexWhy = 'no default printer found'
} else {
    $q = Get-CimInstance Win32_Printer -ErrorAction SilentlyContinue |
         Where-Object { $_.Name -eq $target } | Select-Object -First 1
    if (-not $q) {
        $duplexWhy = "printer '$target' is not enumerated by WMI"
    } elseif ($null -eq $q.Capabilities) {
        $duplexWhy = "driver for '$target' reports no Capabilities list"
    } elseif ($q.Capabilities -contains 3) {
        $duplexSupport = 'supported'
    } else {
        $duplexSupport = 'unsupported'
        $duplexWhy = "driver reports capabilities [$($q.CapabilityDescriptions -join ', ')] -- no Duplex"
    }
}

if ($Simplex) {
    $duplexToken = 'simplex'
    $modeLabel = 'SIMPLEX (single-sided, requested)'
} elseif ($ShortEdge) {
    $duplexToken = 'duplexshort'
    $modeLabel = 'duplex, SHORT edge (requested)'
} else {
    $duplexToken = 'duplexlong'
    $modeLabel = 'duplex, long edge'
}

# The refusal. Only bites when we are actually going to print, and only when the queue
# has POSITIVELY said it cannot duplex. Printing anyway would produce a single-sided
# stack indistinguishable from a duplexed one that the printer happened to mis-handle,
# which is precisely the signal Pip is trying to keep.
if (-not $PdfOnly -and -not $Simplex -and $duplexSupport -eq 'unsupported') {
    Write-Error @"
REFUSING TO PRINT: '$target' cannot duplex, so this would come out single-sided.
  $duplexWhy
You are tracking which sheets are single-sided, so this script will not hand you one
without you asking. Either:
  * print it deliberately single-sided:  .\scripts\print-doc.ps1 $Name -Simplex
  * or pick a queue that duplexes:       .\scripts\print-doc.ps1 $Name -Printer "<name>"
"@
}

# --- hop 1: HTML -> PDF, headless ----------------------------------------------
# -LeafBase is PowerShell 6+; this box runs Windows PowerShell 5.1, where it throws
# "A parameter cannot be found that matches parameter name 'LeafBase'".
$pdf = Join-Path $env:TEMP ([IO.Path]::GetFileNameWithoutExtension($src) + '.pdf')
if (Test-Path $pdf) { Remove-Item $pdf -Force }

$uri = 'file:///' + ($src -replace '\\', '/')
# --no-pdf-header-footer drops the URL/date furniture Edge adds by default; the pages
# carry their own dateline and their own page number (see scripts/review-print.css,
# which puts "N / M" in the @page @bottom-center margin box) and Edge's built-in footer
# is a fixed ~7.5pt with no way to restyle it.
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
    Write-Host ("would have printed: {0}  |  paper {1}  |  {2}" -f $modeLabel, $Paper,
        $(if ($target) { "queue '$target' duplex=$duplexSupport" } else { 'no printer resolved' })
    ) -ForegroundColor Yellow
    return
}

# --- hop 2: PDF -> printer, silent ----------------------------------------------
if (-not $target) { Write-Error "No printer to print to. Pass -Printer '<name>' or set a Windows default." }

$modeActual = $modeLabel

if (-not $sumatra) {
    # Fallback still avoids a *browser* window, but the PDF handler may flash briefly --
    # and, more importantly, the shell Print verb carries NO print settings, so neither
    # the paper size nor the duplex request survives. Say so; do not let it pass as done.
    Write-Warning "SumatraPDF not found -- falling back to the shell Print verb, which may flash a window."
    Write-Warning "The shell Print verb carries no print settings: paper=$Paper and $duplexToken are NOT applied. Whatever the queue defaults to is what you get."
    $modeActual = "UNKNOWN -- printed via shell PrintTo, which cannot request duplex"
    Start-Process -FilePath $pdf -Verb PrintTo -ArgumentList "`"$target`"" -WindowStyle Hidden
} else {
    # -print-settings applies to THIS job only; it does not touch the queue default.
    # Tokens verified present in the installed SumatraPDF 3.6.1 binary: duplex,
    # duplexlong, duplexshort, simplex.
    $settings = "paper=$Paper,$duplexToken"
    if ($Printer) { & $sumatra -print-to "$Printer" -print-settings $settings -silent -exit-when-done "$pdf" }
    else          { & $sumatra -print-to-default    -print-settings $settings -silent -exit-when-done "$pdf" }

    if (-not $Simplex -and $duplexSupport -ne 'supported') {
        # Not a refusal -- we could not establish the queue's capability either way, and
        # refusing on "unknown" would block a printer WMI simply does not describe. But an
        # unverified duplex request is exactly the sheet Pip needs to eyeball.
        Write-Warning "Duplex was REQUESTED but NOT VERIFIED: $duplexWhy. Check whether this sheet came out double-sided."
        $modeActual = "$modeLabel (REQUESTED, capability unverified)"
    }
}

Start-Sleep -Seconds 2
$queued = (Get-PrintJob -PrinterName $target -ErrorAction SilentlyContinue | Measure-Object).Count
Write-Host ("sent to {0}  |  paper {1}  |  {2}  |  {3}" -f $target, $Paper, $modeActual,
    $(if ($queued -eq 0) { 'queue empty (spooled through)' } else { "$queued job(s) still queued" })
) -ForegroundColor Green
