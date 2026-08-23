from __future__ import annotations

from pathlib import Path


def test_portable_mode_migrates_localappdata_state(tmp_path: Path, monkeypatch) -> None:
    from zapret_hub import bootstrap

    install_root = tmp_path / "Zapret Hub"
    install_root.mkdir()
    (install_root / "portable.flag").touch()
    (install_root / "portable_legacy.flag").touch()
    local_app_data = tmp_path / "LocalAppData"
    legacy = local_app_data / "Zapret_Hub"
    (legacy / "configs").mkdir(parents=True)
    (legacy / "configs" / "settings.json").write_text('{"selected_runtime_mode":"zapret2"}', encoding="utf-8")
    monkeypatch.setenv("LOCALAPPDATA", str(local_app_data))
    monkeypatch.delenv("ZAPRET_HUB_WORK_ROOT", raising=False)

    monkeypatch.setattr(bootstrap, "is_packaged_runtime", lambda: True)
    work_root = bootstrap._resolve_work_root(install_root)

    assert work_root == install_root / "user_data"
    assert (work_root / "configs" / "settings.json").read_text(encoding="utf-8") == '{"selected_runtime_mode":"zapret2"}'
    assert (legacy / "configs" / "settings.json").exists()


def test_fresh_portable_mode_does_not_import_installed_state(tmp_path: Path, monkeypatch) -> None:
    from zapret_hub import bootstrap

    install_root = tmp_path / "Zapret Hub"
    install_root.mkdir()
    (install_root / "portable.flag").touch()
    local_app_data = tmp_path / "LocalAppData"
    legacy = local_app_data / "Zapret_Hub"
    (legacy / "configs").mkdir(parents=True)
    (legacy / "configs" / "settings.json").write_text("installed", encoding="utf-8")
    monkeypatch.setenv("LOCALAPPDATA", str(local_app_data))
    monkeypatch.delenv("ZAPRET_HUB_WORK_ROOT", raising=False)
    monkeypatch.delenv("ZAPRET_HUB_MIGRATE_LEGACY_DATA", raising=False)

    monkeypatch.setattr(bootstrap, "is_packaged_runtime", lambda: True)
    work_root = bootstrap._resolve_work_root(install_root)

    assert work_root == install_root / "user_data"
    assert not (work_root / "configs" / "settings.json").exists()
    assert (legacy / "configs" / "settings.json").read_text(encoding="utf-8") == "installed"


def test_portable_mode_migration_can_be_enabled_by_environment(tmp_path: Path, monkeypatch) -> None:
    from zapret_hub import bootstrap

    install_root = tmp_path / "Zapret Hub"
    install_root.mkdir()
    (install_root / "portable.flag").touch()
    local_app_data = tmp_path / "LocalAppData"
    legacy = local_app_data / "Zapret_Hub"
    (legacy / "configs").mkdir(parents=True)
    (legacy / "configs" / "settings.json").write_text("opt-in", encoding="utf-8")
    monkeypatch.setenv("LOCALAPPDATA", str(local_app_data))
    monkeypatch.setenv("ZAPRET_HUB_MIGRATE_LEGACY_DATA", "1")
    monkeypatch.delenv("ZAPRET_HUB_WORK_ROOT", raising=False)

    monkeypatch.setattr(bootstrap, "is_packaged_runtime", lambda: True)
    work_root = bootstrap._resolve_work_root(install_root)

    assert (work_root / "configs" / "settings.json").read_text(encoding="utf-8") == "opt-in"


def test_portable_mode_does_not_recopy_existing_user_data(tmp_path: Path, monkeypatch) -> None:
    from zapret_hub import bootstrap

    install_root = tmp_path / "Zapret Hub"
    user_data = install_root / "user_data"
    user_data.mkdir(parents=True)
    (user_data / "marker.txt").write_text("portable", encoding="utf-8")
    (install_root / "portable.flag").touch()
    local_app_data = tmp_path / "LocalAppData"
    legacy = local_app_data / "Zapret_Hub"
    legacy.mkdir(parents=True)
    (legacy / "marker.txt").write_text("legacy", encoding="utf-8")
    monkeypatch.setenv("LOCALAPPDATA", str(local_app_data))
    monkeypatch.delenv("ZAPRET_HUB_WORK_ROOT", raising=False)
    monkeypatch.setattr(bootstrap, "is_packaged_runtime", lambda: True)

    assert bootstrap._resolve_work_root(install_root) == user_data
    assert (user_data / "marker.txt").read_text(encoding="utf-8") == "portable"


def test_portable_registration_does_not_replace_existing_install(tmp_path: Path) -> None:
    from zapret_hub import bootstrap

    installed_root = tmp_path / "Installed Zapret Hub"
    installed_root.mkdir()
    portable_root = tmp_path / "Portable Zapret Hub"
    portable_root.mkdir()
    (portable_root / "portable.flag").touch()

    assert bootstrap._portable_registration_can_replace(portable_root, str(installed_root)) is False
    assert bootstrap._portable_registration_can_replace(portable_root, str(portable_root)) is True
    assert bootstrap._portable_registration_can_replace(portable_root, str(tmp_path / "removed")) is True
