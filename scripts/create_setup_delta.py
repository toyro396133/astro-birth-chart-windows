"""Build a real Inno Setup *patch installer* for an existing registered install.

The patch uses exactly the same AppId as the full installer, so Inno appends
its changes to the existing Windows uninstall log. It contains only changed
files. Unchanged installed files are SHA-256 verified *before* any writes.
"""
from hashlib import sha256
import argparse
import json
from pathlib import Path
import re
from zipfile import ZipFile

ROOT = "AstroBirthChart/"
VERSION = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
DISALLOWED = re.compile(r'[<>:"|?*\x00-\x1f]')
RESERVED = re.compile(r"^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)", re.I)
MAX_FILES = 3000
MAX_SIZE = 900_000_000


def safe_path(name):
    if not isinstance(name, str) or len(name) > 240 or not name or "\\" in name:
        raise ValueError("Unsafe update file path")
    parts = name.split("/")
    if any(not p or p in (".", "..") or p.endswith((" ", ".")) or
           DISALLOWED.search(p) or RESERVED.match(p) or
           "'" in p or "{" in p or "}" in p or ";" in p for p in parts):
        raise ValueError("Unsafe update file path")
    return name


def _hash(stream):
    digest = sha256()
    size = 0
    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
        digest.update(chunk)
        size += len(chunk)
        if size > MAX_SIZE:
            raise ValueError("Oversized file")
    return size, digest.hexdigest()


def _validate_index(entries):
    if len(entries) > MAX_FILES or sum(size for size, _ in entries.values()) > MAX_SIZE:
        raise ValueError("Update exceeds size or file-count limits")
    names = {k.casefold() for k in entries}
    if len(names) != len(entries):
        raise ValueError("Case-insensitive path collision")
    for name in entries:
        for n in range(1, len(name.split("/"))):
            if "/".join(name.split("/")[:n]).casefold() in names:
                raise ValueError("File and directory path collision")


def read_release_zip(archive):
    result = {}
    with ZipFile(archive) as z:
        for member in z.infolist():
            if member.is_dir():
                continue
            if not member.filename.startswith(ROOT):
                raise ValueError("Unexpected release root")
            name = safe_path(member.filename[len(ROOT):])
            if name in result:
                raise ValueError("Duplicate file")
            with z.open(member) as stream:
                result[name] = _hash(stream)
    _validate_index(result)
    return result


def read_current_tree(root):
    result = {}
    root = Path(root)
    for p in root.rglob("*"):
        if p.is_symlink():
            raise ValueError("Symbolic links not supported")
        if not p.is_file():
            continue
        name = safe_path(p.relative_to(root).as_posix())
        with p.open("rb") as stream:
            result[name] = _hash(stream)
    _validate_index(result)
    return result


def _old_version(archive):
    with ZipFile(archive) as z:
        value = json.loads(z.read(ROOT + "version.json"))
    if value != {"version": value.get("version"), "platform": "windows-x64"}:
        raise ValueError("Invalid old release manifest")
    version = value["version"]
    if not isinstance(version, str) or not VERSION.fullmatch(version):
        raise ValueError("Invalid old release version")
    return version


def _new_version(root):
    value = json.loads((Path(root) / "version.json").read_text("utf-8"))
    if not isinstance(value, dict) or value != {
            "version": value.get("version"), "platform": "windows-x64"}:
        raise ValueError("Invalid new release manifest")
    version = value["version"]
    if not isinstance(version, str) or not VERSION.fullmatch(version):
        raise ValueError("Invalid new release version")
    return version


def _iss_path(name):
    return name.replace("/", "\\")


