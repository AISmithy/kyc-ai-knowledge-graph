"""Download and extract GLEIF data files."""

import zipfile
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from .config import (
    GLEIF_DETAIL_PAGE,
    HTTP_HEADERS,
    DOWNLOAD_CHUNK_SIZE,
    HTML_FETCH_TIMEOUT,
)


def download_file(url: str, dest: Path, chunk_size: int = DOWNLOAD_CHUNK_SIZE) -> None:
    """Stream-download a file to disk.
    
    Args:
        url: URL to download from
        dest: Destination file path
        chunk_size: Size of chunks to download (bytes)
    """
    with requests.get(url, stream=True, headers=HTTP_HEADERS, timeout=120) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=chunk_size):
                if chunk:
                    f.write(chunk)


def unzip_to_dir(zip_path: Path, extract_dir: Path) -> None:
    """Extract a ZIP file to a directory.
    
    Args:
        zip_path: Path to the ZIP file
        extract_dir: Directory to extract to
    """
    extract_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(extract_dir)


def find_csv_in_dir(folder: Path) -> list[Path]:
    """Find all CSV files in a directory recursively.
    
    Args:
        folder: Directory to search
        
    Returns:
        Sorted list of CSV file paths
    """
    return sorted(folder.rglob("*.csv"))


def find_xml_in_dir(folder: Path) -> list[Path]:
    """Find all XML files in a directory recursively.
    
    Args:
        folder: Directory to search
        
    Returns:
        Sorted list of XML file paths
    """
    return sorted(folder.rglob("*.xml"))


def scrape_gleif_download_urls() -> tuple[str, str]:
    """Scrape the GLEIF detail page to get the latest download URLs.
    
    Returns:
        Tuple of (lei_zip_url, rr_zip_url)
        
    Raises:
        RuntimeError: If URLs cannot be found on the page
    """
    html = requests.get(GLEIF_DETAIL_PAGE, headers=HTTP_HEADERS, timeout=HTML_FETCH_TIMEOUT).text
    soup = BeautifulSoup(html, "html.parser")

    # Extract Level 1 (LEI records) URL
    lei_zip_url = None
    for a in soup.select("a[href]"):
        href = a["href"]
        if "leidata.gleif.org/api/v1/concatenated-files/lei2/get" in href and href.endswith("/zip"):
            lei_zip_url = href
            break

    # Extract Level 2 Relationship Records URL
    rr_zip_url = None
    for a in soup.select("a[href]"):
        href = a["href"]
        if "leidata.gleif.org/api/v1/concatenated-files/rr/get" in href and href.endswith("/zip"):
            rr_zip_url = href
            break

    if not lei_zip_url or not rr_zip_url:
        raise RuntimeError("Could not find one or both download URLs on the GLEIF detail page. The page layout may have changed.")

    return lei_zip_url, rr_zip_url


def download_and_extract_gleif_data(downloads_dir: Path, lei_extract_dir: Path, rr_extract_dir: Path) -> tuple[Path, Path]:
    """Download and extract GLEIF Level 1 and Level 2 data.
    
    Args:
        downloads_dir: Directory to store downloaded ZIP files
        lei_extract_dir: Directory to extract Level 1 data
        rr_extract_dir: Directory to extract Level 2 data
        
    Returns:
        Tuple of (lei_csv_path, rr_csv_path)
    """
    downloads_dir.mkdir(parents=True, exist_ok=True)
    
    # Get latest URLs
    print("Scraping GLEIF detail page for latest download URLs...")
    lei_zip_url, rr_zip_url = scrape_gleif_download_urls()
    print(f"Latest Level 1 LEI ZIP URL: {lei_zip_url}")
    print(f"Latest Level 2 RR ZIP URL : {rr_zip_url}")

    # Download ZIPs
    lei_zip_path = downloads_dir / "gleif_level1_lei.zip"
    rr_zip_path = downloads_dir / "gleif_level2_rr.zip"

    print("\nDownloading Level 1 LEI ZIP...")
    download_file(lei_zip_url, lei_zip_path)

    print("Downloading Level 2 RR ZIP...")
    download_file(rr_zip_url, rr_zip_path)

    # Extract ZIPs
    # Try to find CSV first, then XML
    lei_files = find_csv_in_dir(lei_extract_dir) or find_xml_in_dir(lei_extract_dir)
    rr_files = find_csv_in_dir(rr_extract_dir) or find_xml_in_dir(rr_extract_dir)

    if not lei_files:
        raise RuntimeError("No CSV or XML found in Level 1 ZIP.")
    if not rr_files:
        raise RuntimeError("No CSV or XML found in Level 2 RR ZIP.")

    # Pick the largest file as the primary dataset
    lei_file = max(lei_files, key=lambda p: p.stat().st_size)
    rr_file = max(rr_files, key=lambda p: p.stat().st_size)

    file_type_lei = "XML" if str(lei_file).endswith(".xml") else "CSV"
    file_type_rr = "XML" if str(rr_file).endswith(".xml") else "CSV"

    print(f"\nUsing Level 1 {file_type_lei}: {lei_file}")
    print(f"Using Level 2 {file_type_rr}: {rr_file}")

    return lei_file, rr_file
