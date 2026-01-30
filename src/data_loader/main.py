"""Main entry point for GLEIF data loading pipeline."""

import logging
import sys
from .config import DOWNLOADS_DIR, LEI_EXTRACT_DIR, RR_EXTRACT_DIR
from .downloader import download_and_extract_gleif_data
from .processors import load_and_normalize_lei_data, load_and_normalize_rr_data
from .normalization import LEIDataNormalizer, RelationshipDataNormalizer
from .persistence import ParquetPersistence

# Optional Neo4j loading
try:
    from src.neo4j_module.connector import Neo4jConnection
    from src.neo4j_module.loader import Neo4jDataLoader
    NEO4J_AVAILABLE = True
except ImportError:
    NEO4J_AVAILABLE = False

logger = logging.getLogger(__name__)


def main(load_to_neo4j: bool = False, nrows: int = None):
    """
    Execute the complete GLEIF data loading pipeline.
    
    Args:
        load_to_neo4j: If True, load data into Neo4j graph
        nrows: Limit records to process (for testing); None = use default preview
    
    Returns:
        Tuple of (lei_df, rr_df, quality_reports)
    """
    print("=" * 80)
    print("KYC Knowledge Graph - GLEIF Data Loading Pipeline (MVP)")
    print("=" * 80)

    # Step 1: Download and extract
    print("\n[Step 1/5] Downloading and extracting GLEIF data...")
    lei_csv, rr_csv = download_and_extract_gleif_data(DOWNLOADS_DIR, LEI_EXTRACT_DIR, RR_EXTRACT_DIR)

    # Step 2: Load raw data
    print("\n[Step 2/5] Loading raw GLEIF data...")
    if nrows:
        lei_raw = load_and_normalize_lei_data(lei_csv, nrows=nrows)
        rr_raw = load_and_normalize_rr_data(rr_csv, nrows=nrows)
    else:
        lei_raw = load_and_normalize_lei_data(lei_csv)
        rr_raw = load_and_normalize_rr_data(rr_csv)

    # Step 3: Normalize and quality check
    print("\n[Step 3/5] Normalizing data and performing quality checks...")
    
    lei_normalizer = LEIDataNormalizer()
    lei_df, lei_report = lei_normalizer.normalize_lei_data(lei_raw)
    
    # Get valid LEIs for referential integrity
    valid_leis = set(lei_df["lei"].unique()) if "lei" in lei_df.columns else set()
    
    rr_normalizer = RelationshipDataNormalizer()
    rr_df, rr_report = rr_normalizer.normalize_relationship_data(rr_raw, valid_leis)
    
    print(f"\n  LEI Records:        {lei_report.report()['valid_records']} valid")
    print(f"  Relationship Recs:  {rr_report.report()['valid_records']} valid")
    
    # Step 4: Persist to Parquet
    print("\n[Step 4/5] Persisting normalized data to Parquet...")
    persistence = ParquetPersistence(output_dir="data/processed")
    
    lei_path = persistence.write_legal_entities(lei_df)
    rr_path = persistence.write_relationships(rr_df)
    
    # Save quality reports
    lei_report_path = persistence.write_quality_report(lei_report.report(), "full")
    rr_report_path = persistence.write_quality_report(rr_report.report(), "full")
    
    # Step 5: Load into Neo4j (optional)
    if load_to_neo4j:
        if not NEO4J_AVAILABLE:
            print("\n⚠ Neo4j modules not available; skipping graph load")
        else:
            print("\n[Step 5/5] Loading data into Neo4j Knowledge Graph...")
            try:
                neo4j_conn = Neo4jConnection()
                loader = Neo4jDataLoader(neo4j_conn)
                
                # Load entities
                le_counts = loader.load_legal_entities(lei_df, batch_size=500)
                print(f"  Legal Entities:     {le_counts['created']} created, {le_counts['updated']} updated")
                
                # Load addresses
                addr_counts = loader.load_addresses(lei_df, batch_size=500)
                print(f"  Addresses:          {addr_counts['created']} created, {addr_counts['updated']} updated")
                
                # Create LOCATED_AT relationships
                located_counts = loader.create_located_at_relationships(lei_df, batch_size=500)
                print(f"  LOCATED_AT rels:    {located_counts['created']} created")
                
                # Load parent-child relationships
                if len(rr_df) > 0:
                    rel_counts = loader.load_relationships(rr_df, batch_size=500)
                    print(f"  PARENT_OF rels:     {rel_counts['created']} created, {rel_counts['updated']} updated")
                else:
                    print(f"  PARENT_OF rels:     No valid relationships to load")
                
                neo4j_conn.close()
                
            except Exception as e:
                logger.error(f"Failed to load into Neo4j: {e}")
                print(f"\n✗ Neo4j loading failed: {e}")
    else:
        print("\n[Step 5/5] Skipping Neo4j load (use --neo4j flag to enable)")

    print("\n" + "=" * 80)
    print("Pipeline completed successfully!")
    print(f"  Output: {persistence.output_dir}/")
    print("=" * 80)
    
    return lei_df, rr_df, (lei_report.report(), rr_report.report())


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Parse command line args
    load_neo4j = "--neo4j" in sys.argv
    nrows = None
    if "--nrows" in sys.argv:
        idx = sys.argv.index("--nrows")
        if idx + 1 < len(sys.argv):
            nrows = int(sys.argv[idx + 1])
    
    lei_df, rr_df, reports = main(load_to_neo4j=load_neo4j, nrows=nrows)
