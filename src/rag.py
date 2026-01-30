"""
Simple RAG (retrieval-augmented generation) helper.

This is a lightweight helper that assembles graph-expanded context for a
given LEI and returns a plain-text context block suitable for prompt usage.
It is intentionally small — full LLM integration belongs in another module.
"""

from typing import Dict, List
import logging

from neo4j_module.connector import Neo4jConnection
from retrieval import get_direct_parent, get_ultimate_parent, traverse_beneficial_ownership_chain, jurisdiction_risk_join

logger = logging.getLogger(__name__)


def assemble_context_for_lei(conn: Neo4jConnection, lei: str, ownership_threshold: float = 25.0) -> str:
    """Assemble a compact text context for a single LEI.

    - direct parent
    - ultimate parent
    - beneficial ownership paths above threshold
    - jurisdiction risk summary
    """
    parts: List[str] = []
    parts.append(f"Entity LEI: {lei}")

    try:
        direct = get_direct_parent(conn, lei)
        if direct:
            parts.append(f"Direct parent: {direct.get('lei')} - {direct.get('legalName')}")
        else:
            parts.append("Direct parent: None")

        ultimate = get_ultimate_parent(conn, lei)
        if ultimate:
            parts.append(f"Ultimate parent: {ultimate.get('lei')} - {ultimate.get('legalName')}")
        else:
            parts.append("Ultimate parent: None")

        paths = traverse_beneficial_ownership_chain(conn, lei, threshold_pct=ownership_threshold)
        parts.append(f"Beneficial ownership chains (threshold {ownership_threshold}%): {len(paths)} path(s)")
        for p in paths[:5]:
            parts.append(" -> ".join(p.get('leis', [])))

        jr = jurisdiction_risk_join(conn, lei)
        parts.append(f"Jurisdiction: {jr.get('jurisdiction')} | High-risk neighbors: {jr.get('high_risk_neighbors',0)}")

    except Exception as e:
        logger.error(f"Failed to assemble context for {lei}: {e}")
        parts.append(f"Error assembling context: {e}")

    return "\n".join(parts)
