"""Download build-time JPL kernel, verify fixed SHA-256, never run from the app."""
import hashlib
import urllib.request
from pathlib import Path

URL = "https://naif.jpl.nasa.gov/pub/naif/generic_kernels/spk/planets/de440s.bsp"
SHA256 = "c1c7feeab882263fc493a9d5a5b2ddd71b54826cdf65d8d17a76126b260a49f2"
SIZE = 32726016
DEST = Path(__file__).resolve().parents[1] / "data" / "ephemeris" / "de440s.bsp"


def verified(path):
    if not path.is_file() or path.stat().st_size != SIZE:
        return False
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest() == SHA256


def main():
    DEST.parent.mkdir(parents=True, exist_ok=True)
    if verified(DEST):
        print("DE440s already verified.")
        return
    part = DEST.with_suffix(".bsp.part")
    try:
        with urllib.request.urlopen(URL, timeout=90) as response, part.open("wb") as target:
            for chunk in iter(lambda: response.read(1024 * 1024), b""):
                target.write(chunk)
        if not verified(part):
            raise RuntimeError("DE440s size or SHA256 mismatch; refusing to use kernel")
        part.replace(DEST)
        print("Downloaded and verified:", DEST)
    finally:
        part.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
