"""Merge `Data/4년재/4년재/` into `Data/영남권/경북/`. Same path + same SHA-256: drop source.

Run:  python scripts/reorganize_gyeongbuk_import.py
"""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DATA = REPO / "Data"
DEST_ROOT = DATA / "영남권" / "경북"


def file_sha256(path: Path, chunk: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def pick_src_root() -> Path | None:
    nested = DATA / "4년재" / "4년재"
    if nested.is_dir() and any(nested.iterdir()):
        return nested
    flat = DATA / "4년재"
    if flat.is_dir() and any(flat.iterdir()):
        return flat
    nested2 = DATA / "4년제" / "4년제"
    if nested2.is_dir() and any(nested2.iterdir()):
        return nested2
    flat2 = DATA / "4년제"
    if flat2.is_dir() and any(flat2.iterdir()):
        return flat2
    return None


def main() -> None:
    src_root = pick_src_root()
    if src_root is None:
        print("No Data/4년재 (or 4년제) import tree. Nothing to do.")
        return

    DEST_ROOT.mkdir(parents=True, exist_ok=True)
    moved = 0
    skipped_dup = 0
    renamed = 0

    for path in sorted(src_root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(src_root)
        dest = DEST_ROOT / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            if file_sha256(path) == file_sha256(dest):
                path.unlink()
                skipped_dup += 1
                continue
            alt = dest.with_name(dest.stem + "_중복" + dest.suffix)
            n = 2
            while alt.exists():
                alt = dest.with_name(f"{dest.stem}_중복{n}{dest.suffix}")
                n += 1
            shutil.move(str(path), str(alt))
            renamed += 1
            print("conflict ->", alt.relative_to(DATA))
        else:
            shutil.move(str(path), str(dest))
            moved += 1
            print("move", rel)

    # Remove emptied import dirs (bottom-up)
    for base in (DATA / "4년재", DATA / "4년제"):
        if not base.exists():
            continue
        for sub in sorted(base.rglob("*"), key=lambda p: len(p.parts), reverse=True):
            if sub.is_dir():
                try:
                    sub.rmdir()
                except OSError:
                    pass
        try:
            base.rmdir()
        except OSError:
            print("note: could not remove", base, "(not empty?)")

    print(f"done: moved={moved}, same_hash_removed={skipped_dup}, conflict_renamed={renamed}")

    # Same folder, identical bytes, different filenames (e.g. renamed vs 공지 원본)
    def format_pref(p: Path) -> tuple[int, int]:
        s = p.suffix.lower()
        tier = 0 if s in {".xlsx", ".xlsm", ".xls"} else 1 if s == ".pdf" else 2
        return (tier, len(p.name))

    removed_inner = 0
    for folder in sorted(DEST_ROOT.rglob("*")):
        if not folder.is_dir():
            continue
        by_hash: dict[str, list[Path]] = {}
        for f in folder.iterdir():
            if not f.is_file():
                continue
            h = file_sha256(f)
            by_hash.setdefault(h, []).append(f)
        for paths in by_hash.values():
            if len(paths) < 2:
                continue
            keep = sorted(paths, key=format_pref)[0]
            for p in paths:
                if p == keep:
                    continue
                print("unlink same-hash", p.relative_to(DATA))
                p.unlink()
                removed_inner += 1
    if removed_inner:
        print(f"same-folder duplicate bytes removed: {removed_inner}")


if __name__ == "__main__":
    main()
