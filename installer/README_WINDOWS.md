# DeckForge V4 — standalone Windows installer build

The `installer/` directory supplies a **real build pipeline** for a Windows desktop executable that does not require Python on the buyer's machine. It is not a prebuilt `.exe`.

## How to obtain it

1. Publish the source repository to GitHub (private is fine).
2. In **Actions** select **DeckForge V4 Windows installer** and **Run workflow**.
3. After the successful Windows runner job, open its **Artifacts** and download `DeckForgeStudio-V4-Windows-Installer-UNSIGNED`.
4. Verify `SHA256SUMS.txt`, and test on a clean Windows 10/11 PC before redistributing.

Alternatively run `powershell -ExecutionPolicy Bypass -File installer/build_windows.ps1` on Windows with Python 3.12 and Inno Setup 6/7 installed. This creates `release/DeckForgeStudio-V4-Windows-Setup.exe`.

## What is and isn't verified

- The workflow runs all Python tests and a frozen-executable `--self-test`, then builds a single installer.
- The installer is **unsigned**: Windows may display SmartScreen warnings. Commercial distribution needs signing, malware scanning and a separate clean-machine installation test.
- Windows testing cannot be performed on this Linux-based artifact builder. A successful workflow run is required before describing the Windows `.exe` as built and tested.
- User artwork and API keys are never bundled. Optional vision usage requires a separately configured API key and explicit consent.
