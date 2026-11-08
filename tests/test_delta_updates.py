"""Offline unit tests for secure, size-saving portable update packages."""
import json
import os
from pathlib import Path
from random import Random
from zipfile import ZipFile, ZIP_DEFLATED

import pytest

from astrochart.delta_updates import (
    create_delta, extract_delta, prepare_portable_update,
)
from astrochart.updater import (
    ASSET, SETUP_ASSET, Release, UpdateError, parse_release,
)
from astrochart.updater import DELTA_PREFIX


LARGE_UNCHANGED = Random(42).randbytes(120_000)


def files(version, exe=b"app", extra=True):
    result = {
        "AstroBirthChart/AstroBirthChart.exe": exe,
        "AstroBirthChart/AstroBirthChartUpdater.exe": b"worker",
        "AstroBirthChart/version.json": json.dumps({
            "version": version, "platform": "windows-x64"}).encode(),
        "AstroBirthChart/_internal/data/ephemeris/de440s.bsp": LARGE_UNCHANGED,
        "AstroBirthChart/_internal/keep.bin": b"unchanged",
    }
    if extra:
        result["AstroBirthChart/_internal/removed.dat"] = b"obsolete"
    else:
        result["AstroBirthChart/_internal/added.dat"] = b"new asset"
    return result


def zipped(path, contents):
    with ZipFile(path, "w", ZIP_DEFLATED) as output:
        for name, data in contents.items():
            output.writestr(name, data)
    return path


def packages(tmp_path):
    old = zipped(tmp_path / "old.zip", files("0.3.1", b"old"))
    new = zipped(tmp_path / "new.zip", files("0.3.2", b"new", False))
    return old, new


def installed(tmp_path, old):
    with ZipFile(old) as z:
        z.extractall(tmp_path / "installed")
    return tmp_path / "installed" / "AstroBirthChart"


def test_delta_roundtrip_reuses_large_file_deletes_old_and_adds_new(tmp_path):
    old, new = packages(tmp_path)
    location = installed(tmp_path, old)
    patch = create_delta(old, new, tmp_path / "delta.zip")
    assert patch is not None
    assert patch.stat().st_size < new.stat().st_size // 2
    with ZipFile(patch) as z:
        entries = set(z.namelist())
        manifest = json.loads(z.read("delta.json"))
        assert len(entries) == 1 + sum(
            item["source"] == "payload" for item in manifest["files"])
        assert "payload/_internal/data/ephemeris/de440s.bsp" not in entries
        assert "_internal/removed.dat" not in {
            item["path"] for item in manifest["files"]}
    stage = extract_delta(patch, location, "0.3.2", "0.3.1")
    assert stage.parent == location.parent
    assert (stage / "AstroBirthChart.exe").read_bytes() == b"new"
    assert (stage / "_internal/added.dat").read_bytes() == b"new asset"
    assert (stage / "_internal/data/ephemeris/de440s.bsp").read_bytes() == LARGE_UNCHANGED
    assert not (stage / "_internal/removed.dat").exists()


def test_modified_local_reused_file_blocks_partial_update(tmp_path):
    old, new = packages(tmp_path)
    location = installed(tmp_path, old)
    patch = create_delta(old, new, tmp_path / "delta.zip")
    (location / "_internal/data/ephemeris/de440s.bsp").write_bytes(
        LARGE_UNCHANGED[:-1] + b"!")
    with pytest.raises(UpdateError):
        extract_delta(patch, location, "0.3.2", "0.3.1")
    assert (location / "AstroBirthChart.exe").read_bytes() == b"old"
    assert not list(location.parent.glob(".astrochart-stage-*"))


def test_base_version_mismatch_rejected(tmp_path):
    old, new = packages(tmp_path)
    location = installed(tmp_path, old)
    patch = create_delta(old, new, tmp_path / "delta.zip")
    with pytest.raises(UpdateError):
        extract_delta(patch, location, "0.3.2", "0.3.0")


def test_installed_setup_marker_blocks_delta(tmp_path):
    old, new = packages(tmp_path)
    location = installed(tmp_path, old)
    (location / "installed-by-setup.marker").write_text("setup")
    patch = create_delta(old, new, tmp_path / "delta.zip")
    with pytest.raises(UpdateError):
        extract_delta(patch, location, "0.3.2", "0.3.1")


def test_unlisted_payload_and_manifest_traversal_rejected(tmp_path):
    old, new = packages(tmp_path)
    location = installed(tmp_path, old)
    patch = create_delta(old, new, tmp_path / "delta.zip")
    with ZipFile(patch) as z:
        current = {name: z.read(name) for name in z.namelist()}
    noisy = dict(current)
    noisy["payload/../../escape.txt"] = b"attack"
    zipped(tmp_path / "noisy.zip", noisy)
    with pytest.raises(UpdateError):
        extract_delta(tmp_path / "noisy.zip", location, "0.3.2", "0.3.1")
    changed = json.loads(current["delta.json"])
    changed["files"][0]["path"] = "../outside"
    noisy = dict(current)
    noisy["delta.json"] = json.dumps(changed).encode()
    zipped(tmp_path / "traversal.zip", noisy)
    with pytest.raises(UpdateError):
        extract_delta(tmp_path / "traversal.zip", location, "0.3.2", "0.3.1")
    assert not (tmp_path / "outside").exists()


