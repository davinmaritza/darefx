# PowerShell script to create a clean Desktop Shortcut for DareFX GUI using pythonw.exe
$WshShell = New-Object -ComObject WScript.Shell
$DesktopPath = [System.Environment]::GetFolderPath([System.Environment+SpecialFolder]::Desktop)
$ShortcutPath = Join-Path $DesktopPath "DareFX Trading Terminal.lnk"

$ProjectRoot = "C:\DareFX"
$PythonW = Join-Path $ProjectRoot ".venv\Scripts\pythonw.exe"
$TargetScript = Join-Path $ProjectRoot "app.py"

$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $PythonW
$Shortcut.Arguments = "`"$TargetScript`""
$Shortcut.WorkingDirectory = $ProjectRoot
$Shortcut.Description = "DareFX Quantitative AI Trading Terminal"
$Shortcut.Save()

Write-Host "✅ Desktop shortcut created successfully at: $ShortcutPath"