def generate_patch(previous_zip, current_root, original_iss, output_iss):
    """Return plan dict, after generating an Inno script with a strict guard."""
    old = read_release_zip(previous_zip)
    new = read_current_tree(current_root)
    from_version = _old_version(previous_zip)
    to_version = _new_version(current_root)
    if tuple(map(int, to_version.split("."))) <= tuple(map(int, from_version.split("."))):
        raise ValueError("Patch target must be newer than source")
    if not {"AstroBirthChart.exe", "AstroBirthChartUpdater.exe",
            "version.json", "_internal/data/ephemeris/de440s.bsp"}.issubset(new):
        raise ValueError("Current release lacks required files")
    changed = sorted(p for p in new if old.get(p) != new[p])
    reused = sorted(p for p in new if old.get(p) == new[p])
    removed = sorted(p for p in old if p not in new)
    if not changed or "version.json" not in changed:
        raise ValueError("No versioned update files")
    script = Path(original_iss).read_text("utf-8")
    if not script.count('[Files]') == 1 or not script.count('[Icons]') == 1:
        raise ValueError("Installer template does not contain expected sections")
    first, remainder = script.split("[Files]\n", 1)
    _, last = remainder.split("[Icons]\n", 1)
    rows = ["[Files]"]
    for name in changed:
        path = _iss_path(name)
        parent = path.rsplit("\\", 1)[0] if "\\" in path else ""
        directory = "{app}" + ("\\" + parent if parent else "")
        rows.append(
            f'Source: "dist\\AstroBirthChart\\{path}"; DestDir: "{directory}"; '
            'Flags: ignoreversion')
    # The marker is managed by the *full* installer and must remain present.
    rows += ["", "[InstallDelete]"]
    for name in removed:
        rows.append(f'Type: files; Name: "{{app}}\\{_iss_path(name)}"')
    code = [
        "[Code]",
        "function PrepareToInstall(var NeedsRestart: Boolean): String;",
        "var CurrentVersion: String;",
        "begin",
        "  Result := '';",
        "  if not RegQueryStringValue(HKCU,",
        "    'Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\AstroBirthChart.Windows_is1',",
        "    'DisplayVersion', CurrentVersion) then begin",
        "    Result := 'Existing registered AstroBirthChart installation not found';",
        "    Exit;",
        "  end;",
        f"  if CurrentVersion <> '{from_version}' then begin",
        "    Result := 'Update source version mismatch';",
        "    Exit;",
        "  end;",
        "  if not FileExists(ExpandConstant('{app}\\installed-by-setup.marker')) then begin",
        "    Result := 'Existing setup marker is missing';",
        "    Exit;",
        "  end;",
    ]
    for name in reused:
        path = _iss_path(name)
        expected = old[name][1]
        code.extend([
            f"  if not FileExists(ExpandConstant('{{app}}\\{path}')) then begin",
            "    Result := 'Installed file is missing. Use the full installer.';",
            "    Exit;",
            "  end;",
            f"  if CompareText(GetSHA256OfFile(ExpandConstant('{{app}}\\{path}')), '{expected}') <> 0 then begin",
            "    Result := 'Installed file digest differs. Use the full installer.';",
            "    Exit;",
            "  end;",
        ])
    # Old version.json is replaced, but still must be exact before installing.
    code.extend([
        "  if CompareText(GetSHA256OfFile(ExpandConstant('{app}\\version.json')),",
        f"    '{old['version.json'][1]}') <> 0 then begin",
        "    Result := 'Installed version manifest differs. Use the full installer.';",
        "    Exit;",
        "  end;",
        "end;",
    ])
    asset = f"AstroBirthChart-Setup-Delta-from-v{from_version}-to-v{to_version}"
    script = first + "\n".join(rows) + "\n\n[Icons]\n" + last
    script = script.replace("OutputBaseFilename=AstroBirthChart-Setup",
                            "OutputBaseFilename=" + asset)
    if "[Code]" in script:
        raise ValueError("Original installer has a Code section that must be reviewed")
    script += "\n" + "\n".join(code) + "\n"
    target = Path(output_iss)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(script, encoding="utf-8")
    return {"from": from_version, "to": to_version, "asset": asset + ".exe",
            "changed": changed, "reused": reused, "removed": removed,
            "reused_bytes": sum(new[p][0] for p in reused),
            "changed_bytes": sum(new[p][0] for p in changed)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("previous_zip", type=Path)
    parser.add_argument("current_root", type=Path)
    parser.add_argument("original_iss", type=Path)
    parser.add_argument("output_iss", type=Path)
    args = parser.parse_args()
    plan = generate_patch(
        args.previous_zip, args.current_root, args.original_iss, args.output_iss)
    print(json.dumps(plan, ensure_ascii=False))


if __name__ == "__main__":
    main()
