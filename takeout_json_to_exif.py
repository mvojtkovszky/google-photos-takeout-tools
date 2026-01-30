#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path
from shutil import get_terminal_size

MEDIA_EXTS = {
    ".jpg", ".jpeg", ".heic", ".png", ".gif", ".webp",
    ".mp4", ".mov", ".m4v", ".avi", ".3gp"
}

SUPPLEMENTAL_SUFFIX = ".supplemental-metadata.json"


def run(cmd, dry_run=False):
    if dry_run:
        print("[DRY-RUN]", " ".join(cmd))
        return 0, "", ""
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return p.returncode, p.stdout, p.stderr


def parse_ts(value):
    if value is None:
        return None
    try:
        return int(str(value))
    except Exception:
        return None


def pick_ts(obj):
    ts = parse_ts((obj.get("photoTakenTime") or {}).get("timestamp"))
    if ts is None:
        ts = parse_ts((obj.get("creationTime") or {}).get("timestamp"))
    return ts


def ts_to_exif_datetime(sec, use_utc=True):
    if use_utc:
        d = dt.datetime.fromtimestamp(sec, tz=dt.timezone.utc)
    else:
        d = dt.datetime.fromtimestamp(sec)
    return d.strftime("%Y:%m:%d %H:%M:%S")


def pick_geo(obj):
    geo = obj.get("geoDataExif") or obj.get("geoData") or {}
    lat = geo.get("latitude")
    lon = geo.get("longitude")
    alt = geo.get("altitude")
    # Google often uses 0,0 when unknown
    if lat is None or lon is None:
        return None
    if float(lat) == 0.0 and float(lon) == 0.0:
        return None
    return (float(lat), float(lon), float(alt) if alt is not None else None)


def set_file_mtime(path: Path, sec: int, dry_run=False):
    if dry_run:
        print(f"[DRY-RUN] touch mtime {path} -> {sec}")
        return
    os.utime(path, (sec, sec))


def list_media_in_dir(parent: Path):
    media = {}
    for p in parent.iterdir():
        if p.is_file() and p.suffix.lower() in MEDIA_EXTS:
            media[p.name.lower()] = p
    return media


def strip_known_json_wrappers(json_name: str) -> str:
    # IMG_4166.HEIC.supplemental-metadata.json -> IMG_4166.HEIC
    if json_name.lower().endswith(SUPPLEMENTAL_SUFFIX):
        return json_name[:-len(SUPPLEMENTAL_SUFFIX)]
    # IMG_1234.jpg.json -> IMG_1234.jpg
    if json_name.lower().endswith(".json"):
        return json_name[:-5]
    return json_name


def candidate_names_from_json(json_path: Path, obj: dict):
    jname = json_path.name
    candidates = []

    # Strongest signal: "title" field (your examples show it consistently)
    title = obj.get("title")
    if isinstance(title, str) and title:
        candidates.append(title)

    # Supplemental pattern
    base = strip_known_json_wrappers(jname)
    candidates.append(base)

    base_path = Path(base)

    # If base has no extension, try common ones
    if base_path.suffix == "":
        for ext in MEDIA_EXTS:
            candidates.append(base + ext)

    # Handle UUID-ish numeric tail mismatch:
    # C...-000.json -> C...-0000.mov (and similar)
    stem = base_path.stem
    ext = base_path.suffix
    for zeros in ("0", "00"):
        if ext:
            candidates.append(f"{stem}{zeros}{ext}")
        else:
            for mext in MEDIA_EXTS:
                candidates.append(f"{stem}{zeros}{mext}")

    return candidates


def find_media_for_json(json_path: Path, obj: dict) -> Path | None:
    media_lookup = list_media_in_dir(json_path.parent)
    for name in candidate_names_from_json(json_path, obj):
        hit = media_lookup.get(name.lower())
        if hit:
            return hit
    return None


def exiftool_read_json(media_path: Path):
    """
    Read key fields from the file using exiftool JSON output.
    We avoid parsing human-readable exiftool output.
    """
    cmd = [
        "exiftool", "-j", "-n",
        "-DateTimeOriginal", "-CreateDate", "-ModifyDate",
        "-TrackCreateDate", "-MediaCreateDate", "-CreationDate",
        "-GPSLatitude", "-GPSLongitude", "-GPSAltitude",
        "-Description", "-ImageDescription", "-Caption-Abstract",
        str(media_path)
    ]
    rc, out, err = run(cmd, dry_run=False)
    if rc != 0 or not out.strip():
        return None
    try:
        arr = json.loads(out)
        return arr[0] if arr else None
    except Exception:
        return None


