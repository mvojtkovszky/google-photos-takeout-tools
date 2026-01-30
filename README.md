# Google Photos Takeout Tools

A small collection of Python scripts for processing data exported from **Google Photos Takeout**.

The scripts help fix common Takeout issues such as metadata stored in JSON sidecar files, incorrect or missing timestamps, and inconsistent media metadata, so the archive can be imported cleanly into other photo management tools.

---

## What this project is

- Simple, standalone Python scripts
- Focused on Google Photos Takeout archives
- No Python dependencies beyond the standard library
- Uses ExifTool for all metadata writing
- Designed to be run locally on your own data

---

## Requirements

- Python **3.10 or newer**
- **ExifTool** (required)

---

## Setup

### macOS

Install Python (if needed) and ExifTool using Homebrew:

```bash
brew install python exiftool
```

---

### Linux

Debian / Ubuntu:

```bash
sudo apt install python3 python3-venv exiftool
```

Arch:

```bash
sudo pacman -S python exiftool
```

---

### Windows

1. Install Python from the official site  
   Make sure **Add Python to PATH** is enabled.
2. Download ExifTool for Windows
3. Rename `exiftool(-k).exe` to `exiftool.exe`
4. Add it to your PATH or place it next to the scripts

Verify setup on all platforms:

```bash
python --version
exiftool -ver
```

---

## Scripts

### takeout_json_to_exif.py

Copies metadata from Google Photos Takeout JSON sidecar files into the corresponding photo or video files.

What it does:
- Reads timestamps, GPS data, and descriptions from JSON
- Writes EXIF / QuickTime metadata using ExifTool
- Skips files that already contain valid metadata
- Shows progress while running

---

## Usage

Run the script from the root of your Takeout directory:

```bash
python takeout_json_to_exif.py /path/to/Takeout
```

If no path is given, the current directory is used.

---

## Common options

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

---

## Safety notes

- Files are modified **in place**
- Always test with `--dry-run`
- Keep a backup of your Takeout archive

---

## License

Licensed under the **Apache License, Version 2.0**.

See the `LICENSE` file for details.

---

## Disclaimer

Not affiliated with or endorsed by Google.
Google Photos Takeout formats may change over time.
