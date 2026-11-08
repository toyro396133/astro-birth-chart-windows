"""Safe Setup delta generation and installation-button behavior (offline)."""
from hashlib import sha256
import json
from pathlib import Path
from zipfile import ZipFile

import pytest

from astrochart.updater import (
    Release, SETUP_ASSET, setup_delta_asset, selected_setup_download,
    is_setup_delta_name,
)
import astrochart.ui as ui

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from create_setup_delta import generate_patch, safe_path
import update_worker


def _make_tree(root, version, same=b"identical", changed=b"new", removed=False):
    (root / "_internal" / "data" / "ephemeris").mkdir(parents=True)
    files = {
        "AstroBirthChart.exe": changed,
        "AstroBirthChartUpdater.exe": b"helper",
        "version.json": json.dumps(
            {"version": version, "platform": "windows-x64"}).encode(),
        "_internal/data/ephemeris/de440s.bsp": same,
        "stable.txt": b"unchanged",
    }
    if removed:
        files["removed.txt"] = b"old"
    for name, data in files.items():
        p = root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
    return files


def _zip(tree, path):
    with ZipFile(path, "w") as z:
        for file in tree.rglob("*"):
            if file.is_file():
                z.write(file, "AstroBirthChart/" + file.relative_to(tree).as_posix())


def test_generator_writes_only_changed_files_with_reuse_checks(tmp_path):
    old, new = tmp_path / "old", tmp_path / "new"
    _make_tree(old, "0.6.0", changed=b"old", removed=True)
    _make_tree(new, "0.6.1", changed=b"new")
    archive = tmp_path / "previous.zip"
    _zip(old, archive)
    template = tmp_path / "base.iss"
    template.write_text(
        "[Setup]\nAppId=AstroBirthChart.Windows\n"
        "OutputBaseFilename=AstroBirthChart-Setup\n"
        "[Files]\nSource: \"dist\\AstroBirthChart\\*\"; DestDir: \"{app}\"\n"
        "[Icons]\nName: \"test\"; Filename: \"{app}\\AstroBirthChart.exe\"\n",
        encoding="utf-8")
    dest = tmp_path / "delta.iss"
    plan = generate_patch(archive, new, template, dest)
    source = dest.read_text("utf-8")
    assert plan["from"] == "0.6.0" and plan["to"] == "0.6.1"
    assert plan["changed"] == ["AstroBirthChart.exe", "version.json"]
    assert plan["removed"] == ["removed.txt"]
    assert "_internal/data/ephemeris/de440s.bsp" in plan["reused"]
    assert "Source: \"dist\\AstroBirthChart\\stable.txt\"" not in source
    assert "GetSHA256OfFile" in source
    assert sha256(b"unchanged").hexdigest() in source
    assert "InstallDelete" in source and "removed.txt" in source
    assert "AppId=AstroBirthChart.Windows" in source
    assert "AstroBirthChart-Setup-Delta-from-v0.6.0-to-v0.6.1" in source
    assert "registered AstroBirthChart" in source


@pytest.mark.parametrize("name", [
    "../outside", "foo\\bar", "C:/drive", "CON", "a/../b",
    "a.", "name;", "a/'quote", "duplicate//segment", "a/{app}/b",
])
def test_rejects_dangerous_paths(name):
    with pytest.raises(ValueError):
        safe_path(name)


def _release_payload():
    name = "AstroBirthChart-Setup-Delta-from-v0.6.0-to-v0.6.1.exe"
    return {
        "assets": [{
            "name": name, "state": "uploaded", "size": 1_000_000,
            "digest": "sha256:" + ("b" * 64),
            "browser_download_url": (
                "https://github.com/toyro396133/astro-birth-chart-windows/"
                "releases/download/v0.6.1/" + name),
        }]
    }


