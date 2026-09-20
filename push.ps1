# ============================================================
# push.ps1
# ------------------------------------------------------------
# One-command Git push for the property-platform repo.
#
# Usage (from anywhere):
#   Right-click this file -> Run with PowerShell
#     OR
#   From a PowerShell terminal:
#     & C:\Projects\property-platform\push.ps1 "your commit message"
#
# If no message is given, uses a timestamped default.
# ============================================================

param(
    [string]$Message = ""
)

$ErrorActionPreference = "Stop"

# --- Move to the repo root ---
$repoRoot = "C:\Projects\property-platform"
Set-Location $repoRoot

# --- Build default message if none supplied ---
if ([string]::IsNullOrWhiteSpace($Message)) {
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm"
    $Message = "auto-push $timestamp"
}

Write-Host ""
Write-Host "==> Repo:    $repoRoot" -ForegroundColor Cyan
Write-Host "==> Message: $Message" -ForegroundColor Cyan
Write-Host ""

# --- Check if there is anything to commit ---
$status = git status --porcelain
if ([string]::IsNullOrWhiteSpace($status)) {
    Write-Host "Nothing to commit. Working tree is clean." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Still pushing in case remote is behind..." -ForegroundColor Yellow
    git push
    Write-Host ""
    Write-Host "Done." -ForegroundColor Green
    exit 0
}

# --- Stage everything ---
Write-Host "==> git add ." -ForegroundColor Cyan
git add .

# --- Commit ---
Write-Host "==> git commit" -ForegroundColor Cyan
git commit -m "$Message"

# --- Push ---
Write-Host "==> git push" -ForegroundColor Cyan
git push

Write-Host ""
Write-Host "Done. Everything is on GitHub." -ForegroundColor Green
Write-Host ""