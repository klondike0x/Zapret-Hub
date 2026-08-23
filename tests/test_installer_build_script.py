from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_prepare_release_arguments_are_separate_powershell_array_entries() -> None:
    script = (ROOT / "scripts" / "build_nuitka_installer.ps1").read_text(encoding="utf-8")

    assert '$Version,\n        "--skip-installer-payload-zips"' in script


def test_uninstaller_packages_only_its_required_icons() -> None:
    script = (ROOT / "scripts" / "build_nuitka_installer.ps1").read_text(encoding="utf-8")
    uninstaller_section = script.split("function Build-Uninstaller", 1)[1].split("$installerDataFiles", 1)[0]

    assert '"--include-data-dir=ui_assets=ui_assets"' not in uninstaller_section
    assert "installer_runtime_icon.png=ui_assets\\icons\\installer_runtime_icon.png" in uninstaller_section
    assert "app.png=ui_assets\\icons\\app.png" in uninstaller_section
    assert "app.ico=ui_assets\\icons\\app.ico" in uninstaller_section


def test_installer_build_uses_onefile_without_inno_wrapper() -> None:
    script = (ROOT / "scripts" / "build_nuitka_installer.ps1").read_text(encoding="utf-8")

    assert '"--onefile"' in script
    assert "--onefile-cache-mode=cached" in script
    assert "Find-ISCC" not in script
    assert "zapret_hub_installer.iss" not in script


def test_portable_flag_is_not_written_to_shared_dist() -> None:
    script = (ROOT / "scripts" / "build_nuitka.ps1").read_text(encoding="utf-8")

    # The shared *.dist feeds both the installer and portable packaging, so it
    # must never carry the portable marker: an installed app has to keep its
    # data in LocalAppData, not beside the executable.
    assert 'New-Item -ItemType File -Path (Join-Path $distDir.FullName "portable.flag")' not in script


def test_portable_packaging_writes_portable_flag() -> None:
    release_script = (ROOT / "scripts" / "prepare_nuitka_release.py").read_text(encoding="utf-8")
    build_script = (ROOT / "scripts" / "build_nuitka.ps1").read_text(encoding="utf-8")

    assert '(portable_dir / "portable.flag").write_text("", encoding="utf-8")' in release_script
    assert 'Remove-Item -LiteralPath (Join-Path $distDir.FullName "portable.flag")' in build_script


def test_component_updates_button_uses_theme_aware_text_color() -> None:
    modal = (ROOT / "web_ui" / "src" / "components" / "shell" / "ComponentUpdatesModal.tsx").read_text(encoding="utf-8")

    assert 'Обновить всё' in modal
    assert 'font-semibold text-fg' in modal
    assert 'font-medium text-white' not in modal
def test_installed_mods_actions_use_theme_aware_button_colors() -> None:
    page = (ROOT / "web_ui" / "src" / "pages" / "InstalledModsPage.tsx").read_text(encoding="utf-8")

    assert page.count("bg-accent") >= 2
    assert page.count("text-accent-foreground") >= 2
    assert "bg-[rgb(var(--page-accent-rgb))]" not in page
