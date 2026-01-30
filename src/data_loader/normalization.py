"""
Normalization and quality checks for GLEIF data.

Handles:
- Column mapping (GLEIF schema → KYC schema)
- Data type conversion and validation
- Referential integrity checks (parent/child relationships)
- Duplicate detection
- Null/missing value analysis
"""

import pandas as pd
import logging
from typing import Tuple, Dict, List, Set
from datetime import datetime
import hashlib

logger = logging.getLogger(__name__)


class DataQualityReport:
    """Tracks data quality metrics during normalization."""
    
    def __init__(self):
        self.total_records = 0
        self.valid_records = 0
        self.invalid_records = 0
        self.warnings = []
        self.errors = []
        self.nulls_by_column = {}
        self.duplicates = 0
        self.referential_integrity_issues = 0
        
    def add_warning(self, warning: str):
        self.warnings.append(warning)
        
    def add_error(self, error: str):
        self.errors.append(error)
        
    def report(self) -> Dict:
        return {
            "total_records": self.total_records,
            "valid_records": self.valid_records,
            "invalid_records": self.invalid_records,
            "duplicate_count": self.duplicates,
            "referential_integrity_issues": self.referential_integrity_issues,
            "nulls_by_column": self.nulls_by_column,
            "warnings": len(self.warnings),
            "errors": len(self.errors),
            "validity_rate": round(self.valid_records / max(self.total_records, 1) * 100, 2)
        }


