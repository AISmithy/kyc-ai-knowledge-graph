"""
Quick MVP test - bypasses download and tests normalization + persistence.
Uses simple ASCII output to avoid Windows console encoding issues.
"""

import sys
sys.path.insert(0, '/src')

import pandas as pd
from pathlib import Path
from data_loader.processors import load_and_normalize_lei_data, load_and_normalize_rr_data
from data_loader.normalization import LEIDataNormalizer, RelationshipDataNormalizer
from data_loader.persistence import ParquetPersistence

# Paths to existing extracted files
LEI_XML = Path("data/gleif_downloads/level1_lei/20260129-gleif-concatenated-file-lei2.xml")
RR_XML = Path("data/gleif_downloads/level2_rr/20260129-gleif-concatenated-file-rr.xml")

def test_mvp():
    """Test MVP pipeline with existing GLEIF data."""
    
    print("=" * 80)
    print("KYC Knowledge Graph MVP - Quick Test")
    print("=" * 80)
    
    # Load raw data (1000 records for quick test)
    print("\n[1] Loading raw data (1000 records)...")
    lei_raw = load_and_normalize_lei_data(LEI_XML, nrows=1000)
    rr_raw = load_and_normalize_rr_data(RR_XML, nrows=1000)
    print("  LEI records loaded: %d" % len(lei_raw))
    print("  RR records loaded: %d" % len(rr_raw))
    
    # Normalize LEI data
    print("\n[2] Normalizing LEI data...")
    lei_normalizer = LEIDataNormalizer()
    lei_df, lei_report = lei_normalizer.normalize_lei_data(lei_raw)
    print("  Valid LEI records: %d" % lei_report.report()['valid_records'])
    
    # Get valid LEIs for referential integrity
    valid_leis = set(lei_df["lei"].unique()) if "lei" in lei_df.columns else set()
    
    # Normalize RR data
    print("\n[3] Normalizing relationship data...")
    rr_normalizer = RelationshipDataNormalizer()
    rr_df, rr_report = rr_normalizer.normalize_relationship_data(rr_raw, valid_leis)
    print("  Valid RR records: %d" % rr_report.report()['valid_records'])
    
    # Persist to Parquet
    print("\n[4] Persisting to Parquet...")
    persistence = ParquetPersistence(output_dir="data/processed")
    lei_path = persistence.write_legal_entities(lei_df)
    rr_path = persistence.write_relationships(rr_df)
    print("  LEI file: %s" % lei_path)
    print("  RR file: %s" % rr_path)
    
    # Load into Neo4j
    print("\n[5] Loading into Neo4j...")
    try:
        from neo4j_module.connector import Neo4jConnection
        from neo4j_module.loader import Neo4jDataLoader
        
        neo4j_conn = Neo4jConnection()
        neo4j_conn.connect()  # Explicitly connect
        loader = Neo4jDataLoader(neo4j_conn)
        
        # Load entities
        if len(lei_df) > 0:
            le_counts = loader.load_legal_entities(lei_df, batch_size=500)
            print("  Legal Entities: %d created, %d updated" % (le_counts['created'], le_counts['updated']))
            
            # Load addresses
            addr_counts = loader.load_addresses(lei_df, batch_size=500)
            print("  Addresses: %d created, %d updated" % (addr_counts['created'], addr_counts['updated']))
            
            # Create LOCATED_AT relationships
            located_counts = loader.create_located_at_relationships(lei_df, batch_size=500)
            print("  LOCATED_AT edges: %d created" % located_counts['created'])
        
        # Load parent-child relationships
        if len(rr_df) > 0:
            rel_counts = loader.load_relationships(rr_df, batch_size=500)
            print("  PARENT_OF edges: %d created, %d updated" % (rel_counts['created'], rel_counts['updated']))
        else:
            print("  PARENT_OF edges: No valid relationships")
        
        # Get statistics
        print("\n[6] Neo4j Statistics...")
        session = neo4j_conn.get_session()
        if session:
            try:
                # Count legal entities
                result = session.run("MATCH (le:LegalEntity) RETURN count(le) AS count")
                rec = result.single()
                le_count = rec["count"] if rec else 0
                
                # Count addresses
                result = session.run("MATCH (addr:Address) RETURN count(addr) AS count")
                rec = result.single()
                addr_count = rec["count"] if rec else 0
                
                # Count PARENT_OF relationships
                result = session.run("MATCH ()-[r:PARENT_OF]->() RETURN count(r) AS count")
                rec = result.single()
                parent_of_count = rec["count"] if rec else 0
                
                # Count LOCATED_AT relationships
                result = session.run("MATCH ()-[r:LOCATED_AT]->() RETURN count(r) AS count")
                rec = result.single()
                located_at_count = rec["count"] if rec else 0
                
                print("  Legal Entities in graph: %d" % le_count)
                print("  Addresses in graph: %d" % addr_count)
                print("  PARENT_OF edges: %d" % parent_of_count)
                print("  LOCATED_AT edges: %d" % located_at_count)
            except Exception as e:
                print("  Error getting statistics: %s" % str(e))
            finally:
                session.close()
        
        neo4j_conn.close()
        
    except Exception as e:
        print("  Error: %s" % str(e))
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 80)
    print("MVP Test Complete!")
    print("=" * 80)

if __name__ == "__main__":
    test_mvp()
