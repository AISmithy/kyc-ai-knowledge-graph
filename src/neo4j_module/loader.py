"""
Neo4j data loader for KYC Knowledge Graph.

Handles:
- Creating :LegalEntity nodes
- Creating :Address nodes
- Creating :PARENT_OF relationships (ownership hierarchy)
- Batch insertion with error handling
- Constraint enforcement
"""

import pandas as pd
import logging
from typing import Dict, List, Tuple, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class Neo4jDataLoader:
    """Load normalized GLEIF data into Neo4j graph."""
    
    def __init__(self, connection):
        """
        Initialize loader with Neo4j connection.
        
        Args:
            connection: Neo4jConnection instance
        """
        self.conn = connection
        
    def load_legal_entities(
        self,
        df: pd.DataFrame,
        batch_size: int = 500
    ) -> Dict[str, int]:
        """
        Load legal entities as :LegalEntity nodes.
        
        Args:
            df: Normalized LegalEntity DataFrame
            batch_size: Records per transaction
            
        Returns:
            Dict with counts: {created, updated, failed}
        """
        logger.info(f"Loading {len(df)} legal entities into Neo4j")
        
        counts = {"created": 0, "updated": 0, "failed": 0}
        
        # Prepare records
        records = df.to_dict(orient="records")
        
        # Process in batches
        for i in range(0, len(records), batch_size):
            batch = records[i:i+batch_size]
            try:
                batch_counts = self._create_legal_entity_batch(batch)
                counts["created"] += batch_counts["created"]
                counts["updated"] += batch_counts["updated"]
            except Exception as e:
                logger.error(f"Failed to load batch {i//batch_size}: {e}")
                counts["failed"] += len(batch)
                
        logger.info(
            f"Legal entity load complete: {counts['created']} created, "
            f"{counts['updated']} updated, {counts['failed']} failed"
        )
        return counts
        
    def _create_legal_entity_batch(self, records: List[Dict]) -> Dict[str, int]:
        """
        Create legal entity nodes in a single transaction.
        
        Args:
            records: List of normalized legal entity records
            
        Returns:
            Dict with {created, updated} counts
        """
        cypher = """
        UNWIND $records AS rec
        MERGE (le:LegalEntity {lei: rec.lei})
        ON CREATE SET
          le.entity_id = rec.entity_id,
          le.legalName = rec.legalName,
          le.previousName = rec.previousName,
          le.legalFormCode = rec.legalFormCode,
          le.legalFormText = rec.legalFormText,
          le.entityStatus = rec.entityStatus,
          le.entityCategory = rec.entityCategory,
          le.registrationStatus = rec.registrationStatus,
          le.countryOfIncorporation = rec.countryOfIncorporation,
          le.countryOfLatestArrival = rec.countryOfLatestArrival,
          le.registrationAuthorityId = rec.registrationAuthorityId,
          le.registrationAuthorityEntityId = rec.registrationAuthorityEntityId,
          le.managingLou = rec.managingLou,
          le.validationAuthorityId = rec.validationAuthorityId,
          le.registrationDate = rec.registrationDate,
          le.latestUpdateDate = rec.latestUpdateDate,
          le.nextRenewalDate = rec.nextRenewalDate,
          le.createdAt = datetime(),
          le.beneficialOwnerKnown = false
        ON MATCH SET
          le.legalName = rec.legalName,
          le.entityStatus = rec.entityStatus,
          le.latestUpdateDate = rec.latestUpdateDate,
          le.updatedAt = datetime()
        WITH le
        MATCH (le) RETURN count(*) AS count
        """
        
        try:
            with self.conn.get_session() as session:
                result = session.run(cypher, records=records)
                data = result.single()
                # Simple count since MERGE doesn't give us created vs updated easily
                return {
                    "created": len(records) if data else 0,
                    "updated": 0
                }
        except Exception as e:
            logger.error(f"Batch creation error: {str(e)[:100]}")
            return {"created": 0, "updated": 0}
            
    def load_addresses(
        self,
        df: pd.DataFrame,
        batch_size: int = 500
    ) -> Dict[str, int]:
        """
        Load addresses as :Address nodes.
        
        Args:
            df: DataFrame with address columns (from legal entities)
            batch_size: Records per transaction
            
        Returns:
            Dict with counts: {created, updated, failed}
        """
        logger.info(f"Loading addresses from {len(df)} legal entities")
        
        # Extract unique addresses
        address_cols = ["addressLine1", "addressLine2", "city", "postalCode", "country"]
        available_cols = [col for col in address_cols if col in df.columns]
        
        addresses = df[["lei"] + available_cols].drop_duplicates(
            subset=available_cols
        ).dropna(subset=["country"])
        
        if len(addresses) == 0:
            logger.warning("No valid addresses found")
            return {"created": 0, "updated": 0, "failed": 0}
            
        logger.info(f"Found {len(addresses)} unique addresses")
        
        counts = {"created": 0, "updated": 0, "failed": 0}
        records = addresses.to_dict(orient="records")
        
        for i in range(0, len(records), batch_size):
            batch = records[i:i+batch_size]
            try:
                batch_counts = self._create_address_batch(batch)
                counts["created"] += batch_counts["created"]
                counts["updated"] += batch_counts["updated"]
            except Exception as e:
                logger.error(f"Failed to load address batch {i//batch_size}: {e}")
                counts["failed"] += len(batch)
                
        logger.info(
            f"Address load complete: {counts['created']} created, "
            f"{counts['updated']} updated, {counts['failed']} failed"
        )
        return counts
        
    def _create_address_batch(self, records: List[Dict]) -> Dict[str, int]:
        """Create address nodes in a single transaction."""
        # Filter out records without country
        valid_records = [r for r in records if r.get('country')]
        if not valid_records:
            return {"created": 0, "updated": 0}
            
        cypher = """
        UNWIND $records AS rec
        MERGE (addr:Address {
          line1: coalesce(rec.addressLine1, ''),
          line2: coalesce(rec.addressLine2, ''),
          city: coalesce(rec.city, ''),
          postalCode: coalesce(rec.postalCode, ''),
          country: rec.country
        })
        ON CREATE SET addr.createdAt = datetime()
        RETURN count(*) AS count
        """
        
        try:
            with self.conn.get_session() as session:
                result = session.run(cypher, records=valid_records)
                data = result.single()
                return {
                    "created": data["count"] if data else 0,
                    "updated": 0
                }
        except Exception as e:
            logger.error(f"Address batch creation error: {str(e)[:100]}")
            return {"created": 0, "updated": 0}
            
    def create_located_at_relationships(
        self,
        df: pd.DataFrame,
        batch_size: int = 500
    ) -> Dict[str, int]:
        """
        Create LOCATED_AT relationships between entities and addresses.
        
        Args:
            df: Legal entities DataFrame with address columns
            batch_size: Records per transaction
            
        Returns:
            Dict with counts: {created, updated, failed}
        """
        logger.info(f"Creating LOCATED_AT relationships for {len(df)} entities")
        
        counts = {"created": 0, "updated": 0, "failed": 0}
        records = df[["lei", "addressLine1", "addressLine2", "city", "postalCode", "country"]].to_dict(
            orient="records"
        )
        
        for i in range(0, len(records), batch_size):
            batch = records[i:i+batch_size]
            try:
                batch_counts = self._create_located_at_batch(batch)
                counts["created"] += batch_counts["created"]
                counts["updated"] += batch_counts["updated"]
            except Exception as e:
                logger.error(f"Failed to create LOCATED_AT batch {i//batch_size}: {e}")
                counts["failed"] += len(batch)
                
        logger.info(
            f"LOCATED_AT relationships complete: {counts['created']} created, "
            f"{counts['updated']} updated, {counts['failed']} failed"
        )
        return counts
        
    def _create_located_at_batch(self, records: List[Dict]) -> Dict[str, int]:
        """Create LOCATED_AT relationships in a single transaction."""
        # Filter records with valid country
        valid_records = [r for r in records if r.get('country')]
        if not valid_records:
            return {"created": 0, "updated": 0}
            
        cypher = """
        UNWIND $records AS rec
        MATCH (le:LegalEntity {lei: rec.lei})
        MERGE (addr:Address {
          line1: coalesce(rec.addressLine1, ''),
          line2: coalesce(rec.addressLine2, ''),
          city: coalesce(rec.city, ''),
          postalCode: coalesce(rec.postalCode, ''),
          country: rec.country
        })
        MERGE (le)-[rel:LOCATED_AT]->(addr)
        ON CREATE SET
          rel.isPrimary = true,
          rel.createdAt = datetime()
        RETURN count(rel) AS count
        """
        
        try:
            with self.conn.get_session() as session:
                result = session.run(cypher, records=valid_records)
                data = result.single()
                return {
                    "created": data["count"] if data else 0,
                    "updated": 0
                }
        except Exception as e:
            logger.error(f"LOCATED_AT batch error: {str(e)[:100]}")
            return {"created": 0, "updated": 0}
            
    def load_relationships(
        self,
        df: pd.DataFrame,
        batch_size: int = 500
    ) -> Dict[str, int]:
        """
        Load parent-child relationships as PARENT_OF edges.
        
        Args:
            df: Normalized relationships DataFrame
            batch_size: Records per transaction
            
        Returns:
            Dict with counts: {created, updated, failed}
        """
        logger.info(f"Loading {len(df)} relationships (PARENT_OF edges)")
        
        counts = {"created": 0, "updated": 0, "failed": 0}
        records = df.to_dict(orient="records")
        
        for i in range(0, len(records), batch_size):
            batch = records[i:i+batch_size]
            try:
                batch_counts = self._create_relationship_batch(batch)
                counts["created"] += batch_counts["created"]
                counts["updated"] += batch_counts["updated"]
            except Exception as e:
                logger.error(f"Failed to load relationship batch {i//batch_size}: {e}")
                counts["failed"] += len(batch)
                
        logger.info(
            f"Relationship load complete: {counts['created']} created, "
            f"{counts['updated']} updated, {counts['failed']} failed"
        )
        return counts
        
    def _create_relationship_batch(self, records: List[Dict]) -> Dict[str, int]:
        """Create PARENT_OF relationships in a single transaction."""
        cypher = """
        UNWIND $records AS rec
        MATCH (parent:LegalEntity {lei: rec.parentLei})
        MATCH (child:LegalEntity {lei: rec.childLei})
        MERGE (parent)-[rel:PARENT_OF]->(child)
        ON CREATE SET
          rel.relationshipId = rec.relationshipId,
          rel.relationshipType = rec.relationshipType,
          rel.relationshipStatus = rec.relationshipStatus,
          rel.ownershipPercentage = rec.ownershipPercentage,
          rel.relationshipStartDate = rec.relationshipStartDate,
          rel.relationshipEndDate = rec.relationshipEndDate,
          rel.createdAt = datetime()
        ON MATCH SET
          rel.relationshipStatus = rec.relationshipStatus,
          rel.ownershipPercentage = rec.ownershipPercentage,
          rel.updatedAt = datetime()
        RETURN count(rel) AS count
        """
        
        try:
            with self.conn.get_session() as session:
                result = session.run(cypher, records=records)
                data = result.single()
                return {
                    "created": data["count"] if data else 0,
                    "updated": 0
                }
        except Exception as e:
            logger.error(f"Relationship batch error: {str(e)[:100]}")
            return {"created": 0, "updated": 0}
            
    def get_load_statistics(self) -> Dict:
        """Get current graph statistics."""
        cypher = """
        RETURN
          apoc.meta.stats() AS stats,
          (MATCH (le:LegalEntity) RETURN count(*) AS legal_entities) AS legal_entities,
          (MATCH (addr:Address) RETURN count(*) AS addresses) AS addresses,
          (MATCH ()-[rel:PARENT_OF]->() RETURN count(*) AS parent_of) AS parent_of,
          (MATCH ()-[rel:LOCATED_AT]->() RETURN count(*) AS located_at) AS located_at
        """
        
        try:
            with self.conn.get_session() as session:
                result = session.run(cypher)
                return result.single()
        except Exception as e:
            logger.error(f"Failed to get statistics: {e}")
            return {}
