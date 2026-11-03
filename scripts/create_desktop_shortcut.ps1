# PowerShell script to create a clean Desktop Shortcut for DareFX GUI using pythonw.exe
$WshShell = New-Object -ComObject WScript.Shell
$DesktopCandidates = @()
$SpecialDesktop = [System.Environment]::GetFolderPath([System.Environment+SpecialFolder]::Desktop)
if (![string]::IsNullOrWhiteSpace($SpecialDesktop) -and (Test-Path $SpecialDesktop)) {
    $DesktopCandidates += $SpecialDesktop
}
if (Test-Path "C:\Users\davin\Desktop") {
    $DesktopCandidates += "C:\Users\davin\Desktop"
}
if (Test-Path "C:\Users\Public\Desktop") {
    $DesktopCandidates += "C:\Users\Public\Desktop"
}
$DesktopCandidates = $DesktopCandidates | Select-Object -Unique

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
foreach ($DesktopPath in $DesktopCandidates) {
    $ShortcutPath = Join-Path $DesktopPath "DareFX Trading Terminal.lnk"
    $Shortcut = $WshShell.CreateShortcut($ShortcutPath)
    $Shortcut.TargetPath = $PythonW
    $Shortcut.Arguments = "`"$TargetScript`""
    $Shortcut.WorkingDirectory = $ProjectRoot
    $Shortcut.Description = "DareFX Quantitative AI Trading Terminal"
    $IconPath = Join-Path $ProjectRoot "assets\logo\darefx-app.ico"
    if (Test-Path $IconPath) {
        $Shortcut.IconLocation = "$IconPath,0"
    }
    $Shortcut.Save()
    Write-Host "✅ Desktop shortcut created successfully at: $ShortcutPath"
}
