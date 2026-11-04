# Full-system validation

Portable tests cannot certify WebView2, Windows Job Objects, DPAPI, microphone/hotkey behavior, or NPU/GPU execution. Use a Windows 11 machine for release qualification.

## 1. Preflight

```powershell
.\scripts\Test-WindowsPrerequisites.ps1 -RequireDevTools -OutputJson build\preflight.json
```

## 2. Optional runtime setup

```powershell
.\scripts\Bootstrap-Windows.ps1 -AllRuntimes
```

The default runtime root is `%LOCALAPPDATA%\Metatron`. Inspect each optional model/runtime license before redistribution.

## 3. Build and validate

```powershell
.\scripts\Bootstrap-Windows.ps1 -AllRuntimes -Build -Validate
```

Or run validation independently:

```powershell
.\scripts\Invoke-MetatronFullValidation.ps1 -All -ModelPath C:\path\to\probe.onnx
```

## 4. Accelerator proof

Inventory is not proof. For an NPU/GPU claim, require a real model session/warm-up, CPU fallback disabled when the execution provider supports it, runtime execution-device evidence, and Windows utilization cross-check. A Device Manager NPU without a routable provider must be reported as detected only.

## 5. Speech qualification

Set `METATRON_SPEECH_CMD` to the validated JSONL speech sidecar and run:

```powershell
python .\scripts\Verify-SpeechRuntime.py --json-out build\speech.json
```

The setup helper installs the pinned EZSTT environment but does not invent an unverified entrypoint. The sidecar must report actual placement before Metatron treats it as proven.

## 6. Desktop metrics

```powershell
.\scripts\Measure-MetatronDesktop.ps1 -Scenario idle_shell
```

Metrics distinguish private working set, private bytes, whole-system commit and GPU shared memory. Gates are defined in `qualification_thresholds.json`.

## 7. Support bundle

```powershell
.\scripts\Collect-SupportBundle.ps1
```

The bundle intentionally excludes secrets, the SQLite database, transcript history and audio.
