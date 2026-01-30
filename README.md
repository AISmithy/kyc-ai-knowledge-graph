# KYC AI Knowledge Graph

Summary
- Objective: provide a small, maintainable Python pipeline to download, extract, and normalize GLEIF (Global Legal Entity Identifier Foundation) Level 1 (LEI records) and Level 2 (Relationship Records) data for use in KYC/AML knowledge-graph workflows.
- Scope: streaming-friendly ingestion for very large GLEIF XML/CSV files, lightweight normalization, and an example join of entities to parent relationships.

Project highlights
- Modular layout: configuration (`src/data_loader/config.py`), downloading (`src/data_loader/downloader.py`), processing (`src/data_loader/processors.py`), and orchestration (`src/data_loader/main.py`).
- Streaming XML support: large GLEIF XML files are parsed via `xml.etree.ElementTree.iterparse` to avoid loading multi-gigabyte files into memory.
- Output location: generated files are written under the `data/` directory (this directory is ignored by Git by default).

Quickstart
1. Create and activate a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. Install dependencies:

```powershell
pip install -r requirements.txt
```

3. Run the pipeline (downloads latest GLEIF concatenated files, extracts, and runs a preview normalization):

```powershell
cd src\data_loader
python -m data_loader.main
```

Or after installing the package in editable mode:

```powershell
pip install -e .
gleif-loader
```

What the pipeline does
- Scrapes the GLEIF detail page to find current concatenated-file download URLs.
- Downloads Level 1 and Level 2 ZIPs, extracts them to `data/gleif_downloads/`.
- Selects the largest data file in each package and performs a streaming preview (defaults: 50k LEI rows, 200k RR rows).
- Normalizes common columns (LEI, legal name, status; relationship start/end, type, status) and demonstrates a left-join of entities to parent relationships.

Notes & Next steps
- Relationship Records (RR) can vary in structure; the code includes a fallback when direct start/end LEI columns are not present. I can add more robust RR parsing (node traversal) on request.
- For production use, I recommend adding a streaming XML→Parquet writer to persist records without holding them in memory.
- Consider adding CLI flags for `--nrows`, `--out-format` (csv/parquet), and `--extract-only`.

Project layout

```
src/data_loader/
  ├─ __init__.py
  ├─ config.py         # paths and constants
  ├─ downloader.py     # scraping, downloading, extracting
  ├─ processors.py     # streaming parsing and normalization
  └─ main.py           # orchestration and CLI entrypoint

data/                 # generated data output (ignored by Git)
requirements.txt      # dependencies
setup.py / pyproject.toml
.gitignore
```

Commands to stop tracking existing `data/` in Git (if already committed)

```powershell
git rm -r --cached data
git commit -m "Stop tracking data/ directory"
```

If you want, I can:
- Add a streaming XML→Parquet writer and an option to output full datasets as Parquet files.
- Improve RR parsing to extract parent/child relationships from nested nodes.
- Add CLI flags and unit tests.

License: MIT

A Python project for loading and processing GLEIF (Global Legal Entity Identifier Foundation) data for KYC (Know Your Customer) AI knowledge graph applications.

## Features

- Download latest GLEIF Level 1 (LEI records) and Level 2 (Relationship Records) data
- Automatic extraction and normalization of GLEIF datasets
- Column mapping for flexible GLEIF data format versions
- Join entity records with relationship information
- Output data organized in the `data/` directory

## Installation

### Using pip (development mode)

```bash
pip install -e .
```

Or install with dependencies:

```bash
pip install -r requirements.txt
```

## Usage

### As a command-line tool

Once installed, you can run the GLEIF loader:

```bash
gleif-loader
```

### As a Python module

```python
from data_loader.main import main

lei_df, rr_df, joined_df = main()
```

### Individual components

```python
from data_loader.downloader import download_and_extract_gleif_data
from data_loader.processors import load_and_normalize_lei_data, load_and_normalize_rr_data

# Download and extract
lei_csv, rr_csv = download_and_extract_gleif_data(...)

# Load data
lei_df = load_and_normalize_lei_data(lei_csv)
rr_df = load_and_normalize_rr_data(rr_csv)
```

## Project Structure

```
kyc-ai-knowledge-graph/
├── src/
│   └── data_loader/              # Main package
│       ├── __init__.py
│       ├── config.py             # Configuration and constants
│       ├── downloader.py         # Download and extraction logic
│       ├── processors.py         # Data loading and normalization
│       └── main.py               # Pipeline orchestration
├── data/                         # Generated data output directory
│   └── gleif_downloads/          # Downloaded and extracted GLEIF files
├── requirements.txt              # Python dependencies
├── setup.py                      # Package setup configuration
├── pyproject.toml               # Modern Python project configuration
├── README.md                     # This file
└── .gitignore                   # Git ignore rules
```

## Configuration

All configuration is centralized in `src/data_loader/config.py`:

- `DATA_DIR`: Output directory for generated data (defaults to `data/`)
- `DOWNLOADS_DIR`: Directory for downloaded ZIP files
- `LEI_EXTRACT_DIR`: Directory for extracted Level 1 data
- `RR_EXTRACT_DIR`: Directory for extracted Level 2 data
- `LEI_PREVIEW_ROWS`: Number of LEI rows to load (default: 50,000)
- `RR_PREVIEW_ROWS`: Number of relationship rows to load (default: 200,000)

## Requirements

- Python 3.8+
- requests
- pandas
- beautifulsoup4

## Development

To set up a development environment:

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode
pip install -e .
```

## License

MIT
