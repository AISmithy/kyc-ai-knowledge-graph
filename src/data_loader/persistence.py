"""
Parquet persistence layer for processed data.

Handles writing normalized data to Parquet format for:
- Storage efficiency (columnar compression)
- Fast retrieval (read specific columns)
- Cross-platform interoperability
- Version control (timestamp each export)
"""

import os
import pandas as pd
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class ParquetPersistence:
    """Manage Parquet file I/O for KYC data."""
    
    def __init__(self, output_dir: str = "data/processed"):
        """
        Initialize persistence layer.
        
        Args:
            output_dir: Directory to store Parquet files
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Parquet output directory: {self.output_dir.absolute()}")
        
    def write_legal_entities(
        self,
        df: pd.DataFrame,
        version: Optional[str] = None
    ) -> str:
        """
        Write normalized legal entity data to Parquet.
        
        Args:
            df: Normalized LegalEntity DataFrame
            version: Optional version string; defaults to timestamp
            
        Returns:
            Path to written file
        """
        if version is None:
            version = datetime.now().strftime("%Y%m%d_%H%M%S")
            
        filename = self.output_dir / f"legal_entities_{version}.parquet"
        
        # Ensure LEI is unique
        if "lei" in df.columns:
            duplicates = df[df.duplicated(subset=["lei"], keep=False)]
            if len(duplicates) > 0:
                logger.warning(
                    f"Found {len(duplicates)} duplicate LEIs; keeping first occurrence"
                )
                df = df.drop_duplicates(subset=["lei"], keep="first")
                
        df.to_parquet(
            filename,
            engine="pyarrow",
            compression="snappy",
            index=False,
            coerce_timestamps="us"
        )
        
        file_size_mb = filename.stat().st_size / (1024 * 1024)
        logger.info(
            f"Wrote {len(df)} legal entities to {filename.name} ({file_size_mb:.2f} MB)"
        )
        return str(filename)
        
    def write_relationships(
        self,
        df: pd.DataFrame,
        version: Optional[str] = None
    ) -> str:
        """
        Write normalized relationship data to Parquet.
        
        Args:
            df: Normalized relationships DataFrame
            version: Optional version string; defaults to timestamp
            
        Returns:
            Path to written file
        """
        if version is None:
            version = datetime.now().strftime("%Y%m%d_%H%M%S")
            
        filename = self.output_dir / f"relationships_{version}.parquet"
        
        # Ensure relationship uniqueness
        if all(col in df.columns for col in ["childLei", "parentLei"]):
            duplicates = df[df.duplicated(subset=["childLei", "parentLei"], keep=False)]
            if len(duplicates) > 0:
                logger.warning(
                    f"Found {len(duplicates)} duplicate relationships; keeping first occurrence"
                )
                df = df.drop_duplicates(subset=["childLei", "parentLei"], keep="first")
                
        df.to_parquet(
            filename,
            engine="pyarrow",
            compression="snappy",
            index=False,
            coerce_timestamps="us"
        )
        
        file_size_mb = filename.stat().st_size / (1024 * 1024)
        logger.info(
            f"Wrote {len(df)} relationships to {filename.name} ({file_size_mb:.2f} MB)"
        )
        return str(filename)
        
    def write_quality_report(
        self,
        report_dict: dict,
        report_type: str = "full",
        version: Optional[str] = None
    ) -> str:
        """
        Write data quality report.
        
        Args:
            report_dict: Quality report dictionary
            report_type: "full" for detailed, "summary" for brief
            version: Optional version string
            
        Returns:
            Path to written file
        """
        if version is None:
            version = datetime.now().strftime("%Y%m%d_%H%M%S")
            
        filename = self.output_dir / f"quality_report_{version}.json"
        
        import json
        with open(filename, "w") as f:
            json.dump(report_dict, f, indent=2, default=str)
            
        logger.info(f"Wrote quality report to {filename.name}")
        return str(filename)
        
    def read_legal_entities(self, version: str = "latest") -> pd.DataFrame:
        """
        Read legal entities from Parquet.
        
        Args:
            version: Version string or "latest"
            
        Returns:
            DataFrame of legal entities
        """
        if version == "latest":
            files = sorted(self.output_dir.glob("legal_entities_*.parquet"))
            if not files:
                raise FileNotFoundError("No legal entities Parquet files found")
            filename = files[-1]
        else:
            filename = self.output_dir / f"legal_entities_{version}.parquet"
            
        if not filename.exists():
            raise FileNotFoundError(f"File not found: {filename}")
            
        df = pd.read_parquet(filename)
        logger.info(f"Read {len(df)} legal entities from {filename.name}")
        return df
        
    def read_relationships(self, version: str = "latest") -> pd.DataFrame:
        """
        Read relationships from Parquet.
        
        Args:
            version: Version string or "latest"
            
        Returns:
            DataFrame of relationships
        """
        if version == "latest":
            files = sorted(self.output_dir.glob("relationships_*.parquet"))
            if not files:
                raise FileNotFoundError("No relationships Parquet files found")
            filename = files[-1]
        else:
            filename = self.output_dir / f"relationships_{version}.parquet"
            
        if not filename.exists():
            raise FileNotFoundError(f"File not found: {filename}")
            
        df = pd.read_parquet(filename)
        logger.info(f"Read {len(df)} relationships from {filename.name}")
        return df
        
    def list_versions(self) -> dict:
        """List available Parquet versions."""
        versions = {
            "legal_entities": sorted([
                f.stem.replace("legal_entities_", "")
                for f in self.output_dir.glob("legal_entities_*.parquet")
            ]),
            "relationships": sorted([
                f.stem.replace("relationships_", "")
                for f in self.output_dir.glob("relationships_*.parquet")
            ])
        }
        return versions
        
    def export_to_csv(
        self,
        data_type: str,
        version: str = "latest",
        output_path: Optional[str] = None
    ) -> str:
        """
        Export Parquet to CSV for interoperability.
        
        Args:
            data_type: "legal_entities" or "relationships"
            version: Version string or "latest"
            output_path: Optional custom output path
            
        Returns:
            Path to CSV file
        """
        if data_type == "legal_entities":
            df = self.read_legal_entities(version)
            default_name = f"legal_entities_{version}.csv"
        elif data_type == "relationships":
            df = self.read_relationships(version)
            default_name = f"relationships_{version}.csv"
        else:
            raise ValueError(f"Unknown data_type: {data_type}")
            
        if output_path is None:
            output_path = self.output_dir / default_name
        else:
            output_path = Path(output_path)
            
        df.to_csv(output_path, index=False)
        file_size_mb = output_path.stat().st_size / (1024 * 1024)
        logger.info(f"Exported {len(df)} records to {output_path.name} ({file_size_mb:.2f} MB)")
        return str(output_path)
