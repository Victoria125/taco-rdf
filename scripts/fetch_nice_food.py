"""Download the NEVO subgraphs of NICE-Food from their pinned Zenodo release, checking each file's MD5.

NICE-Food types each NEVO food with its FoodOn class, as this project types TACO foods, so the comparison
of the two alignments reads these files. They are not committed: data/external/ is ignored by git, and
NEVO's own conditions (see data/SOURCES.md) only allow the data unchanged and with its source and version.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "external" / "nice-food"

# NICE-Food v3, published by RIVM on 2026-02-03; the record's licence covers all its files.
RECORD = "https://zenodo.org/records/18450818"
DOI = "10.5281/zenodo.18450818"
LICENSE = "https://creativecommons.org/licenses/by/4.0/"
FILES = {
    "nevo21_graph.ttl": "803c4f20e9902dc9cd2cf939ba380356",
    "nevo23_graph.ttl": "962ca4fa740493a4e7b04c8c7e9b6cd6",
    "nice_food_datamodel.svg": "fc4811114a7fa1336a849d12ecd884ac",
}


def md5(path: Path) -> str:
    digest = hashlib.md5()  # Zenodo publishes MD5 checksums only
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fetch(name: str, expected: str, out_dir: Path) -> Path:
    target = out_dir / name
    if target.exists() and md5(target) == expected:
        print(f"{name}: present, checksum matches")
        return target
    partial = target.with_name(name + ".part")
    url = f"{RECORD}/files/{name}?download=1"
    print(f"{name}: downloading {url}", file=sys.stderr)
    urllib.request.urlretrieve(url, str(partial))
    got = md5(partial)
    if got != expected:
        partial.unlink()
        raise ValueError(f"{name}: MD5 {got} differs from the record's {expected}")
    partial.replace(target)
    print(f"{name}: downloaded, checksum matches")
    return target


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("-o", "--out", type=Path, default=OUT_DIR, help=f"folder to write to (default {OUT_DIR})")
    out_dir = p.parse_args().out
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        for name, expected in FILES.items():
            fetch(name, expected, out_dir)
    except (OSError, ValueError) as exc:
        print(exc, file=sys.stderr)
        return 1
    print(f"NICE-Food {DOI}, {LICENSE}; files in {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