class LEIDataNormalizer:
    """Normalize Level 1 LEI records to KYC schema."""
    
    # GLEIF → KYC column mapping
    # Maps potential GLEIF column names to standardized KYC schema columns
    COLUMN_MAPPING = {
        # LEI and basic identifiers
        "LEI": "lei",
        "LegalName": "legalName",
        "Entity.LegalName": "legalName",
        "PreviousName": "previousName",
        "Entity.PreviousName": "previousName",
        
        # Legal form
        "EntityLegalFormCode": "legalFormCode",
        "LegalFormCode": "legalFormCode",
        "Entity.LegalForm.EntityLegalFormCode": "legalFormCode",
        "OtherLegalForm": "legalFormText",
        "Entity.LegalForm.OtherLegalForm": "legalFormText",
        
        # Status and category
        "EntityStatus": "entityStatus",
        "Entity.Status": "entityStatus",
        "EntityCategory": "entityCategory",
        "Entity.EntityCategory": "entityCategory",
        "RegistrationStatus": "registrationStatus",
        "Entity.RegistrationStatus": "registrationStatus",
        
        # Jurisdiction and location
        "LegalJurisdiction": "jurisdiction",
        "Entity.CountryOfIncorporation": "countryOfIncorporation",
        "Entity.CountryOfLatestArrival": "countryOfLatestArrival",
        
        # Address
        "FirstAddressLine": "addressLine1",
        "AdditionalAddressLine": "addressLine2",
        "City": "city",
        "Region": "region",
        "PostalCode": "postalCode",
        "Country": "country",
        
        # Authority and management
        "RegistrationAuthorityID": "registrationAuthorityId",
        "RegistrationAuthorityEntityID": "registrationAuthorityEntityId",
        "ManagingLOU": "managingLou",
        "ValidationAuthorityID": "validationAuthorityId",
        "ValidationAuthorityEntityID": "validationAuthorityEntityId",
        
        # Dates
        "LastUpdateDate": "latestUpdateDate",
        "LatestUpdateDate": "latestUpdateDate",
        "EntityCreationDate": "registrationDate",
        "InitialRegistrationDate": "registrationDate",
        "RegistrationDate": "registrationDate",
        "NextRenewalDate": "nextRenewalDate",
    }
    
    # Valid values for entity status
    VALID_ENTITY_STATUS = {
        "ACTIVE", "INACTIVE", "MERGED", "OBSOLETE", "PENDING_ARCHIVAL"
    }
    
    def __init__(self):
        self.report = DataQualityReport()
        
    def normalize_lei_data(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, DataQualityReport]:
        """
        Normalize Level 1 LEI data.
        
        Args:
            df: Raw GLEIF Level 1 DataFrame
            
        Returns:
            Tuple of (normalized_df, quality_report)
        """
        logger.info(f"Normalizing {len(df)} LEI records")
        self.report.total_records = len(df)
        
        # Step 1: Map columns
        df = self._map_columns(df)
        
        # Step 2: Type conversion
        df = self._convert_types(df)
        
        # Step 3: Validate required fields
        df = self._validate_required_fields(df)
        
        # Step 4: Standardize values
        df = self._standardize_values(df)
        
        # Step 5: Detect duplicates
        self._detect_duplicates(df)
        
        # Step 6: Generate entity IDs
        df = self._generate_entity_ids(df)
        
        # Final count
        self.report.valid_records = len(df)
        self.report.invalid_records = self.report.total_records - self.report.valid_records
        
        logger.info(f"Normalization complete: {self.report.valid_records}/{self.report.total_records} valid")
        return df, self.report
        
    def _map_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Map GLEIF columns to KYC schema columns."""
        # Rename available columns
        rename_map = {}
        for old_col, new_col in self.COLUMN_MAPPING.items():
            if old_col in df.columns and new_col not in df.columns:
                rename_map[old_col] = new_col
        
        # Also handle pre-mapped columns from processors (lei, legal_name, entity_status)
        simple_mapping = {
            "lei": "lei",
            "legal_name": "legalName",
            "entity_status": "entityStatus",
            "child_lei": "childLei",
            "parent_lei": "parentLei",
            "relationship_type": "relationshipType",
            "relationship_status": "relationshipStatus",
        }
        
        for simple_col, mapped_col in simple_mapping.items():
            if simple_col in df.columns and mapped_col not in df.columns:
                rename_map[simple_col] = mapped_col
        
        df = df.rename(columns=rename_map)
        
        # Add missing columns as null
        for old_col, new_col in self.COLUMN_MAPPING.items():
            if new_col not in df.columns:
                df[new_col] = None
        
        # Keep only mapped columns (exclude unmapped GLEIF columns)
        mapped_cols = list(self.COLUMN_MAPPING.values())
        # Add simple mapped columns
        mapped_cols.extend(simple_mapping.values())
        df = df[[col for col in df.columns if col in mapped_cols]]
        
        logger.debug(f"Mapped {len(rename_map)} columns")
        return df
        
    def _convert_types(self, df: pd.DataFrame) -> pd.DataFrame:
        """Convert data types to proper formats."""
        # LEI must be string
        if "lei" in df.columns:
            df["lei"] = df["lei"].astype(str).str.strip()
            
        # Dates to datetime
        date_cols = ["latestUpdateDate", "registrationDate", "nextRenewalDate"]
        for col in date_cols:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce")
                
        # Status enum
        if "entityStatus" in df.columns:
            df["entityStatus"] = df["entityStatus"].astype(str).str.upper()
            
        # String columns
        string_cols = ["legalName", "city", "country", "addressLine1", "postalCode"]
        for col in string_cols:
            if col in df.columns:
                df[col] = df[col].astype(str).fillna("").str.strip()
                
        return df
        
    def _validate_required_fields(self, df: pd.DataFrame) -> pd.DataFrame:
        """Remove records with missing required fields."""
        # For MVP: only LEI and legalName are strictly required
        # Country/address data can come from extended attributes if available
        required = ["lei", "legalName"]
        initial_count = len(df)
        
        for col in required:
            if col in df.columns:
                mask = df[col].notna() & (df[col] != "")
                removed = (~mask).sum()
                if removed > 0:
                    self.report.add_warning(f"Removed {removed} records with null {col}")
                df = df[mask]
                
        logger.info(f"Removed {initial_count - len(df)} records with missing required fields")
        return df
        
    def _standardize_values(self, df: pd.DataFrame) -> pd.DataFrame:
        """Standardize entity status and other enumerations."""
        if "entityStatus" in df.columns:
            # Map unknown statuses to ACTIVE
            mask = ~df["entityStatus"].isin(self.VALID_ENTITY_STATUS)
            unknown_count = mask.sum()
            if unknown_count > 0:
                self.report.add_warning(
                    f"Found {unknown_count} records with unknown entityStatus; defaulting to ACTIVE"
                )
                df.loc[mask, "entityStatus"] = "ACTIVE"
                
        return df
        
    def _detect_duplicates(self, df: pd.DataFrame) -> None:
        """Detect duplicate LEIs."""
        if "lei" in df.columns:
            duplicates = df[df.duplicated(subset=["lei"], keep=False)]
            self.report.duplicates = len(duplicates)
            if self.report.duplicates > 0:
                self.report.add_warning(f"Found {self.report.duplicates} duplicate LEI records")
                logger.warning(f"Duplicate LEIs: {duplicates['lei'].unique().tolist()[:10]}...")
                
    def _generate_entity_ids(self, df: pd.DataFrame) -> pd.DataFrame:
        """Generate internal entity IDs."""
        df["entity_id"] = df["lei"].apply(
            lambda lei: hashlib.md5(lei.encode()).hexdigest()[:16]
        )
        return df
        
    def get_null_analysis(self, df: pd.DataFrame) -> Dict[str, float]:
        """Analyze null values as percentage."""
        nulls = {}
        for col in df.columns:
            null_pct = (df[col].isna().sum() / len(df) * 100)
            if null_pct > 0:
                nulls[col] = round(null_pct, 2)
        return nulls


class RelationshipDataNormalizer:
    """Normalize Level 2 Relationship Records to KYC schema."""
    
    # GLEIF RR → KYC schema mapping
    COLUMN_MAPPING = {
        "RelationshipRecordID": "relationshipId",
        "ChildLEI": "childLei",
        "ParentLEI": "parentLei",
        "RelationshipStartDate": "relationshipStartDate",
        "RelationshipEndDate": "relationshipEndDate",
        "RelationshipType": "relationshipType",
        "RelationshipStatus": "relationshipStatus",
        "PercentageOwnership": "ownershipPercentage",
    }
    
    VALID_RELATIONSHIP_STATUS = {
        "ACTIVE", "INACTIVE", "OBSOLETE"
    }
    
    def __init__(self):
        self.report = DataQualityReport()
        
    def normalize_relationship_data(
        self, 
        df: pd.DataFrame,
        valid_leis: Set[str]
    ) -> Tuple[pd.DataFrame, DataQualityReport]:
        """
        Normalize Level 2 Relationship Records.
        
        Args:
            df: Raw GLEIF Level 2 DataFrame
            valid_leis: Set of valid LEIs from Level 1 (for referential integrity)
            
        Returns:
            Tuple of (normalized_df, quality_report)
        """
        logger.info(f"Normalizing {len(df)} relationship records")
        self.report.total_records = len(df)
        
        # Step 1: Map columns
        df = self._map_columns(df)
        
        # Step 2: Type conversion
        df = self._convert_types(df)
        
        # Step 3: Validate required fields
        df = self._validate_required_fields(df)
        
        # Step 4: Check referential integrity
        df = self._check_referential_integrity(df, valid_leis)
        
        # Step 5: Standardize values
        df = self._standardize_values(df)
        
        # Step 6: Detect duplicates
        self._detect_duplicates(df)
        
        self.report.valid_records = len(df)
        self.report.invalid_records = self.report.total_records - self.report.valid_records
        
        logger.info(f"Normalization complete: {self.report.valid_records}/{self.report.total_records} valid")
        return df, self.report
        
    def _map_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Map GLEIF RR columns to KYC schema columns."""
        rename_map = {}
        for old_col, new_col in self.COLUMN_MAPPING.items():
            if old_col in df.columns and new_col not in df.columns:
                rename_map[old_col] = new_col
        
        # Handle pre-mapped columns from processors
        simple_mapping = {
            "child_lei": "childLei",
            "parent_lei": "parentLei",
            "relationship_type": "relationshipType",
            "relationship_status": "relationshipStatus",
        }
        
        for simple_col, mapped_col in simple_mapping.items():
            if simple_col in df.columns and mapped_col not in df.columns:
                rename_map[simple_col] = mapped_col
        
        df = df.rename(columns=rename_map)
        
        for old_col, new_col in self.COLUMN_MAPPING.items():
            if new_col not in df.columns:
                df[new_col] = None
                
        mapped_cols = list(self.COLUMN_MAPPING.values())
        mapped_cols.extend(simple_mapping.values())
        df = df[[col for col in df.columns if col in mapped_cols]]
        return df
        
    def _convert_types(self, df: pd.DataFrame) -> pd.DataFrame:
        """Convert data types."""
        # LEIs to string
        for col in ["childLei", "parentLei"]:
            if col in df.columns:
                df[col] = df[col].astype(str).str.strip().str.upper()
                
        # Dates
        date_cols = ["relationshipStartDate", "relationshipEndDate"]
        for col in date_cols:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce")
                
        # Status
        if "relationshipStatus" in df.columns:
            df["relationshipStatus"] = df["relationshipStatus"].astype(str).str.upper()
            
        # Ownership percentage (numeric, 0-100)
        if "ownershipPercentage" in df.columns:
            df["ownershipPercentage"] = pd.to_numeric(
                df["ownershipPercentage"], 
                errors="coerce"
            ).clip(0, 100)
            
        return df
        
    def _validate_required_fields(self, df: pd.DataFrame) -> pd.DataFrame:
        """Remove records with missing required fields."""
        # For MVP: childLei and parentLei are required, relationshipType is optional
        required = ["childLei", "parentLei"]
        initial_count = len(df)
        
        for col in required:
            if col in df.columns:
                mask = df[col].notna() & (df[col] != "")
                removed = (~mask).sum()
                if removed > 0:
                    self.report.add_warning(f"Removed {removed} records with null {col}")
                df = df[mask]
                
        return df
        
    def _check_referential_integrity(
        self, 
        df: pd.DataFrame,
        valid_leis: Set[str]
    ) -> pd.DataFrame:
        """Verify child and parent LEIs exist in valid_leis."""
        initial_count = len(df)
        
        # Check child LEI
        if "childLei" in df.columns:
            invalid_child = ~df["childLei"].isin(valid_leis)
            if invalid_child.sum() > 0:
                self.report.referential_integrity_issues += invalid_child.sum()
                self.report.add_warning(
                    f"{invalid_child.sum()} relationships with invalid childLei"
                )
                df = df[~invalid_child]
                
        # Check parent LEI
        if "parentLei" in df.columns:
            invalid_parent = ~df["parentLei"].isin(valid_leis)
            if invalid_parent.sum() > 0:
                self.report.referential_integrity_issues += invalid_parent.sum()
                self.report.add_warning(
                    f"{invalid_parent.sum()} relationships with invalid parentLei"
                )
                df = df[~invalid_parent]
                
        logger.info(f"Removed {initial_count - len(df)} records due to referential integrity issues")
        return df
        
    def _standardize_values(self, df: pd.DataFrame) -> pd.DataFrame:
        """Standardize relationship status."""
        if "relationshipStatus" in df.columns:
            mask = ~df["relationshipStatus"].isin(self.VALID_RELATIONSHIP_STATUS)
            if mask.sum() > 0:
                self.report.add_warning(
                    f"Found {mask.sum()} records with unknown relationshipStatus"
                )
                df.loc[mask, "relationshipStatus"] = "ACTIVE"
                
        return df
        
    def _detect_duplicates(self, df: pd.DataFrame) -> None:
        """Detect duplicate relationships."""
        if all(col in df.columns for col in ["childLei", "parentLei"]):
            duplicates = df[df.duplicated(subset=["childLei", "parentLei"], keep=False)]
            self.report.duplicates = len(duplicates)
            if self.report.duplicates > 0:
                self.report.add_warning(
                    f"Found {self.report.duplicates} duplicate relationships"
                )