def parse_exif_datetime(s: str):
    # Expected: "YYYY:MM:DD HH:MM:SS" optionally with timezone; we handle basic case.
    if not s or not isinstance(s, str):
        return None
    s = s.strip()
    try:
        return dt.datetime.strptime(s[:19], "%Y:%m:%d %H:%M:%S").replace(tzinfo=dt.timezone.utc)
    except Exception:
        return None


def pick_existing_time(exif: dict):
    """
    Pick the best existing timestamp depending on what the file has.
    For photos: DateTimeOriginal is preferred.
    For videos: QuickTime tags like MediaCreateDate / TrackCreateDate are common.
    """
    if not exif:
        return None

    for key in ("DateTimeOriginal", "CreateDate", "MediaCreateDate", "TrackCreateDate", "CreationDate", "ModifyDate"):
        val = exif.get(key)
        d = parse_exif_datetime(val) if isinstance(val, str) else None
        if d:
            return d
    return None


def gps_is_missing_or_zero(exif: dict):
    if not exif:
        return True
    lat = exif.get("GPSLatitude")
    lon = exif.get("GPSLongitude")
    if lat is None or lon is None:
        return True
    try:
        if float(lat) == 0.0 and float(lon) == 0.0:
            return True
    except Exception:
        return True
    return False


def text_is_empty(exif: dict):
    if not exif:
        return True
    for key in ("Description", "ImageDescription", "Caption-Abstract"):
        v = exif.get(key)
        if isinstance(v, str) and v.strip():
            return False
    return True


def build_write_cmd(media_path: Path, dt_str: str | None, geo, desc: str | None, use_utc: bool):
    cmd = ["exiftool", "-overwrite_original", "-P"]
    if use_utc:
        cmd += ["-api", "QuickTimeUTC=1"]

    if dt_str:
        cmd += [
            f"-DateTimeOriginal={dt_str}",
            f"-CreateDate={dt_str}",
            f"-ModifyDate={dt_str}",
            f"-AllDates={dt_str}",
        ]

    if desc:
        cmd += [
            f"-Description={desc}",
            f"-ImageDescription={desc}",
            f"-Caption-Abstract={desc}",
            f"-XPComment={desc}",
        ]

    if geo:
        lat, lon, alt = geo
        cmd += [f"-GPSLatitude={lat}", f"-GPSLongitude={lon}"]
        if alt is not None:
            cmd += [f"-GPSAltitude={alt}"]

    cmd += [str(media_path)]
    return cmd


class Progress:
    def __init__(self, total: int, root: Path):
        self.total = max(0, int(total))
        self.root = root
        self.last_len = 0

    def _bar(self, done: int):
        width = get_terminal_size((100, 20)).columns
        # reserve space for text around the bar
        # " 9999/9999 100% |[.....]| folder"
        bar_width = max(10, min(40, width - 40))
        if self.total <= 0:
            frac = 0.0
        else:
            frac = min(1.0, max(0.0, done / self.total))
        filled = int(round(frac * bar_width))
        return "█" * filled + "░" * (bar_width - filled), int(round(frac * 100))

    def update(self, done: int, current_folder: Path | None):
        bar, pct = self._bar(done)
        folder_str = ""
        if current_folder is not None:
            try:
                folder_str = str(current_folder.relative_to(self.root))
            except Exception:
                folder_str = str(current_folder)
        msg = f"{done}/{self.total} {pct:3d}% |{bar}| {folder_str}"
        # overwrite the previous line cleanly
        pad = " " * max(0, self.last_len - len(msg))
        sys.stderr.write("\r" + msg + pad)
        sys.stderr.flush()
        self.last_len = len(msg)

    def done(self):
        sys.stderr.write("\n")
        sys.stderr.flush()


