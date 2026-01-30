"""Main entry point for GLEIF data loading pipeline."""

from .config import DOWNLOADS_DIR, LEI_EXTRACT_DIR, RR_EXTRACT_DIR
from .downloader import download_and_extract_gleif_data
from .processors import load_and_normalize_lei_data, load_and_normalize_rr_data, join_lei_and_relationships


def main():
    """Execute the complete GLEIF data loading pipeline."""
    print("=" * 80)
    print("GLEIF Data Loading Pipeline")
    print("=" * 80)

    # Step 1: Download and extract
    print("\n[Step 1/3] Downloading and extracting GLEIF data...")
    lei_csv, rr_csv = download_and_extract_gleif_data(DOWNLOADS_DIR, LEI_EXTRACT_DIR, RR_EXTRACT_DIR)

    # Step 2: Load and normalize Level 1 data
    print("\n[Step 2/3] Loading and normalizing Level 1 LEI data...")
    lei_df = load_and_normalize_lei_data(lei_csv)

    # Step 3: Load and normalize Level 2 data
    print("\n[Step 3/3] Loading and normalizing Level 2 relationship data...")
    rr_df = load_and_normalize_rr_data(rr_csv)

    # Step 4: Join data
    print("\n[Step 4/4] Joining LEI entities with relationships...")
    joined_df = join_lei_and_relationships(lei_df, rr_df)

    print("\n" + "=" * 80)
    print("Pipeline completed successfully!")
    print("=" * 80)
    
    return lei_df, rr_df, joined_df


if __name__ == "__main__":
    main()
