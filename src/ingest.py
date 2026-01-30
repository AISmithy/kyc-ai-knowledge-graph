"""
Ingestion helpers for external data (adverse media, screening results).

This module contains small utilities to load adverse media feeds and push
them into Neo4j using the `retrieval.link_adverse_media` helper.
"""

import csv
from pathlib import Path
from typing import List, Dict
import logging

from neo4j_module.connector import Neo4jConnection
from retrieval import link_adverse_media

logger = logging.getLogger(__name__)


def load_adverse_media_csv(path: str) -> List[Dict]:
    """Read a CSV of adverse media items and return list of records.

    Expect columns: id, title, source, date, lei, entity_name
    """
    records: List[Dict] = []
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(str(p))

    with p.open("r", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            records.append({
                "id": row.get("id") or row.get("identifier"),
                "title": row.get("title") or row.get("headline"),
                "source": row.get("source"),
                "date": row.get("date"),
                "lei": row.get("lei"),
                "entity_name": row.get("entity_name") or row.get("name"),
            })
    return records


def ingest_adverse_media_csv(conn: Neo4jConnection, csv_path: str) -> Dict:
    """Load adverse media CSV and link items to LegalEntity nodes in Neo4j.

    Returns the same shape dict returned by `link_adverse_media`.
    """
    records = load_adverse_media_csv(csv_path)
    logger.info(f"Loaded {len(records)} adverse media records from {csv_path}")
    results = link_adverse_media(conn, records)
    logger.info(f"Adverse media ingestion result: {results}")
    return results
