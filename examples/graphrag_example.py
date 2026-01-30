"""
Example: Using GraphRAG for KYC question answering.

This demonstrates:
- Initializing GraphRAG with Neo4j connection
- Running individual KYC checks (beneficial owners, jurisdiction risk, adverse media)
- Running comprehensive reviews
- Formatting results
"""

import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv
from neo4j_module.connector import Neo4jConnection
from graphrag import GraphRAG

load_dotenv()


def main():
    """Run example KYC review using GraphRAG."""

    # Initialize Neo4j connection
    uri = os.getenv("NEO4J_URI")
    user = os.getenv("NEO4J_USER")
    password = os.getenv("NEO4J_PASSWORD")

    if not all([uri, user, password]):
        print("ERROR: Missing Neo4j credentials in .env")
        print("Expected: NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD")
        return

    conn = Neo4jConnection(uri, user, password)

    # Test connection
    try:
        conn.verify_connection()
        print("✓ Neo4j connection verified")
    except Exception as e:
        print(f"✗ Neo4j connection failed: {e}")
        return

    # Initialize GraphRAG with Claude (requires ANTHROPIC_API_KEY)
    # For OpenAI: GraphRAG(conn, model="gpt-4")
    try:
        graphrag = GraphRAG(conn, model="claude-3-sonnet")
        print("✓ GraphRAG initialized (Claude)")
    except ImportError as e:
        print(f"✗ LLM initialization failed: {e}")
        print("Install dependencies: pip install anthropic")
        return

    # Example: Query a LEI from the database
    # (replace with actual LEI from your graph)
    with conn.get_session() as session:
        result = session.run("MATCH (e:LegalEntity) RETURN e.lei LIMIT 1")
        lei = result.single()
        if not lei:
            print("No entities found in database. Run MVP pipeline first.")
            return
        lei = lei[0]

    print(f"\nRunning KYC review for LEI: {lei}")
    print("-" * 60)

    # Option 1: Individual checks
    print("\n1. Beneficial Owner Identification")
    try:
        bo_result = graphrag.identify_beneficial_owners(lei)
        print(bo_result.answer)
        if bo_result.usage:
            print(f"   [Tokens: {bo_result.usage}]")
    except Exception as e:
        print(f"   Error: {e}")

    print("\n2. Jurisdiction Risk Assessment")
    try:
        jr_result = graphrag.assess_jurisdiction_risk(lei)
        print(jr_result.answer)
        if jr_result.usage:
            print(f"   [Tokens: {jr_result.usage}]")
    except Exception as e:
        print(f"   Error: {e}")

    print("\n3. Adverse Media Check")
    try:
        am_result = graphrag.flag_adverse_media(lei)
        print(am_result.answer)
        if am_result.usage:
            print(f"   [Tokens: {am_result.usage}]")
    except Exception as e:
        print(f"   Error: {e}")

    # Option 2: Comprehensive review (all checks + formatted report)
    print("\n" + "=" * 60)
    print("Running Comprehensive Review...")
    try:
        review = graphrag.comprehensive_kyc_review(lei)
        report = graphrag.format_report(review)
        print(report)
    except Exception as e:
        print(f"Error: {e}")

    conn.close()


if __name__ == "__main__":
    main()
