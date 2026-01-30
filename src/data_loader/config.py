"""Configuration and constants for GLEIF data loader."""

from pathlib import Path

# Output directory - data generated should go to the data folder
DATA_DIR = Path(__file__).parent.parent.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Download staging directory
DOWNLOADS_DIR = DATA_DIR / "gleif_downloads"
DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)

# Extract directories
LEI_EXTRACT_DIR = DOWNLOADS_DIR / "level1_lei"
RR_EXTRACT_DIR = DOWNLOADS_DIR / "level2_rr"

# GLEIF URLs and endpoints
GLEIF_DETAIL_PAGE = "https://www.gleif.org/en/lei-data/gleif-concatenated-file/download-the-concatenated-file/detail"
HTTP_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; GLEIF-downloader/1.0)"}

# Data loading parameters
LEI_PREVIEW_ROWS = 50_000
RR_PREVIEW_ROWS = 200_000

# Chunk size for streaming downloads (1MB)
DOWNLOAD_CHUNK_SIZE = 1024 * 1024

# Timeout for HTTP requests (in seconds)
HTTP_TIMEOUT = 120
HTML_FETCH_TIMEOUT = 60
