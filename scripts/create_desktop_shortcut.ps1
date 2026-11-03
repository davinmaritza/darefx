# PowerShell script to create a clean Desktop Shortcut for DareFX GUI using pythonw.exe
$WshShell = New-Object -ComObject WScript.Shell
$DesktopPath = [System.Environment]::GetFolderPath([System.Environment+SpecialFolder]::Desktop)
$ShortcutPath = Join-Path $DesktopPath "DareFX Trading Terminal.lnk"

$ProjectRoot = "C:\DareFX"
$TargetScript = Join-Path $ProjectRoot "app.py"

$VenvPythonW = Join-Path $ProjectRoot ".venv\Scripts\pythonw.exe"
if (Test-Path $VenvPythonW) {
    $PythonW = $VenvPythonW
} else {
    $CmdPythonW = (Get-Command pythonw.exe -ErrorAction SilentlyContinue)
    if ($CmdPythonW) {
        $PythonW = $CmdPythonW.Source
    } elseif (Test-Path "C:\Program Files\Python312\pythonw.exe") {
        $PythonW = "C:\Program Files\Python312\pythonw.exe"
    } else {
        $PythonW = "pythonw.exe"
    }
}

$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $PythonW
$Shortcut.Arguments = "`"$TargetScript`""
$Shortcut.WorkingDirectory = $ProjectRoot
$Shortcut.Description = "DareFX Quantitative AI Trading Terminal"
$Shortcut.Save()

Write-Host "✅ Desktop shortcut created successfully at: $ShortcutPath"
