# Python Tools Collection

This repository contains various useful Python tools and utilities.

## Current Tools

### File Organizer (`file_organizer.py`)

A utility to automatically organize files in a directory by type (images, documents, videos, etc.).

#### Features:
- Organizes files by category (images, documents, videos, audio, archives, code, executables, fonts)
- Creates category folders automatically
- Dry-run mode to preview changes
- Verbose output for detailed logging
- Handles files without extensions
- Skips already organized files
- Preserves original filenames
- Handles filename conflicts by adding numbers

#### Usage:
```bash
# Basic usage
python file_organizer.py /path/to/directory

# Dry run to see what would happen
python file_organizer.py /path/to/directory --dry-run

# Verbose output
python file_organizer.py /path/to/directory --verbose

# Combine options
python file_organizer.py ~/Downloads --dry-run --verbose
```

#### Supported File Types:
- **Images**: jpg, jpeg, png, gif, bmp, tiff, webp, svg, ico, raw
- **Documents**: pdf, doc, docx, txt, rtf, odt, pages, tex, md, csv, xls, xlsx, ppt, pptx, ods, odp
- **Videos**: mp4, avi, mkv, mov, wmv, flv, webm, m4v, mpg, mpeg, 3gp, ts, vob
- **Audio**: mp3, wav, flac, aac, ogg, wma, m4a, aiff, alac, mid, midi
- **Archives**: zip, rar, 7z, tar, gz, bz2, xz, iso, dmg, cab, apk
- **Code**: py, js, html, css, java, cpp, c, h, cs, php, rb, go, rs, swift, kt, scala, pl, sh, bash, zsh, fish, sql, xml, json, yaml, yml, toml, ini, cfg, conf
- **Executables**: exe, msi, deb, rpm, dmg, app, bin, run
- **Fonts**: ttf, otf, woff, woff2, eot, pfb, pfm

#### Requirements:
- Python 3.6+

#### License:
MIT License - feel free to use, modify, and distribute.

#### Contributing:
Feel free to submit issues, fork the repository, and send pull requests!