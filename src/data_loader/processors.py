"""Data loading and normalization for GLEIF datasets."""

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Iterator

import pandas as pd

from .config import LEI_PREVIEW_ROWS, RR_PREVIEW_ROWS


def load_large_csv(csv_path: Path, usecols=None, nrows=None, chunksize=None) -> pd.DataFrame:
    """Load a CSV file with appropriate settings for large files.
    
    Args:
        csv_path: Path to CSV file
        usecols: Columns to load (optional)
        nrows: Number of rows to load (optional)
        chunksize: Size of chunks to load (optional)
        
    Returns:
        DataFrame with loaded data
    """
    # dtype=str prevents pandas from guessing types and blowing memory on mixed columns
    return pd.read_csv(
        csv_path,
        dtype=str,
        usecols=usecols,
        nrows=nrows,
        chunksize=chunksize,
        low_memory=False,
    )


def first_existing(col_candidates: list[str], columns: list[str]) -> str | None:
    """Find the first existing column from a list of candidates.
    
    Args:
        col_candidates: List of column name candidates
        columns: List of actual columns in the dataframe
        
    Returns:
        First matching column name, or None if no match
    """
    for c in col_candidates:
        if c in columns:
            return c
    return None


def parse_xml_records(xml_file: Path, record_tag: str, nrows: int = None) -> Iterator[dict]:
    """Stream-parse XML file and yield records as dictionaries.
    
    Args:
        xml_file: Path to XML file
        record_tag: XML tag name for individual records (e.g., "LEIRecord")
        nrows: Maximum number of records to yield
        
    Yields:
        Dictionary representing each record
    """
    count = 0
    for event, elem in ET.iterparse(xml_file, events=['end']):
        # Check for both namespaced and non-namespaced tag names
        if record_tag in elem.tag or elem.tag.endswith(record_tag):
            if nrows and count >= nrows:
                elem.clear()
                break
            
            # Extract all text data from the element
            record = {}
            for child in elem.iter():
                # Get the local tag name without namespace
                tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
                
                if child.text and child.text.strip():
                    record[tag] = child.text.strip()
            
            if record:
                yield record
            
            elem.clear()
            count += 1


def load_and_normalize_lei_data(lei_file: Path, nrows: int = LEI_PREVIEW_ROWS) -> pd.DataFrame:
    """Load and normalize Level 1 LEI data.
    
    Args:
        lei_file: Path to LEI data file (CSV or XML)
        nrows: Number of rows to load
        
    Returns:
        Normalized DataFrame with columns: lei, legal_name, entity_status
    """
    file_size_gb = lei_file.stat().st_size / (1024 ** 3)
    print(f"Loading LEI data ({file_size_gb:.2f} GB)...")
    
    if str(lei_file).endswith(".xml"):
        # Stream XML data
        records = list(parse_xml_records(lei_file, "LEIRecord", nrows=nrows))
        lei_df = pd.DataFrame(records)
    else:
        lei_df = load_large_csv(lei_file, nrows=nrows)
    
    print(f"Loaded {len(lei_df)} LEI records")
    print(f"Level 1 columns: {list(lei_df.columns)[:25]}...")

    # Identify key columns
    lei_col = first_existing(["LEI", "lei", "LegalEntityIdentifier"], lei_df.columns)
    name_col = first_existing(
        ["LegalName", "EntityLegalName", "Entity.LegalName", "Entity_LegalName"],
        lei_df.columns
    )
    status_col = first_existing(
        ["EntityStatus", "Entity.EntityStatus", "Entity_Status"],
        lei_df.columns
    )

    if not lei_col:
        print(f"Available columns: {list(lei_df.columns)}")
        raise RuntimeError("Couldn't identify LEI column in Level 1 file.")

    # Keep only needed columns
    lei_keep = [c for c in [lei_col, name_col, status_col] if c]
    lei_small = lei_df[lei_keep].copy()

    # Rename to standard names
    rename_map = {lei_col: "lei"}
    if name_col:
        rename_map[name_col] = "legal_name"
    if status_col:
        rename_map[status_col] = "entity_status"
    
    lei_small.rename(columns=rename_map, inplace=True)

    print("\nSample LEI rows:")
    print(lei_small.head(5))

    return lei_small


def load_and_normalize_rr_data(rr_file: Path, nrows: int = RR_PREVIEW_ROWS) -> pd.DataFrame:
    """Load and normalize Level 2 Relationship Records data.
    
    Args:
        rr_file: Path to relationship records file (CSV or XML)
        nrows: Number of rows to load
        
    Returns:
        Normalized DataFrame with columns: child_lei, parent_lei, relationship_type, relationship_status
    """
    file_size_gb = rr_file.stat().st_size / (1024 ** 3)
    print(f"Loading Relationship Records ({file_size_gb:.2f} GB)...")
    
    if str(rr_file).endswith(".xml"):
        # Stream XML data
        records = list(parse_xml_records(rr_file, "RelationshipRecord", nrows=nrows))
        rr_df = pd.DataFrame(records)
    else:
        rr_df = load_large_csv(rr_file, nrows=nrows)
    
    print(f"Loaded {len(rr_df)} relationship records")
    print(f"Level 2 columns: {list(rr_df.columns)[:25]}...")

    # Identify key columns
    start_lei_col = first_existing(
        ["StartNodeID", "StartNode.NodeID", "StartNodeNodeID", "StartNode_ID"],
        rr_df.columns,
    )
    end_lei_col = first_existing(
        ["EndNodeID", "EndNode.NodeID", "EndNodeNodeID", "EndNode_ID"],
        rr_df.columns,
    )
    rel_type_col = first_existing(
        ["RelationshipType", "Relationship.RelationshipType", "Relationship_Type"],
        rr_df.columns,
    )
    rel_status_col = first_existing(
        ["RelationshipStatus", "RegistrationStatus", "Registration.RegistrationStatus", "Registration_Status"],
        rr_df.columns,
    )

    # If we don't have explicit start/end node columns, this might be a different RR format
    if not start_lei_col or not end_lei_col:
        print(f"\nWarning: Could not identify direct Start/End LEI columns.")
        print(f"This relationship file may have a different structure.")
        print(f"Available columns: {list(rr_df.columns)}")
        # Return empty dataframe to allow pipeline to continue
        return pd.DataFrame(columns=["child_lei", "parent_lei", "relationship_type", "relationship_status"])

    # Keep only needed columns
    rr_keep = [c for c in [start_lei_col, end_lei_col, rel_type_col, rel_status_col] if c]
    rr_small = rr_df[rr_keep].copy()

    # Rename to standard names
    rename_map = {
        start_lei_col: "child_lei",
        end_lei_col: "parent_lei",
    }
    if rel_type_col:
        rename_map[rel_type_col] = "relationship_type"
    if rel_status_col:
        rename_map[rel_status_col] = "relationship_status"
    
    rr_small.rename(columns=rename_map, inplace=True)

    print("\nSample relationship rows:")
    print(rr_small.head(5))

    return rr_small


def join_lei_and_relationships(lei_df: pd.DataFrame, rr_df: pd.DataFrame) -> pd.DataFrame:
    """Join LEI entities with their relationship records.
    
    Args:
        lei_df: Normalized LEI DataFrame
        rr_df: Normalized relationship records DataFrame
        
    Returns:
        Joined DataFrame with entity information and parent relationships
    """
    joined = lei_df.merge(rr_df, how="left", left_on="lei", right_on="child_lei")
    
    print("\nJoined sample (first 10 rows):")
    print(joined.head(10))

    return joined