def main():
    ap = argparse.ArgumentParser(description="Safely populate EXIF/metadata from Google Takeout JSON sidecars.")
    ap.add_argument("root", nargs="?", default=".", help="Root directory to scan recursively.")
    ap.add_argument("--dry-run", action="store_true", help="Show what would change without writing.")
    ap.add_argument("--local-time", action="store_true", help="Write dates in local time instead of UTC.")
    ap.add_argument("--touch", action="store_true", help="Also set filesystem mtime to taken time when we write time tags.")
    ap.add_argument("--time-threshold-seconds", type=int, default=300,
                    help="Only overwrite existing time if it differs by more than this many seconds (default 300 = 5 min).")
    ap.add_argument("--force-time", action="store_true", help="Always write time from JSON (not recommended).")
    ap.add_argument("--force-gps", action="store_true", help="Always write GPS from JSON (not recommended).")
    ap.add_argument("--force-desc", action="store_true", help="Always write description from JSON (not recommended).")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    use_utc = not args.local_time

    json_files = sorted(root.rglob("*.json"))
    if not json_files:
        print("No JSON files found under:", root)
        return

    # Pre-scan: build concrete jobs so we can show an accurate progress total.
    # We count "target media files to be checked" as UNIQUE matched media files.
    jobs = []
    seen_media = set()
    skipped_unreadable = 0
    skipped_not_sidecar = 0
    skipped_no_match = 0
    skipped_no_ts = 0

    for jp in json_files:
        try:
            obj = json.loads(jp.read_text(encoding="utf-8"))
        except Exception:
            skipped_unreadable += 1
            continue

        if "title" not in obj:
            skipped_not_sidecar += 1
            continue

        media = find_media_for_json(jp, obj)
        if not media:
            skipped_no_match += 1
            continue

        ts = pick_ts(obj)
        if ts is None:
            skipped_no_ts += 1
            continue

        # Ensure unique media targets
        mkey = str(media.resolve())
        if mkey in seen_media:
            continue
        seen_media.add(mkey)

        jobs.append((jp, media, obj, ts))

    total_targets = len(jobs)
    if total_targets == 0:
        print("No matching media targets found under:", root)
        print(f"Details: unreadable_json={skipped_unreadable}, not_sidecar={skipped_not_sidecar}, no_match={skipped_no_match}, no_ts={skipped_no_ts}")
        return

    print(f"Targets to check (media files): {total_targets}")
    prog = Progress(total_targets, root)

    updated = 0
    checked = 0
    no_change_needed = 0
    failed_write = 0

    last_folder = None

    for (jp, media, obj, ts) in jobs:
        checked += 1
        current_folder = media.parent
        # Update progress every file; it includes the current folder
        prog.update(checked, current_folder)

        target_dt_str = ts_to_exif_datetime(ts, use_utc=use_utc)
        target_dt = dt.datetime.fromtimestamp(ts, tz=dt.timezone.utc)

        geo = pick_geo(obj)
        desc = obj.get("description")
        if isinstance(desc, str) and not desc.strip():
            desc = None

        exif = exiftool_read_json(media)
        existing_dt = pick_existing_time(exif)  # stored as UTC in our parser
        need_time = False
        need_gps = False
        need_desc = False

        if args.force_time:
            need_time = True
        else:
            if existing_dt is None:
                need_time = True
            else:
                diff = abs((existing_dt - target_dt).total_seconds())
                if diff > args.time_threshold_seconds:
                    need_time = True

        if geo:
            if args.force_gps:
                need_gps = True
            else:
                if gps_is_missing_or_zero(exif):
                    need_gps = True

        if desc:
            if args.force_desc:
                need_desc = True
            else:
                if text_is_empty(exif):
                    need_desc = True

        if not (need_time or need_gps or need_desc):
            no_change_needed += 1
            continue

        cmd = build_write_cmd(
            media_path=media,
            dt_str=target_dt_str if need_time else None,
            geo=geo if need_gps else None,
            desc=desc if need_desc else None,
            use_utc=use_utc
        )

        if args.dry_run:
            # Keep progress line intact: print a newline before details
            sys.stderr.write("\n")
            print(f"Would update: {media}")
            if need_time:
                print(f"  time -> {target_dt_str}")
            if need_gps:
                print(f"  gps  -> {geo}")
            if need_desc:
                print(f"  desc -> (non-empty)")
            run(cmd, dry_run=True)
            # Re-draw progress line after verbose output
            prog.update(checked, current_folder)
            continue

        rc, out, err = run(cmd, dry_run=False)
        if rc == 0:
            updated += 1
            if args.touch and need_time:
                set_file_mtime(media, ts, dry_run=False)
        else:
            failed_write += 1

    prog.done()
    print(
        "Done. "
        f"Checked: {checked}, updated: {updated}, no-change: {no_change_needed}, failed: {failed_write}. "
        f"Pre-scan skips: unreadable_json={skipped_unreadable}, not_sidecar={skipped_not_sidecar}, no_match={skipped_no_match}, no_ts={skipped_no_ts}"
    )


if __name__ == "__main__":
    main()
