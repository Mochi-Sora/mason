from pathlib import Path


def test_windows_native_install_path_docs_match_installer() -> None:
    doc = Path("website/docs/user-guide/windows-native.md").read_text()
    install = Path("scripts/install.ps1").read_text()

    # The launchers live in the managed binary dir OUTSIDE the git checkout
    # (MASON_HOME\bin, next to the managed uv) — NOT the whole venv\Scripts
    # (which would shadow the user's python, #83797) and NOT a dir inside
    # the checkout (which `mason update`'s autostash swept off disk).
    assert "%LOCALAPPDATA%\\mason\\bin" in doc
    assert (
        "Get-Command mason        # should print "
        "C:\\Users\\<you>\\AppData\\Local\\mason\\bin\\mason.exe"
    ) in doc
    # Installer exposes $MasonHome\bin, and must copy the launchers into it.
    assert '$masonBin = "$MasonHome\\bin"' in install
    assert "mason.exe" in install and "mason-acp.exe" in install
    # Guard against regressions to either legacy layout.
    assert '$masonBin = "$InstallDir\\venv\\Scripts"' not in install
    assert '$masonBin = "$InstallDir\\bin"' not in install
