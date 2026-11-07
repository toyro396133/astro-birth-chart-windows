"""Update security, extraction, version and rollback tests. No network."""
import json
from pathlib import Path
import sys
from zipfile import ZipFile

import pytest

from astrochart.updater import (
    ASSET, MAX_ZIP, UpdateError, extract_release, parse_release,
    is_newer, auto_updates_enabled, save_auto_updates,
)
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from update_worker import install


def release_payload(ver="0.2.0"):
    return {
        "tag_name": "v" + ver, "draft": False, "prerelease": False,
        "assets": [{
            "name": ASSET, "state": "uploaded", "size": 150000,
            "digest": "sha256:" + ("a" * 64),
            "browser_download_url": (
                "https://github.com/toyro396133/astro-birth-chart-windows/"
                "releases/download/v" + ver + "/" + ASSET),
        }]
    }


def test_versions():
    assert is_newer("0.2.0", "0.1.9")
    assert not is_newer("0.2.0", "0.2.0")
    assert not is_newer("1.0.0", "1.0.1")
    with pytest.raises(UpdateError):
        is_newer("0.2.0-alpha", "0.1.0")


def test_strict_release_asset():
    good = parse_release(release_payload())
    assert good.version == "0.2.0"
    for key, bad in [("digest", None), ("digest", "sha256:ab"),
                     ("size", MAX_ZIP + 1), ("size", "ten"),
                     ("browser_download_url", "http://evil.invalid/file")]:
        doc = release_payload()
        doc["assets"][0][key] = bad
        with pytest.raises(UpdateError):
            parse_release(doc)


def test_prerelease_rejected():
    doc = release_payload()
    doc["prerelease"] = True
    with pytest.raises(UpdateError):
        parse_release(doc)


def test_optin_default_disabled(tmp_path):
    cfg = tmp_path / "prefs.json"
    assert not auto_updates_enabled(cfg)
    save_auto_updates(True, cfg)
    assert auto_updates_enabled(cfg)
    save_auto_updates(False, cfg)
    assert not auto_updates_enabled(cfg)


def archive_items(version="0.2.0"):
    return {
        "AstroBirthChart/AstroBirthChart.exe": b"new-app",
        "AstroBirthChart/AstroBirthChartUpdater.exe": b"worker",
        "AstroBirthChart/version.json": json.dumps(
            {"version": version, "platform": "windows-x64"}).encode(),
        "AstroBirthChart/_internal/data/ephemeris/de440s.bsp": b"jpl"
    }


def create_zip(tmp_path, items):
    archive = tmp_path / "release.zip"
    with ZipFile(archive, "w") as z:
        for name, content in items.items():
            z.writestr(name, content)
    return archive


def installation(tmp_path):
    folder = tmp_path / "AstroBirthChart"
    folder.mkdir()
    (folder / "AstroBirthChart.exe").write_bytes(b"old-app")
    return folder


def test_valid_extract_and_atomic_swap(tmp_path):
    installed = installation(tmp_path)
    archive = create_zip(tmp_path, archive_items())
    staged = extract_release(archive, installed, "0.2.0")
    assert staged.parent == installed.parent
    launched = []
    backup = install(installed, staged, "0.2.0", launch=launched.append)
    assert launched == [installed / "AstroBirthChart.exe"]
    assert (installed / "AstroBirthChart.exe").read_bytes() == b"new-app"
    assert (backup / "AstroBirthChart.exe").read_bytes() == b"old-app"


def test_rolls_back_if_restart_fails(tmp_path):
    installed = installation(tmp_path)
    staged = extract_release(create_zip(tmp_path, archive_items()), installed, "0.2.0")
    def error(exe):
        raise OSError("could not launch")
    with pytest.raises(OSError):
        install(installed, staged, "0.2.0", launch=error)
    assert (installed / "AstroBirthChart.exe").read_bytes() == b"old-app"


@pytest.mark.parametrize("attack", [
    "AstroBirthChart/../evil.txt",
    "AstroBirthChart\\evil.txt",
    "../AstroBirthChart/evil.txt",
    "AstroBirthChart/C:/evil.txt",
])
def test_zip_traversal_rejected(tmp_path, attack):
    installed = installation(tmp_path)
    entries = archive_items()
    entries[attack] = b"attack"
    with pytest.raises(UpdateError):
        extract_release(create_zip(tmp_path, entries), installed, "0.2.0")
    assert not (tmp_path / "evil.txt").exists()


def test_wrong_package_version_rejected(tmp_path):
    installed = installation(tmp_path)
    archive = create_zip(tmp_path, archive_items("0.1.0"))
    with pytest.raises(UpdateError):
        extract_release(archive, installed, "0.2.0")
