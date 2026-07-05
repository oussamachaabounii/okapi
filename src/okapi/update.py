"""Self-update: check GitHub Releases and update this install in place.

Handles the three ways okapi gets installed:
- standalone PyInstaller binary  → download the matching release asset and
  swap the executable in place
- pipx                           → reinstall pinned to the latest release tag
- plain pip                      → pip install --upgrade in this interpreter
A development checkout (editable install inside a git repo) is left alone.
"""

from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console

from . import __version__

REPO = "oussamachaabounii/okapi"
API_LATEST = f"https://api.github.com/repos/{REPO}/releases/latest"


@dataclass
class ReleaseInfo:
    tag: str                  # e.g. "v0.4.1"
    version: str              # e.g. "0.4.1"
    assets: dict[str, str]    # asset name -> download URL


def fetch_latest() -> ReleaseInfo:
    req = urllib.request.Request(
        API_LATEST,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "okapi-updater"},
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.load(resp)
    tag = data["tag_name"]
    return ReleaseInfo(
        tag=tag,
        version=tag.lstrip("v"),
        assets={a["name"]: a["browser_download_url"] for a in data.get("assets", [])},
    )


def _version_tuple(v: str) -> tuple[int, ...]:
    return tuple(int(p) for p in re.findall(r"\d+", v)[:3]) or (0,)


def is_newer(latest: str, current: str) -> bool:
    return _version_tuple(latest) > _version_tuple(current)


def binary_asset_name() -> str:
    if sys.platform == "win32":
        return "okapi-windows-x64.exe"
    if sys.platform == "darwin":
        return "okapi-macos-arm64" if platform.machine() == "arm64" else "okapi-macos-x64"
    return "okapi-linux-x64"


def install_kind() -> str:
    """How is this okapi installed? -> binary | pipx | dev | pip"""
    if getattr(sys, "frozen", False):
        return "binary"
    if "pipx" in Path(sys.prefix).as_posix().lower():
        return "pipx"
    repo_root = Path(__file__).resolve().parents[2]
    if (repo_root / ".git").exists() and (repo_root / "pyproject.toml").exists():
        return "dev"
    return "pip"


def _update_binary(rel: ReleaseInfo, console: Console) -> None:
    asset = binary_asset_name()
    url = rel.assets.get(asset)
    if not url:
        raise RuntimeError(f"release {rel.tag} has no asset '{asset}'")
    target = Path(sys.executable).resolve()

    console.print(f"downloading {asset} {rel.tag} …")
    # Download into the target's directory so the final move is same-filesystem.
    fd, tmp_name = tempfile.mkstemp(prefix=".okapi-update-", dir=target.parent)
    tmp = Path(tmp_name)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "okapi-updater"})
        with urllib.request.urlopen(req, timeout=120) as resp, os.fdopen(fd, "wb") as out:
            shutil.copyfileobj(resp, out)
        if tmp.stat().st_size < 1_000_000:
            raise RuntimeError("downloaded file is suspiciously small; aborting")
        tmp.chmod(0o755)
        if os.name == "nt":
            # Windows can't overwrite a running exe, but it can be renamed.
            stale = target.with_name(target.name + ".old")
            stale.unlink(missing_ok=True)
            target.rename(stale)
            shutil.move(str(tmp), str(target))
            console.print(f"[dim]previous version kept as {stale.name}; safe to delete[/]")
        else:
            os.replace(tmp, target)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    console.print(f"[green]updated:[/] {target} → {rel.tag}")


def _update_pipx(rel: ReleaseInfo, console: Console) -> None:
    pipx = shutil.which("pipx")
    if not pipx:
        raise RuntimeError("this okapi was installed with pipx, but pipx is not on PATH")
    spec = f"git+https://github.com/{REPO}@{rel.tag}"
    console.print(f"running pipx install --force {spec} …")
    subprocess.run([pipx, "install", "--force", spec], check=True)
    console.print(f"[green]updated to {rel.tag}[/]")


def _update_pip(rel: ReleaseInfo, console: Console) -> None:
    spec = f"git+https://github.com/{REPO}@{rel.tag}"
    console.print(f"running pip install --upgrade {spec} …")
    subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", spec], check=True)
    console.print(f"[green]updated to {rel.tag}[/]")


def run_update(*, check_only: bool = False, console: Console | None = None) -> int:
    """Returns an exit code: 0 up-to-date/updated, 1 failure, 3 update available
    (only in --check mode, so scripts can branch on it)."""
    console = console or Console()
    try:
        rel = fetch_latest()
    except Exception as exc:
        console.print(f"[red]error:[/] could not reach GitHub releases: {exc}")
        return 1

    console.print(f"current: v{__version__}   latest: {rel.tag}")
    if not is_newer(rel.version, __version__):
        console.print("[green]already up to date[/]")
        return 0
    if check_only:
        console.print(f"update available: {rel.tag} (run [bold]okapi update[/] to install)")
        return 3

    kind = install_kind()
    try:
        if kind == "binary":
            _update_binary(rel, console)
        elif kind == "pipx":
            _update_pipx(rel, console)
        elif kind == "dev":
            console.print(
                "this is a development checkout — update it with [bold]git pull[/] "
                "(refusing to overwrite a working tree)"
            )
            return 1
        else:
            _update_pip(rel, console)
    except Exception as exc:
        console.print(f"[red]update failed:[/] {exc}")
        return 1
    return 0
