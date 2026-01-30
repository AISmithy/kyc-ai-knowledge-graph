"""
Graph expansion utilities for KYC use-cases.

Provides deterministic expansions:
- beneficial ownership chain traversal
- control threshold filtering (e.g., >25% ownership)
- jurisdiction / country risk joins
- adverse media joins

These functions use the existing `neo4j_module.connector.Neo4jConnection` to run Cypher queries.
"""

from typing import List, Dict, Optional
import logging

from neo4j_module.connector import Neo4jConnection

logger = logging.getLogger(__name__)


def get_direct_parent(conn: Neo4jConnection, lei: str) -> Optional[Dict]:
    """Return the direct parent of an entity (one hop).

    Returns a dict with parent properties or None.
    """
    cypher = """
    MATCH (c:LegalEntity {lei: $lei})-[:PARENT_OF]->(p:LegalEntity)
    RETURN p LIMIT 1
    """
    with conn.get_session() as session:
        res = session.run(cypher, lei=lei)
        rec = res.single()
        if not rec or rec[0] is None:
            return None
        node = rec[0]
        return dict(node)


def get_ultimate_parent(conn: Neo4jConnection, lei: str) -> Optional[Dict]:
    """Return the ultimate parent by walking PARENT_OF to the top.

    Uses a variable-length path and returns the farthest ancestor.
    """
    cypher = """
    MATCH path=(c:LegalEntity {lei: $lei})-[:PARENT_OF*1..]->(anc:LegalEntity)
    WITH anc, length(path) AS depth
    ORDER BY depth DESC
    RETURN anc LIMIT 1
    """
    with conn.get_session() as session:
        res = session.run(cypher, lei=lei)
        rec = res.single()
        if not rec or rec[0] is None:
            return None
        return dict(rec[0])


def traverse_beneficial_ownership_chain(
    conn: Neo4jConnection,
    lei: str,
    threshold_pct: float = 25.0,
    max_hops: int = 10
) -> List[Dict]:
    """Traverse ownership paths where each relationship meets a control threshold.

    Returns a list of paths; each path is dict {leis: [...], rels: [...]}
    """
    threshold = float(threshold_pct)
    cypher = f"""
    MATCH path=(start:LegalEntity {{lei: $lei}})-[r:PARENT_OF*1..{max_hops}]->(end:LegalEntity)
    WHERE ALL(rel IN relationships(path) WHERE coalesce(rel.ownershipPercentage, 0) >= $threshold)
    RETURN [n IN nodes(path) | n.lei] AS leis,
           [rel IN relationships(path) | {{ownership: coalesce(rel.ownershipPercentage, 0), start: startNode(rel).lei, end: endNode(rel).lei}}] AS rels
    LIMIT 100
    """
    with conn.get_session() as session:
        result = session.run(cypher, lei=lei, threshold=threshold)
        paths = []
        for rec in result:
            paths.append({"leis": rec["leis"], "rels": rec["rels"]})
        return paths


def jurisdiction_risk_join(conn: Neo4jConnection, lei: str, risk_countries: Optional[List[str]] = None) -> Dict:
    """Return entity plus nearby jurisdictional risk signals.

    - If `risk_countries` not provided, uses a sensible default list.
    - Returns counts and matching entities in high-risk jurisdictions.
    """
    if risk_countries is None:
        risk_countries = ["IR", "KP", "SY", "SD", "CU", "VE"]  # example high-risk list

    cypher = """
    MATCH (e:LegalEntity {lei: $lei})
    OPTIONAL MATCH (other:LegalEntity) WHERE other.jurisdiction IN $risk_countries
    RETURN e.lei AS lei, e.legalName AS name, e.jurisdiction AS jurisdiction, count(DISTINCT other) AS high_risk_neighbors
    """
    with conn.get_session() as session:
        rec = session.run(cypher, lei=lei, risk_countries=risk_countries).single()
        return dict(rec) if rec else {}


def link_adverse_media(conn: Neo4jConnection, records: List[Dict], batch_size: int = 200) -> Dict:
    """Ingest adverse media records and link to entities where possible.

    Each record should contain at minimum: `id`, and one of `lei` or `entity_name`.
    Returns counts of created links.
    """
    created = 0
    failed = 0
    for i in range(0, len(records), batch_size):
        batch = records[i : i + batch_size]
        params = []
        for r in batch:
            params.append({
                "id": r.get("id"),
                "title": r.get("title"),
                "source": r.get("source"),
                "date": r.get("date"),
                "lei": r.get("lei"),
                "entity_name": r.get("entity_name"),
            })

        cypher = """
        UNWIND $records AS rec
        MERGE (am:AdverseMedia {id: rec.id})
          ON CREATE SET am.title = rec.title, am.source = rec.source, am.date = rec.date, am.createdAt = datetime()
        WITH rec, am
        WHERE rec.lei IS NOT NULL
        MATCH (e:LegalEntity {lei: rec.lei})
        MERGE (e)-[rel:MENTIONED_IN]->(am)
        RETURN count(rel) AS links
        """
        try:
            with conn.get_session() as session:
                res = session.run(cypher, records=params)
                rec = res.single()
                if rec and rec.get("links"):
                    created += int(rec.get("links"))
        except Exception as e:
            logger.error(f"Adverse media batch failed: {e}")
            failed += len(batch)

    return {"created": created, "failed": failed}
