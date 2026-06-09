$ErrorActionPreference = "Stop"

$desktopPath = [System.IO.Path]::Combine($env:USERPROFILE, "Desktop")
$shortcutName = "Disk Companion.lnk"
$shortcutPath = [System.IO.Path]::Combine($desktopPath, $shortcutName)

$projectDir = "C:\Users\Diomedes Fernandez\.gemini\antigravity\scratch\disk-companion"
$entryPoint = Join-Path $projectDir "main.py"

# Find proper Python executable (pythonw for no console, python as fallback)
$pythonExe = (Get-Command "pythonw.exe" -ErrorAction SilentlyContinue).Source
if (-not $pythonExe) {
    $pythonExe = (Get-Command "python.exe" -ErrorAction SilentlyContinue).Source
}

if (-not $pythonExe) {
    Write-Error "Python not found in PATH."
    exit 1
}

Write-Host "Creating shortcut for Disk Companion..."
Write-Host "Desktop Path: $desktopPath"
Write-Host "Target Path: $pythonExe"
Write-Host "Entry Point: $entryPoint"

try {
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = $pythonExe
    $shortcut.Arguments = "`"$entryPoint`""
    $shortcut.WorkingDirectory = $projectDir
    $shortcut.WindowStyle = 1
    $shortcut.Description = "Disk Companion File Explorer"
    $shortcut.Save()
    Write-Host "Successfully created shortcut $shortcutPath"
} catch {
    Write-Error "Failed to create shortcut: $_"
    exit 1
}
