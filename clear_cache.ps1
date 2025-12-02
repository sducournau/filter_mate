# Clear FilterMate Plugin Cache for QGIS
# Run this script when you encounter ModuleNotFoundError

Write-Host "FilterMate Cache Cleaner" -ForegroundColor Green
Write-Host "========================" -ForegroundColor Green
Write-Host ""

# Plugin source directory
$sourceDir = $PSScriptRoot

# QGIS plugin installation directory
$qgisPluginDir = "$env:APPDATA\QGIS\QGIS3\profiles\imagodata\python\plugins\filter_mate"

Write-Host "1. Clearing __pycache__ from source directory..." -ForegroundColor Yellow
$cacheDirs = Get-ChildItem -Path $sourceDir -Directory -Recurse -Filter "__pycache__"
$count = 0
foreach ($dir in $cacheDirs) {
    Write-Host "   Removing: $($dir.FullName)"
    Remove-Item -Path $dir.FullName -Recurse -Force
    $count++
}
Write-Host "   Removed $count cache directories from source" -ForegroundColor Green
Write-Host ""

Write-Host "2. Clearing .pyc files from source directory..." -ForegroundColor Yellow
$pycFiles = Get-ChildItem -Path $sourceDir -File -Recurse -Filter "*.pyc"
$count = 0
foreach ($file in $pycFiles) {
    Write-Host "   Removing: $($file.FullName)"
    Remove-Item -Path $file.FullName -Force
    $count++
}
Write-Host "   Removed $count .pyc files from source" -ForegroundColor Green
Write-Host ""

if (Test-Path $qgisPluginDir) {
    Write-Host "3. Clearing __pycache__ from QGIS plugin directory..." -ForegroundColor Yellow
    $cacheDirs = Get-ChildItem -Path $qgisPluginDir -Directory -Recurse -Filter "__pycache__"
    $count = 0
    foreach ($dir in $cacheDirs) {
        Write-Host "   Removing: $($dir.FullName)"
        Remove-Item -Path $dir.FullName -Recurse -Force
        $count++
    }
    Write-Host "   Removed $count cache directories from QGIS" -ForegroundColor Green
    Write-Host ""
    
    Write-Host "4. Clearing .pyc files from QGIS plugin directory..." -ForegroundColor Yellow
    $pycFiles = Get-ChildItem -Path $qgisPluginDir -File -Recurse -Filter "*.pyc"
    $count = 0
    foreach ($file in $pycFiles) {
        Write-Host "   Removing: $($file.FullName)"
        Remove-Item -Path $file.FullName -Force
        $count++
    }
    Write-Host "   Removed $count .pyc files from QGIS" -ForegroundColor Green
    Write-Host ""
} else {
    Write-Host "3. QGIS plugin directory not found (plugin may not be installed)" -ForegroundColor Cyan
    Write-Host ""
}

Write-Host "Cache cleared successfully!" -ForegroundColor Green
Write-Host ""
Write-Host "NEXT STEPS:" -ForegroundColor Cyan
Write-Host "1. Close QGIS completely (if running)" -ForegroundColor White
Write-Host "2. Reopen QGIS" -ForegroundColor White
Write-Host "3. Go to Plugin Manager > Installed" -ForegroundColor White
Write-Host "4. Uncheck and re-check FilterMate" -ForegroundColor White
Write-Host ""
Write-Host "If the error persists, run this command in PowerShell:" -ForegroundColor Yellow
Write-Host "   Remove-Item -Path '$qgisPluginDir' -Recurse -Force" -ForegroundColor Yellow
Write-Host "Then reinstall the plugin from the source directory." -ForegroundColor Yellow
Write-Host ""
Write-Host "Press any key to exit..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
