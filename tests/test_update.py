import sys
from pathlib import Path

from okapi import update


def test_is_newer():
    assert update.is_newer("0.5.0", "0.4.1")
    assert update.is_newer("1.0.0", "0.9.9")
    assert not update.is_newer("0.4.1", "0.4.1")
    assert not update.is_newer("0.4.0", "0.4.1")
    # tags with a leading v parse the same
    assert update.is_newer("v0.5.0", "v0.4.1")


def test_binary_asset_name_per_platform(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    assert update.binary_asset_name() == "okapi-windows-x64.exe"
    monkeypatch.setattr(sys, "platform", "linux")
    assert update.binary_asset_name() == "okapi-linux-x64"
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(update.platform, "machine", lambda: "arm64")
    assert update.binary_asset_name() == "okapi-macos-arm64"
    monkeypatch.setattr(update.platform, "machine", lambda: "x86_64")
    assert update.binary_asset_name() == "okapi-macos-x64"


def test_install_kind_frozen(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert update.install_kind() == "binary"


def test_install_kind_pipx(monkeypatch):
    monkeypatch.setattr(sys, "prefix", "/Users/x/.local/pipx/venvs/okapi")
    assert update.install_kind() == "pipx"


def test_install_kind_dev():
    # the test suite runs from an editable install inside the git checkout
    assert update.install_kind() == "dev"


def test_run_update_up_to_date(monkeypatch, capsys):
    monkeypatch.setattr(
        update, "fetch_latest",
        lambda: update.ReleaseInfo(tag="v0.0.1", version="0.0.1", assets={}),
    )
    assert update.run_update() == 0


def test_run_update_check_reports_available(monkeypatch):
    monkeypatch.setattr(
        update, "fetch_latest",
        lambda: update.ReleaseInfo(tag="v99.0.0", version="99.0.0", assets={}),
    )
    assert update.run_update(check_only=True) == 3


def test_run_update_refuses_dev_checkout(monkeypatch):
    monkeypatch.setattr(
        update, "fetch_latest",
        lambda: update.ReleaseInfo(tag="v99.0.0", version="99.0.0", assets={}),
    )
    assert update.run_update() == 1  # dev checkout → git pull, no overwrite