def test_payload_tamper_rejected(tmp_path):
    old, new = packages(tmp_path)
    location = installed(tmp_path, old)
    patch = create_delta(old, new, tmp_path / "delta.zip")
    with ZipFile(patch) as z:
        current = {name: z.read(name) for name in z.namelist()}
    key = next(n for n in current if n.startswith("payload/"))
    current[key] = b"tampered"
    zipped(tmp_path / "tampered.zip", current)
    with pytest.raises(UpdateError):
        extract_delta(tmp_path / "tampered.zip", location, "0.3.2", "0.3.1")
    assert not list(location.parent.glob(".astrochart-stage-*"))


@pytest.mark.skipif(os.name == "nt", reason="Windows symlink creation may require privileges")
def test_untrusted_local_symlink_is_not_followed(tmp_path):
    old, new = packages(tmp_path)
    location = installed(tmp_path, old)
    patch = create_delta(old, new, tmp_path / "delta.zip")
    outside = tmp_path / "outside.bin"
    outside.write_bytes(LARGE_UNCHANGED)
    target = location / "_internal/data/ephemeris/de440s.bsp"
    target.unlink()
    target.symlink_to(outside)
    with pytest.raises(UpdateError):
        extract_delta(patch, location, "0.3.2", "0.3.1")
    assert outside.read_bytes() == LARGE_UNCHANGED


def test_no_delta_if_not_smaller(tmp_path):
    before = files("0.3.1", b"old")
    after = files("0.3.2", b"new")
    after["AstroBirthChart/_internal/data/ephemeris/de440s.bsp"] = Random(9).randbytes(120_000)
    old = zipped(tmp_path / "before.zip", before)
    new = zipped(tmp_path / "after.zip", after)
    assert create_delta(old, new, tmp_path / "delta.zip") is None
    assert not (tmp_path / "delta.zip").exists()


def test_reject_downgrade_and_reserved_paths_in_builder(tmp_path):
    old, new = packages(tmp_path)
    with pytest.raises(UpdateError):
        create_delta(new, old, tmp_path / "delta.zip")
    malicious = files("0.3.2")
    malicious["AstroBirthChart/CON.txt"] = b"bad"
    zipped(tmp_path / "malicious.zip", malicious)
    with pytest.raises(UpdateError):
        create_delta(old, tmp_path / "malicious.zip", tmp_path / "delta.zip")


def release_payload():
    version = "0.3.2"
    full_url = f"https://github.com/toyro396133/astro-birth-chart-windows/releases/download/v{version}/"
    delta_name = f"{DELTA_PREFIX}0.3.1-to-v{version}.zip"
    return {
        "tag_name": "v" + version, "draft": False, "prerelease": False,
        "assets": [
            {"name": ASSET, "state": "uploaded", "size": 120_000,
             "digest": "sha256:" + "a" * 64,
             "browser_download_url": full_url + ASSET},
            {"name": delta_name, "state": "uploaded", "size": 800,
             "digest": "sha256:" + "b" * 64,
             "browser_download_url": full_url + delta_name},
        ],
    }


def test_select_only_matching_base_delta_and_keep_full_fallback():
    payload = release_payload()
    current = parse_release(payload, base_version="0.3.1")
    assert current.delta and current.delta.size == 800
    assert current.size == 120_000
    assert parse_release(payload, base_version="0.3.0").delta is None
    payload["assets"][1]["digest"] = None
    assert parse_release(payload, base_version="0.3.1").delta is None


def test_fallback_uses_full_verification_path(monkeypatch, tmp_path):
    from astrochart import delta_updates
    release = parse_release(release_payload(), base_version="0.3.1")
    called = []
    def fake_download(asset, target):
        called.append(asset.url)
        if asset == release.delta:
            raise UpdateError("unavailable delta")
        Path(target).write_bytes(b"full asset")
    monkeypatch.setattr(delta_updates, "download_release", fake_download)
    expected = tmp_path / "stage"
    monkeypatch.setattr(delta_updates, "extract_release",
                        lambda path, folder, version: expected)
    stage, method = prepare_portable_update(release, tmp_path, "0.3.1")
    assert (stage, method) == (expected, "full")
    assert len(called) == 2


def test_setup_path_cannot_choose_portable_delta():
    payload = release_payload()
    version = "0.3.2"
    url = f"https://github.com/toyro396133/astro-birth-chart-windows/releases/download/v{version}/"
    payload["assets"].append({
        "name": SETUP_ASSET, "state": "uploaded", "size": 125_000,
        "digest": "sha256:" + "c" * 64,
        "browser_download_url": url + SETUP_ASSET,
    })
    assert parse_release(payload, asset_name=SETUP_ASSET,
                         base_version="0.3.1").delta is None
