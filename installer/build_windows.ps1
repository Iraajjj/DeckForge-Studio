# Run on Windows 10/11 with Python 3.12 and Inno Setup 6/7 installed.
$ErrorActionPreference = 'Stop'
Set-Location (Resolve-Path (Join-Path $PSScriptRoot '..'))
python -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw 'pip bootstrap failed' }
python -m pip install -e '.[dev]' 'pyinstaller>=6,<7'
if ($LASTEXITCODE -ne 0) { throw 'dependency installation failed' }
python -m pytest -q
if ($LASTEXITCODE -ne 0) { throw 'pytest failed' }
python -m PyInstaller --noconfirm --clean --onedir --windowed --name DeckForgeStudio --collect-submodules PIL --collect-submodules reportlab installer\entrypoint_windows.py
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller failed' }
& '.\dist\DeckForgeStudio\DeckForgeStudio.exe' --self-test
if ($LASTEXITCODE -ne 0) { throw 'Frozen app smoke test failed' }
$iss = 'installer\DeckForgeStudio.iss'
$iscc = (Get-Command ISCC.exe -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty Source)
if (-not $iscc) {
  $candidates = @('C:\Program Files\Inno Setup 7\ISCC.exe', 'C:\Program Files (x86)\Inno Setup 6\ISCC.exe', 'C:\Program Files\Inno Setup 6\ISCC.exe')
  $iscc = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
}
if (-not $iscc) { throw 'Install Inno Setup 6/7 first; Windows binaries are in dist\DeckForgeStudio.' }
& $iscc $iss
if ($LASTEXITCODE -ne 0) { throw 'Inno Setup compile failed' }
Get-Item release\DeckForgeStudio-V4-Windows-Setup.exe
