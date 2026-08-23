from __future__ import annotations

from pathlib import Path

import pytest

from installer import install_zaprethub as installer
from installer import common as installer_common
from installer.common import remove_app_data
from zapret_hub.services.orchestrator.site_catalog import AutoSiteCatalog
from zapret_hub.services.orchestrator.tuner import SmartTuner


def test_installer_normalizes_github_release_array() -> None:
    payload = [
        {
            "tag_name": "v3.0.2",
            "name": "Zapret Hub 3.0.2",
            "assets": [
                {
                    "name": "zapret_hub_3.0.2_portable_win_x64.zip",
                    "browser_download_url": "https://example.test/x64.zip",
                    "size": 123,
                }
            ],
        }
    ]
    release = installer._normalize_github_release(payload)
    assert release["version"] == "3.0.2"
    assert release["assets"]["x64"]["download_url"] == "https://example.test/x64.zip"


def test_installer_latest_page_fallback_builds_direct_assets(monkeypatch) -> None:
    monkeypatch.setattr(installer, "_ensure_host_resolvable", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        installer,
        "_run_with_deadline",
        lambda func, *, timeout, cancel_event=None: (
            200,
            b'<a href="/klondike0x/zapret-hub-continuation/releases/tag/v3.0.2">release</a>',
            "https://github.com/klondike0x/zapret-hub-continuation/releases/latest",
        ),
    )
    release = installer._fetch_latest_release_page()
    assert release["version"] == "3.0.2"
    assert set(release["assets"]) == {"x64"}
    assert release["assets"]["x64"]["download_url"].endswith(
        "/releases/download/v3.0.2/zapret_hub_3.0.2_portable_win_x64.zip"
    )


def test_installer_reports_unsupported_arm64_without_fallback_asset(monkeypatch) -> None:
    monkeypatch.setattr(installer, "_native_windows_machine", lambda: "arm64")
    monkeypatch.setattr(
        installer,
        "_fetch_mirror_release",
        lambda **kwargs: {
            "version": "3.0.3",
            "assets": {
                "x64": {"download_url": "https://example.test/x64.zip", "size": 0},
            },
        },
    )

    with pytest.raises(RuntimeError, match="ARM64"):
        installer._download_payload_from_mirror(progress_cb=lambda *args, **kwargs: None)


def test_installer_strips_portable_marker_from_extracted_payload(tmp_path: Path) -> None:
    """The installer downloads the portable ZIP; overlay must not leak the marker."""
    staging = tmp_path / "staging"
    source_root = staging / "zapret_hub"
    source_root.mkdir(parents=True)
    (source_root / "portable.flag").write_text("", encoding="utf-8")
    (source_root / "Zapret_Hub.exe").write_text("app", encoding="utf-8")

    installer._strip_portable_marker(source_root, staging)

    assert not (source_root / "portable.flag").exists()


def test_installer_strips_portable_marker_when_zip_has_no_root_folder(tmp_path: Path) -> None:
    """The portable ZIP may unpack directly into staging (no zapret_hub/ folder)."""
    staging = tmp_path / "staging"
    staging.mkdir()
    (staging / "portable.flag").write_text("", encoding="utf-8")
    (staging / "Zapret_Hub.exe").write_text("app", encoding="utf-8")

    installer._strip_portable_marker(staging, staging)

    assert not (staging / "portable.flag").exists()


def test_installer_strips_portable_marker_is_idempotent_without_marker(tmp_path: Path) -> None:
    staging = tmp_path / "staging"
    source_root = staging / "zapret_hub"
    source_root.mkdir(parents=True)
    (source_root / "Zapret_Hub.exe").write_text("app", encoding="utf-8")

    installer._strip_portable_marker(source_root, staging)  # must not raise


