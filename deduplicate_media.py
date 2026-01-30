#!/usr/bin/env python3
"""
deduplicate_media.py

Deduplicate byte-identical media files in a directory tree.

Rules:
- Album folder = folder containing metadata.json with a non-empty "title"
- Non-album folder = any folder without such metadata.json
- Folder names are ignored entirely

Behavior:
- Default: report only
- --delete-duplicates: delete duplicates (keeps one copy)
- --album-policy controls whether album or non-album copy is preferred
- Related JSON sidecars are deleted by default
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from shutil import get_terminal_size
from typing import Dict, Iterable, List, Optional


MEDIA_EXTS = {
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic", ".tif", ".tiff",
    ".mp4", ".mov", ".m4v", ".avi", ".mkv", ".3gp", ".mts",
}

SUPPLEMENTAL_SUFFIX = ".supplemental-metadata.json"


@dataclass(frozen=True)
class FileInfo:
    path: Path
    size: int


class Progress:
    def __init__(self, total: int, root: Path):
        self.total = total
        self.root = root
        self.last_len = 0

    def update(self, done: int, folder: Optional[Path]):
        width = get_terminal_size((100, 20)).columns
        bar_width = max(10, min(40, width - 40))
        frac = 0 if self.total == 0 else min(1.0, done / self.total)
        filled = int(frac * bar_width)
        bar = "█" * filled + "░" * (bar_width - filled)
        pct = int(frac * 100)

        folder_str = ""
        if folder:
            try:
                folder_str = str(folder.relative_to(self.root))
            except Exception:
                folder_str = str(folder)

        msg = f"{done}/{self.total} {pct:3d}% |{bar}| {folder_str}"
        pad = " " * max(0, self.last_len - len(msg))
        sys.stderr.write("\r" + msg + pad)
        sys.stderr.flush()
        self.last_len = len(msg)

    def done(self):
        sys.stderr.write("\n")
        sys.stderr.flush()


def is_media_file(p: Path) -> bool:
    return p.is_file() and p.suffix.lower() in MEDIA_EXTS


def iter_media_files(root: Path) -> Iterable[FileInfo]:
    for p in root.rglob("*"):
        if is_media_file(p):
            try:
                st = p.stat()
            except OSError:
                continue
            yield FileInfo(p, st.st_size)


def sha256_file(path: Path, buf_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(buf_size):
            h.update(chunk)
    return h.hexdigest()


def quick_hash(path: Path, size: int) -> str:
    h = hashlib.sha256()
    h.update(str(size).encode())
    with path.open("rb") as f:
        h.update(f.read(64 * 1024))
        if size > 64 * 1024:
            f.seek(max(0, size - 64 * 1024))
            h.update(f.read(64 * 1024))
    return h.hexdigest()


def is_album_folder(folder: Path) -> bool:
    meta = folder / "metadata.json"
    if not meta.is_file():
        return False
    try:
        obj = json.loads(meta.read_text(encoding="utf-8"))
    except Exception:
        return False
    return isinstance(obj, dict) and isinstance(obj.get("title"), str) and obj["title"].strip()


def related_sidecars(media: Path) -> List[Path]:
    folder = media.parent
    name = media.name
    lower = name.lower()

    candidates = [
        folder / (name + ".json"),
        folder / (name + SUPPLEMENTAL_SUFFIX),
    ]

    for jp in folder.glob("*.json"):
        j = jp.name.lower()
        if j == lower + ".json" or j == lower + SUPPLEMENTAL_SUFFIX:
            candidates.append(jp)

    out, seen = [], set()
    for p in candidates:
        try:
            rp = p.resolve()
        except Exception:
            rp = p
        if p.exists() and rp not in seen:
            seen.add(rp)
            out.append(p)
    return out


def pick_keeper(
    paths: List[Path],
    album_policy: str,
    default_policy: str,
) -> Path:
    album = [p for p in paths if is_album_folder(p.parent)]
    non_album = [p for p in paths if not is_album_folder(p.parent)]

    if album and non_album:
        if album_policy == "keep-album":
            paths = album
        elif album_policy == "keep-non-album":
            paths = non_album

    if default_policy == "oldest":
        return min(paths, key=lambda p: p.stat().st_mtime)
    if default_policy == "newest":
        return max(paths, key=lambda p: p.stat().st_mtime)

    # shortest path
    return min(paths, key=lambda p: (len(str(p)), str(p).lower()))


def main():
    ap = argparse.ArgumentParser(description="Deduplicate byte-identical media files.")
    ap.add_argument("root", nargs="?", default=".", help="Root directory to scan")
    ap.add_argument("--delete-duplicates", action="store_true", help="Delete duplicates")
    ap.add_argument("--dry-run", action="store_true", help="Show actions without deleting")
    ap.add_argument(
        "--album-policy",
        choices=["keep-non-album", "keep-album", "keep-default"],
        default="keep-non-album",
        help="Which copy to keep when album and non-album duplicates exist",
    )
    ap.add_argument(
        "--keep",
        choices=["shortest", "oldest", "newest"],
        default="shortest",
        help="Fallback keeper selection strategy",
    )
    ap.add_argument("--report", default="dedupe_report.tsv", help="TSV report output")

    args = ap.parse_args()
    root = Path(args.root).resolve()

    files = list(iter_media_files(root))
    by_size: Dict[int, List[Path]] = {}
    for fi in files:
        by_size.setdefault(fi.size, []).append(fi.path)

    size_groups = [ps for ps in by_size.values() if len(ps) > 1]
    candidates = [p for ps in size_groups for p in ps]

    prog = Progress(len(candidates), root)
    by_qh: Dict[str, List[Path]] = {}
    done = 0
    for ps in size_groups:
        size = ps[0].stat().st_size
        for p in ps:
            done += 1
            prog.update(done, p.parent)
            try:
                qh = quick_hash(p, size)
            except OSError:
                continue
            by_qh.setdefault((size, qh), []).append(p)
    prog.done()

    by_hash: Dict[str, List[Path]] = {}
    for ps in by_qh.values():
        if len(ps) < 2:
            continue
        for p in ps:
            h = sha256_file(p)
            by_hash.setdefault(h, []).append(p)

    dup_sets = [ps for ps in by_hash.values() if len(ps) > 1]

    with Path(args.report).open("w", encoding="utf-8") as f:
        f.write("sha256\tkeeper\tduplicate\n")
        for h, ps in by_hash.items():
            if len(ps) < 2:
                continue
            keeper = pick_keeper(ps, args.album_policy, args.keep)
            for p in ps:
                if p != keeper:
                    f.write(f"{h}\t{keeper}\t{p}\n")

    if not args.delete_duplicates:
        print(f"Duplicate sets: {len(dup_sets)} (report only)")
        return

    deleted = 0
    sidecars = 0

    for ps in dup_sets:
        keeper = pick_keeper(ps, args.album_policy, args.keep)
        for p in ps:
            if p == keeper:
                continue
            scs = related_sidecars(p)
            if args.dry_run:
                print(f"[DRY-RUN] delete {p}")
                for sc in scs:
                    print(f"[DRY-RUN] delete sidecar {sc}")
            else:
                p.unlink()
                deleted += 1
                for sc in scs:
                    if sc.exists():
                        sc.unlink(missing_ok=True)
                        sidecars += 1

    print(
        f"Done. duplicate_sets={len(dup_sets)}, "
        f"deleted_files={deleted}, deleted_sidecars={sidecars}"
    )


if __name__ == "__main__":
    main()
