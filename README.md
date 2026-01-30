# Google Photos Takeout Tools

A collection of standalone Python scripts for processing and repairing data exported from **Google Photos Takeout**. The tools fix common Takeout issues such as metadata stored in JSON sidecar files, missing or incorrect timestamps, and inconsistent media metadata, so the archive can be cleanly imported into other photo management tools. The scripts use only the Python standard library, rely on ExifTool for metadata writing, and are designed to be run locally on your own data.

## Requirements

- Python **3.10 or newer**
- **ExifTool** (required) 

## Setup

### macOS

```bash
brew install python exiftool
```

### Linux

Debian / Ubuntu:
```bash
sudo apt install python3 python3-venv exiftool
```

RPM-based:
```bash
sudo dnf install python3 exiftool
```

Arch:
```bash
sudo pacman -S python exiftool
```

### Windows

1. Install Python from the official site  
   Make sure **Add Python to PATH** is enabled.
2. Download ExifTool for Windows
3. Rename `exiftool(-k).exe` to `exiftool.exe`
4. Add it to your PATH or place it next to the scripts

## Scripts

### takeout_json_to_exif.py

Copies metadata from Google Photos Takeout JSON sidecar files into the corresponding photo or video files.

What it does:
- Reads timestamps, GPS data, and descriptions from JSON
- Writes EXIF / QuickTime metadata using ExifTool
- Skips files that already contain valid metadata
- Shows progress while running

#### Usage

Run the script from the root of your Takeout directory:

```bash
python takeout_json_to_exif.py /path/to/Takeout
```

If no path is given, the current directory is used.

#### Common options

Dry run (recommended first):
```bash
python takeout_json_to_exif.py /path/to/Takeout --dry-run
```

Use local time instead of UTC:
```bash
python takeout_json_to_exif.py /path/to/Takeout --local-time
```

Update filesystem modification time:
```bash
python takeout_json_to_exif.py /path/to/Takeout --touch
```

Force overwriting existing metadata (use with care):
```bash
python takeout_json_to_exif.py /path/to/Takeout --force-time
python takeout_json_to_exif.py /path/to/Takeout --force-gps
python takeout_json_to_exif.py /path/to/Takeout --force-desc
```

You'll get a nice progress overview
```yaml
Scanning JSON sidecars...
Targets to check (media files): 3821
1243/3821  32% |██████████░░░░░░░░░░░░░| Google Photos/2019/
```
With a report in the end
```yaml
Done. Checked: 3821, updated: 2977, no-change: 721, failed: 0.
Pre-scan skips: unreadable_json=0, not_sidecar=0, no_match=0, no_ts=0
```

### deduplicate_media.py

Remove duplicate media files from a Google Photos Takeout archive.
This script finds **byte-identical** photos and videos and removes duplicates using simple and reliable rules.

#### How duplicates are identified

1. Files are grouped by size
2. A fast partial hash narrows candidates
3. A full SHA-256 hash confirms duplicates

Only files that are **100% identical** are considered duplicates.

#### Album vs non-album logic

Folder names are ignored.

- **Album folder**: contains a `metadata.json` file with a non-empty `title`
- **Non-album folder**: does not contain `metadata.json`

When the same media exists in both album and non-album folders, the script can decide which copy to keep.

By default, the **non-album copy is kept** and album copies are removed.

#### Usage

Preview what would be deleted:
```bash
python deduplicate_media.py /path/to/Takeout --delete-duplicates --dry-run
```

Delete duplicates:
```bash
python deduplicate_media.py /path/to/Takeout --delete-duplicates
```

#### Album policy options
Choose which copy to keep when album and non-album duplicates exist:

Keep non-album copy (default):
```bash
--album-policy keep-non-album
```

Keep album copy:
```bash
--album-policy keep-album
```

Ignore album logic and use fallback selection:
```bash
--album-policy keep-default
```

#### Fallback keeper selection

If multiple duplicates exist within the same category (all album or all non-album), the keeper is selected by:

```bash
--keep shortest   # default, shortest path
--keep oldest     # oldest modification time
--keep newest     # newest modification time
```

#### Sidecar JSON files

When a duplicate media file is deleted, its related JSON sidecars are **also deleted by default**:

- `filename.ext.json`
- `filename.ext.supplemental-metadata.json`

This keeps the archive consistent.

#### Report file

A TSV report is always written (default: `dedupe_report.tsv`).

Example format:
```
sha256    keeper_path    duplicate_path
```
Each row records exactly which file was kept and which was removed (or would be removed).

## Safety notes

- Files are modified **in place**
- Always test with `--dry-run`
- Keep a backup of your Takeout archive

## Disclaimer

Not affiliated with or endorsed by Google.
Google Photos Takeout formats may change over time.