def test_portable_uninstaller_keeps_installed_user_data(tmp_path: Path, monkeypatch) -> None:
    install_dir = tmp_path / "Portable Zapret Hub"
    (install_dir / "user_data").mkdir(parents=True)
    (install_dir / "user_data" / "portable-settings.json").write_text("portable", encoding="utf-8")
    (install_dir / "portable.flag").write_text("", encoding="utf-8")

    local_app_data = tmp_path / "LocalAppData"
    installed_data = local_app_data / "Zapret_Hub"
    installed_data.mkdir(parents=True)
    (installed_data / "settings.json").write_text("installed", encoding="utf-8")
    roaming = tmp_path / "Roaming"
    roaming_data = roaming / "Zapret_Hub"
    roaming_data.mkdir(parents=True)
    (roaming_data / "settings.json").write_text("installed-roaming", encoding="utf-8")
    monkeypatch.setenv("LOCALAPPDATA", str(local_app_data))
    monkeypatch.setenv("APPDATA", str(roaming))
    monkeypatch.setenv("ZAPRET_HUB_WORK_ROOT", str(tmp_path / "external-work-root"))

    remove_app_data(install_dir)

    assert not (install_dir / "user_data").exists()
    assert (installed_data / "settings.json").read_text(encoding="utf-8") == "installed"
    assert (roaming_data / "settings.json").read_text(encoding="utf-8") == "installed-roaming"


def test_portable_uninstaller_preserves_installed_registration(tmp_path: Path, monkeypatch) -> None:
    install_dir = tmp_path / "Portable Zapret Hub"
    install_dir.mkdir(parents=True)
    (install_dir / "portable.flag").write_text("", encoding="utf-8")
    calls: list[object] = []
    monkeypatch.setattr(installer_common, "remove_shortcuts", lambda: calls.append("shortcuts"))
    monkeypatch.setattr(installer_common, "remove_uninstall_registry", lambda *args: calls.append(("registry", args)))

    installer_common.perform_uninstall(install_dir)

    assert calls == [("registry", (install_dir,))]


def test_registry_cleanup_requires_matching_install_location(tmp_path: Path) -> None:
    installed_root = tmp_path / "Installed Zapret Hub"
    portable_root = tmp_path / "Portable Zapret Hub"

    assert installer_common._registry_entry_belongs_to(portable_root, str(portable_root)) is True
    assert installer_common._registry_entry_belongs_to(portable_root, str(installed_root)) is False
    assert installer_common._registry_entry_belongs_to(portable_root, "") is False


def test_auto_site_catalog_loads_user_domains(tmp_path: Path) -> None:
    path = AutoSiteCatalog.path(tmp_path)
    path.write_text(
        '{"version": 1, "sites": [{"id": "rutorrent", "name": "RuTorrent", "domains": ["https://example.org/path"]}]}',
        encoding="utf-8",
    )
    sites = AutoSiteCatalog.load(tmp_path)
    assert [(site.id, site.domains) for site in sites] == [("rutorrent", ("example.org",))]


def test_tuner_allows_strategy_after_configured_site_list() -> None:
    steps = SmartTuner().plan(
        symptom="external_miss",
        domain="rutracker.org",
        domains=["rutracker.org"],
        domains_missing=["rutracker.org"],
        selected_services=set(),
        current={"general": "base|general.bat", "ipset": "loaded", "game_filter": "disabled"},
        ranked_generals=[("base|alternative.bat", 1.0)],
        trusted_general="base|trusted.bat",
        allow_strategy_after_list=True,
        max_steps=12,
    )
    assert any(step.kind == "add_domain" for step in steps)
    assert any(step.kind == "general" for step in steps)

def test_registry_discovery_ignores_portable_location(tmp_path: Path) -> None:
    normal = tmp_path / "normal"
    normal.mkdir()
    portable = tmp_path / "portable"
    portable.mkdir()
    (portable / "portable.flag").touch()

    assert installer_common._is_normal_install_location(normal)
    assert not installer_common._is_normal_install_location(portable)
