"""Actualizador no bloqueante basado en GitHub Releases.

Solo descarga artefactos publicados; nunca reemplaza una aplicación en ejecución.
El repositorio se configura con ``APP_UPDATE_REPOSITORY=owner/repo``.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import threading
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Callable

import requests


log = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[1]
VERSION_FILE = ROOT / "src" / "version.json"
DEFAULT_DOWNLOAD_DIR = ROOT / "downloads" / "updates"


def _version_tuple(value: str) -> tuple[int, ...]:
    numbers = re.findall(r"\d+", str(value).lstrip("vV"))
    return tuple(int(part) for part in numbers[:4]) or (0,)


def _configured_repository() -> str:
    repository = os.getenv("APP_UPDATE_REPOSITORY", "").strip()
    if repository:
        return repository.removeprefix("https://github.com/").strip("/")
    try:
        configured = json.loads(VERSION_FILE.read_text(encoding="utf-8"))
        return str(configured.get("github_repository") or "").strip()
    except (OSError, ValueError, TypeError):
        return ""


def current_version() -> str:
    try:
        return str(json.loads(VERSION_FILE.read_text(encoding="utf-8"))["app_version"])
    except (OSError, KeyError, ValueError, TypeError):
        return "0.0.0"


@dataclass(frozen=True)
class UpdateResult:
    status: str
    current_version: str
    latest_version: str | None = None
    repository: str | None = None
    download_path: str | None = None
    release_url: str | None = None
    message: str = ""


class GitHubReleaseUpdater:
    def __init__(self, repository: str | None = None, download_dir: Path | None = None,
                 request_get: Callable[..., Any] = requests.get):
        self.repository = (repository or _configured_repository()).strip().strip("/")
        self.download_dir = Path(download_dir or DEFAULT_DOWNLOAD_DIR)
        self.request_get = request_get

    def _save_status(self, result: UpdateResult) -> None:
        self.download_dir.mkdir(parents=True, exist_ok=True)
        status_file = self.download_dir / "update-status.json"
        status_file.write_text(json.dumps(asdict(result), ensure_ascii=False, indent=2), encoding="utf-8")

    def check_and_download(self) -> UpdateResult:
        installed = current_version()
        if not self.repository or "/" not in self.repository:
            result = UpdateResult(
                "not_configured", installed, repository=self.repository or None,
                message="Configura APP_UPDATE_REPOSITORY=propietario/repositorio para activar actualizaciones.",
            )
            self._save_status(result)
            return result

        api_url = f"https://api.github.com/repos/{self.repository}/releases/latest"
        try:
            response = self.request_get(
                api_url,
                headers={"Accept": "application/vnd.github+json", "User-Agent": "Inversiones-IA-Updater"},
                timeout=12,
            )
            response.raise_for_status()
            release = response.json()
            latest = str(release.get("tag_name") or "").lstrip("vV")
            if not latest:
                raise ValueError("La publicación no contiene tag_name")
            if _version_tuple(latest) <= _version_tuple(installed):
                result = UpdateResult("up_to_date", installed, latest, self.repository,
                                      release_url=release.get("html_url"), message="La aplicación está actualizada.")
                self._save_status(result)
                return result

            assets = release.get("assets") or []
            candidates = [asset for asset in assets if str(asset.get("name", "")).lower().endswith((".zip", ".exe"))]
            if not candidates:
                result = UpdateResult("available_no_asset", installed, latest, self.repository,
                                      release_url=release.get("html_url"),
                                      message="Hay una versión nueva, pero no incluye ZIP o EXE descargable.")
                self._save_status(result)
                return result

            asset = candidates[0]
            safe_name = Path(str(asset["name"])).name
            self.download_dir.mkdir(parents=True, exist_ok=True)
            destination = self.download_dir / safe_name
            temporary = destination.with_suffix(destination.suffix + ".part")
            binary = self.request_get(asset["browser_download_url"], stream=True, timeout=60)
            binary.raise_for_status()
            digest = hashlib.sha256()
            with temporary.open("wb") as output:
                for chunk in binary.iter_content(chunk_size=1024 * 256):
                    if chunk:
                        output.write(chunk)
                        digest.update(chunk)
            expected_size = int(asset.get("size") or 0)
            if expected_size and temporary.stat().st_size != expected_size:
                temporary.unlink(missing_ok=True)
                raise ValueError("El tamaño descargado no coincide con GitHub")
            temporary.replace(destination)
            (destination.with_suffix(destination.suffix + ".sha256")).write_text(
                f"{digest.hexdigest()}  {safe_name}\n", encoding="ascii"
            )
            result = UpdateResult("downloaded", installed, latest, self.repository, str(destination),
                                  release.get("html_url"),
                                  "Actualización descargada; se aplicará manualmente con la aplicación cerrada.")
            self._save_status(result)
            return result
        except Exception as exc:
            result = UpdateResult("check_failed", installed, repository=self.repository,
                                  message=f"No se pudo comprobar GitHub: {exc}")
            self._save_status(result)
            return result


def start_background_update_check() -> threading.Thread | None:
    """Descarga una publicación nueva al arrancar sin bloquear la interfaz."""
    if os.getenv("APP_UPDATE_ENABLED", "1").strip().lower() in {"0", "false", "no"}:
        return None

    def worker() -> None:
        result = GitHubReleaseUpdater().check_and_download()
        getattr(log, "info" if result.status in {"up_to_date", "downloaded"} else "warning")(
            "Actualizador GitHub: %s — %s", result.status, result.message
        )

    thread = threading.Thread(target=worker, daemon=True, name="GitHubStartupUpdater")
    thread.start()
    return thread
