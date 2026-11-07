from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def text(name: str) -> str:
    return (SCRIPTS / name).read_text(encoding="utf-8")


def test_nonexpert_entrypoints_are_present():
    assert (ROOT / "TEST-METATRON.cmd").is_file()
    assert (ROOT / "TEST-METATRON-QUICK.cmd").is_file()
    for name in (
        "Run-MetatronTests.ps1",
        "Prepare-WindowsTestMachine.ps1",
        "Test-MetatronPortable.ps1",
        "Test-MetatronHardware.ps1",
        "Test-MetatronSpeech.ps1",
        "Test-MetatronTTS.ps1",
        "Test-MetatronPresence.ps1",
        "Test-MetatronAutomation.ps1",
        "Test-MetatronMemory.ps1",
        "Test-MetatronPackaging.ps1",
    ):
        assert (SCRIPTS / name).is_file(), name


def test_full_runner_is_one_click_and_collects_evidence_on_failure():
    cmd = (ROOT / "TEST-METATRON.cmd").read_text(encoding="utf-8")
    runner = text("Run-MetatronTests.ps1")
    assert "Run-MetatronTests.ps1\" -Mode Full -SoakMinutes 60" in cmd
    assert "Prepare-WindowsTestMachine.ps1" in runner
    assert "SELF-TEST-SUMMARY.json" in runner
    assert "Compress-Archive" in runner
    assert "Invoke-MetatronReleaseClosure.ps1" in runner


def test_machine_preparation_can_install_every_build_tool_the_full_gate_needs():
    prep = text("Prepare-WindowsTestMachine.ps1")
    for package in (
        "Python.Python.3.12",
        "Git.Git",
        "OpenJS.NodeJS.LTS",
        "Rustlang.Rustup",
        "Microsoft.VisualStudio.2022.BuildTools",
        "Microsoft.EdgeWebView2Runtime",
    ):
        assert package in prep
    assert "Microsoft.VisualStudio.Workload.VCTools" in prep
    assert "setup.exe" in prep and "'modify','--installPath'" in prep
    assert "stable-x86_64-pc-windows-msvc" in prep
    assert "pip','install','-e','.[dev]','onnx'" in prep


def test_release_closure_no_longer_requires_human_model_or_winml_setup():
    closure = text("Invoke-MetatronReleaseClosure.ps1")
    assert "Prepare-WindowsTestMachine.ps1" in closure
    assert "Setup-WindowsML.ps1" in closure
    assert "Generate-TestOnnxModel.py" in closure
    assert "Setup-SpeechRuntime.ps1" in closure
    assert "Setup-Kokoro-TTS.ps1" in closure
    assert "RunEZSTTUpstream=$true" in closure
    assert "soak_minutes=$SoakMinutes" in closure


def test_build_uses_the_build_venv_for_tests_not_an_unprepared_global_python():
    build = text("Build-Windows.ps1")
    assert "& $Py" not in build or "Invoke-NativeChecked -FilePath $Py" in build
    assert "-e','.[dev]'" in build
    assert "-m','pytest'" in build
    assert "product_audit.py" in build


def test_support_bundle_accepts_the_qualified_python():
    support = text("Collect-SupportBundle.ps1")
    full = text("Invoke-MetatronFullValidation.ps1")
    assert '[string]$Python="python"' in support
    assert "-Python $Python" in full


def test_hardware_wrapper_generates_and_uses_a_local_probe_model():
    hw = text("Test-MetatronHardware.ps1")
    assert "Setup-WindowsML.ps1" in hw
    assert "Generate-TestOnnxModel.py" in hw
    assert "Verify-Accelerators.py" in hw
    assert "'--model',$probeModel" in hw
    assert "'NPU,GPU,CPU'" in hw


def test_presence_wrapper_captures_all_product_modes_without_touching_user_data():
    src = text("Test-MetatronPresence.ps1")
    helper = text("Configure-TestPresenceProfile.py")
    closure = text("Invoke-MetatronReleaseClosure.ps1")
    for profile in ("solar", "lattice", "reactor", "pets", "both"):
        assert profile in src
    assert "METATRON_DATA_DIR" in src and "profile-data-" in src
    assert "METATRON_DATA_DIR" in helper
    assert '"mode": mode' in helper
    assert "Test-MetatronPresence.ps1" in closure
