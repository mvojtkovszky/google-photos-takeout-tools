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
Done. Checked: 3821, updated: 2974, no-change: 721, failed: 3.
Pre-scan skips: unreadable_json=12, not_sidecar=184, no_match=96, no_ts=31
```

## Safety notes

- Files are modified **in place**
- Always test with `--dry-run`
- Keep a backup of your Takeout archive

## Disclaimer

Not affiliated with or endorsed by Google.
Google Photos Takeout formats may change over time.