def test_chooses_only_exact_smaller_signed_delta():
    full = Release("0.6.1", "https://example.invalid/full", "a" * 64, 75_000_000)
    candidate = setup_delta_asset(_release_payload(), full, "0.6.0")
    chosen, name, mode = selected_setup_download(candidate)
    assert mode == "setup-delta" and chosen.size == 1_000_000
    assert name.endswith("to-v0.6.1.exe")
    assert selected_setup_download(full)[2] == "setup"
    assert setup_delta_asset(_release_payload(), full, "0.5.1").delta_size == 0

    payload = _release_payload()
    payload["assets"][0]["digest"] = "sha256:invalid"
    assert setup_delta_asset(payload, full, "0.6.0").delta_size == 0
    payload = _release_payload()
    payload["assets"][0]["size"] = full.size
    assert setup_delta_asset(payload, full, "0.6.0").delta_size == 0


def test_worker_rejects_wrong_base_and_wrong_target(tmp_path):
    installed = tmp_path / "AstroBirthChart"
    installed.mkdir()
    (installed / "installed-by-setup.marker").write_text("setup")
    (installed / "version.json").write_text(
        json.dumps({"version": "0.5.1", "platform": "windows-x64"}))
    patch = tmp_path / "AstroBirthChart-Setup-Delta-from-v0.6.0-to-v0.6.1.exe"
    patch.write_bytes(b"placeholder")
    with pytest.raises(update_worker.InstallationError):
        update_worker.install_setup(installed, patch, "0.6.1", "0" * 64,
                                    invoke=lambda args: None)
    assert not is_setup_delta_name(patch.name, "0.6.2", "0.6.0")


def test_button_prefers_delta_then_falls_back_to_full_on_download_error(tmp_path, monkeypatch):
    full = Release("0.6.1", "https://example.invalid/full", "a" * 64, 80_000_000)
    delta = setup_delta_asset(_release_payload(), full, "0.6.0")
    attempts = []

    def fake_download(asset, target):
        attempts.append(asset.url)
        if asset.url != full.url:
            raise ui.UpdateError("bad delta digest")
        target.write_bytes(b"verified installer")
        return target

    monkeypatch.setattr(ui, "download_release", fake_download)
    thread = ui.UpdateDownloadThread(delta, "setup")
    received, errors = [], []
    thread.result.connect(received.append)
    thread.error.connect(errors.append)
    thread.run()
    assert not errors
    assert len(attempts) == 2
    assert received[0][2] == "setup"
    assert received[0][1].name == SETUP_ASSET
    received[0][1].unlink()
    received[0][1].parent.rmdir()


def test_worker_retry_uses_full_verified_fallback(monkeypatch, tmp_path):
    setup = tmp_path / "AstroBirthChart-Setup-Delta-from-v0.6.0-to-v0.6.1.exe"
    setup.write_bytes(b"not used")
    full = tmp_path / SETUP_ASSET
    full.write_bytes(b"verified")
    installed = tmp_path / "AstroBirthChart"
    installed.mkdir()
    (installed / "AstroBirthChart.exe").write_bytes(b"exe")
    seen = []

    def install(inst, path, version, digest):
        seen.append(Path(path).name)
        if "Delta" in Path(path).name:
            raise update_worker.InstallationError("base changed")
        return installed

    monkeypatch.setattr(update_worker, "wait_for_process", lambda pid: None)
    monkeypatch.setattr(update_worker, "install_setup", install)
    monkeypatch.setattr(update_worker, "download_full_fallback",
                        lambda *args: full)
    monkeypatch.setattr(update_worker.subprocess, "Popen", lambda *a, **k: None)
    # The worker owns a fresh temporary fallback directory; avoid deleting
    # the fixture directory by providing a dedicated holder.
    fallback_dir = tmp_path / "fallback"
    fallback_dir.mkdir()
    replacement = fallback_dir / SETUP_ASSET
    replacement.write_bytes(b"verified")
    monkeypatch.setattr(update_worker, "download_full_fallback",
                        lambda *args: replacement)
    result = update_worker.main([
        "--apply-setup", str(installed), str(setup), "101", "0.6.1", "a" * 64,
        "https://github.com/toyro396133/astro-birth-chart-windows/releases/download/v0.6.1/AstroBirthChart-Setup.exe",
        "b" * 64, "8"])
    assert result == 0
    assert seen == [setup.name, SETUP_ASSET]
    assert not replacement.exists()
