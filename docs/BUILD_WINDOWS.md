# Windows build

## Prerequisites

- Python 3.11–3.13
- Rust stable MSVC
- Visual Studio 2022 Build Tools with Desktop C++
- WebView2 runtime
- Tauri CLI 2.x

## Development

```powershell
python -m pip install -e ".[dev]"
.\scripts\Start-Dev.ps1
```

## Windows ML

```powershell
.\scripts\Setup-WindowsML.ps1
.\scripts\Verify-WindowsML.py
```

## Release

```powershell
.\scripts\Build-Windows.ps1
```

The build script:

1. creates a build virtual environment under `%LOCALAPPDATA%\Metatron` by default (overrideable)
2. runs backend tests
3. builds the dependency-light backend sidecar with PyInstaller
4. stages it as a Tauri resource
5. builds Tauri bundles

Vendor ML runtimes and model weights are deliberately not embedded in the base installer.
