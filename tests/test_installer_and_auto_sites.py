from __future__ import annotations

from pathlib import Path

from installer import install_zaprethub as installer
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
    assert release["assets"]["x64"]["download_url"].endswith(
        "/releases/download/v3.0.2/zapret_hub_3.0.2_portable_win_x64.zip"
    )


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