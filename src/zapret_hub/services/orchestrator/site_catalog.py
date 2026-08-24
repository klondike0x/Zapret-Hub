"""User-editable sites that Auto mode should actively probe."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse


CATALOG_FILENAME = "auto_sites.json"
DEFAULT_SITES = (
    {
        "id": "rutracker",
        "name": "Rutracker",
        "domains": ["rutracker.org", "rutracker.net"],
    },
)


@dataclass(frozen=True, slots=True)
class AutoSite:
    id: str
    name: str
    domains: tuple[str, ...]


def _normalize_domain(value: object) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    if "://" in raw:
        raw = urlparse(raw).hostname or ""
    else:
        raw = raw.split("/", 1)[0].split(":", 1)[0]
    return raw.strip("[]").lower().rstrip(".")


def _parse(payload: object) -> list[AutoSite]:
    rows = payload.get("sites") if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        return []
    result: list[AutoSite] = []
    seen: set[str] = set()
    for item in rows:
        if not isinstance(item, dict):
            continue
        site_id = str(item.get("id") or item.get("name") or "").strip().lower()
        name = str(item.get("name") or site_id).strip() or site_id
        raw_domains = item.get("domains") or item.get("hosts") or []
        if isinstance(raw_domains, str):
            raw_domains = [raw_domains]
        normalized = [_normalize_domain(value) for value in raw_domains]
        domains = tuple(dict.fromkeys(value for value in normalized if value))
        if not site_id or not domains or site_id in seen:
            continue
        seen.add(site_id)
        result.append(AutoSite(site_id, name, domains))
    return result


class AutoSiteCatalog:
    @staticmethod
    def path(configs_dir: Path) -> Path:
        return Path(configs_dir) / CATALOG_FILENAME

    @classmethod
    def load(cls, configs_dir: Path, *, template_path: Path | None = None) -> list[AutoSite]:
        path = cls.path(configs_dir)
        if not path.exists() and template_path is not None and template_path.exists():
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(template_path, path)
            except OSError:
                pass
        try:
            if path.is_file():
                payload = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(payload, dict) and "sites" in payload:
                    return _parse(payload)
        except (OSError, ValueError, TypeError):
            pass
        defaults = {"version": 1, "sites": list(DEFAULT_SITES)}
        if not path.exists():
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(defaults, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            except OSError:
                pass
        return _parse(defaults)