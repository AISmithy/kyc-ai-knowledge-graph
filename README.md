# KYC AI Knowledge Graph

**Build a regulatory-ready knowledge graph from GLEIF data with Neo4j.**

## What This Does

Ingests GLEIF Level 1 & 2 data → normalizes & validates → persists to Parquet → loads into Neo4j Aura. Provides graph expansion queries for beneficial ownership chains, jurisdiction risk scoring, and adverse media linking.

## Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         KYC Knowledge Graph System                       │
└─────────────────────────────────────────────────────────────────────────┘

                              GLEIF Data Sources
                                    │
                        ┌───────────┴────────────┐
                        │                        │
                   Level 1 (7.2GB)         Level 2 (1.0GB)
                      XML                     XML
                        │                        │
                        └───────────┬────────────┘
                                    │
                    ┌───────────────▼────────────────┐
                    │   Data Ingestion Pipeline      │
                    │  (src/data_loader/)            │
                    │                                │
                    │  1. Download & Extract         │
                    │  2. Stream XML (iterparse)     │
                    │  3. Normalize & Validate       │
                    │  4. Persist to Parquet         │
                    │  5. Load to Neo4j              │
                    └───────────────┬────────────────┘
                                    │
                    ┌───────────────▼────────────────┐
                    │    Neo4j Aura Instance         │
                    │   (kyc-graph-01)               │
                    │                                │
                    │  • 5 Node Types                │
                    │  • 6 Edge Types                │
                    │  • Indices & Constraints       │
                    └───────────────┬────────────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        │                           │                           │
    ┌───▼────────────┐    ┌────────▼─────────┐    ┌───────────▼──┐
    │ Graph Expansion│    │  External Data   │    │  GraphRAG    │
    │   (retrieval)  │    │   (CSV ingestion)│    │   (LLM)      │
    │                │    │                  │    │              │
    │ • BO Chains    │    │ • Adverse Media  │    │ • Question   │
    │ • Jurisdiction │    │ • Screening List │    │   Routing    │
    │   Risk         │    │ • Watchlists     │    │ • LLM Calls  │
    │ • Risk Scoring │    │                  │    │ • Reasoning  │
    └────────────────┘    └──────────────────┘    └──────────────┘
                                    │
                    ┌───────────────▼────────────────┐
                    │      KYC Answers & Reports     │
                    │  • Beneficial Owners           │
                    │  • Risk Assessment             │
                    │  • Adverse Media Flags         │
                    │  • Compliance Recommendations  │
                    └────────────────────────────────┘
```

### 1. Data Ingestion Pipeline (`src/data_loader/`)
- **downloader.py**: Scrapes GLEIF, downloads & extracts ZIPs
- **processors.py**: Streaming XML parser (ElementTree.iterparse) for 7+ GB files
- **normalization.py**: Column mapping, type conversion, quality checks, deduplication
- **persistence.py**: Parquet I/O with versioning and compression
- **main.py**: 5-stage orchestration (download → load → normalize → persist → neo4j)

### 2. Graph Database (`src/neo4j_module/`)
- **connector.py**: Connection pooling, encryption handling
- **schema.py**: Constraints (LEI unique), indices (name, jurisdiction, status)
- **loader.py**: Batch MERGE operations for entities, addresses, relationships

### 3. Graph Expansion (`src/`)
- **retrieval.py**: Beneficial ownership traversal, jurisdiction risk joins, adverse media linking
- **ingest.py**: CSV loader for external data feeds (adverse media, screening)
- **rag.py**: Context assembly for LLM-based KYC workflows

### 4. LLM-Augmented KYC (`src/`)
- **graphrag.py**: Graph-augmented LLM reasoning for KYC question answering
  - `identify_beneficial_owners()` - BO chain analysis + LLM reasoning
  - `assess_jurisdiction_risk()` - Risk scoring + recommendations
  - `flag_adverse_media()` - Media aggregation + severity assessment
  - `comprehensive_kyc_review()` - Full KYC check in single call
  - Supports Claude 3 (Anthropic) and GPT-4 (OpenAI)

### 5. Schema
- **schema.cypher**: Constraint and index definitions for AdverseMedia node type

## Quick Start

```bash
# Setup
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Run MVP test (1000 LEI records)
python test_mvp_simple.py

# Load data to Neo4j (optional --neo4j flag)
python -m data_loader.main --nrows 1000 --neo4j
```

## Design Principles

- **Streaming First**: Use iterparse for multi-GB files without memory bloat
- **Batch Processing**: Neo4j MERGE ops use 500-record transactions
- **Quality Gates**: Normalization tracks nulls, duplicates, referential integrity
- **Versioning**: Parquet outputs timestamped, quality reports JSON-exported
- **Deterministic Queries**: Graph expansion uses explicit thresholds (e.g., >25% ownership)

## Key Features

| Component | Purpose |
|-----------|---------|
| `traverse_beneficial_ownership_chain()` | Follow PARENT_OF relationships above control threshold |
| `jurisdiction_risk_join()` | Flag entities in high-risk jurisdictions |
| `link_adverse_media()` | Ingest screening records, link to LegalEntity nodes |
| `assemble_context_for_lei()` | Prepare text context for LLM prompts |
| `graphrag.comprehensive_kyc_review()` | Run all KYC checks (BO, risk, media) with LLM reasoning |
| `GraphRAG.identify_beneficial_owners()` | Trace ownership chains, flag control gaps |
| `GraphRAG.assess_jurisdiction_risk()` | Evaluate AML/CFT exposure |
| `.env.example` | Environment variable template (Neo4j URI, credentials, LLM keys) |

## Data Flow Diagram

```
GLEIF ZIPs (7+ GB)
     │
     ▼
┌─────────────────────────┐
│  Streaming XML Parser   │    ElementTree.iterparse
│  (iterparse)            │    → No memory bloat
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│ Normalization & QC      │    • Column mapping
│                         │    • Type conversion
│ • Null detection        │    • Deduplication
│ • Duplicate detection   │    • Referential integrity
│ • Field validation      │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│ Parquet Persistence     │    • Snappy compression
│                         │    • Versioning
│ • Quality reports JSON  │    • Size: ~500MB (compressed)
│ • CSV exports           │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│ Neo4j Batch MERGE       │    • 500 records/transaction
│                         │    • Idempotent operations
│ • 5 Node types          │    • Constraint enforcement
│ • 6 Edge types          │
│ • Indices created       │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│ Graph Query Engine      │    • Beneficial ownership chains
│                         │    • Jurisdiction risk assessment
│ + LLM Reasoning Layer   │    • Adverse media flagging
│                         │    • KYC recommendations
└─────────────────────────┘
```

## Data Flow

```
GLEIF ZIPs
   ↓
XML streaming (iterparse)
   ↓
Normalize + QC (nulls, duplicates, types)
   ↓
Parquet persistence (snappy compression)
   ↓
Neo4j batch MERGE (500 records/txn)
   ↓
Graph queries (BO chains, risk scores, BO flags)
```

## Project Structure

```
src/
├── data_loader/           # Ingestion & normalization
│   ├── config.py
│   ├── downloader.py
│   ├── processors.py
│   ├── normalization.py   # Quality checks & mapping
│   ├── persistence.py     # Parquet I/O
│   └── main.py
├── neo4j_module/          # Graph database
│   ├── connector.py
│   ├── schema.py
│   └── loader.py
├── retrieval.py           # Graph expansion
├── ingest.py              # External data ingestion
└── rag.py                 # Context assembly

schema.cypher             # Neo4j constraint/index definitions
.env.example              # Environment template
test_mvp_simple.py        # End-to-end validation
```

## MVP Validation

- ✅ 1000 LEI records normalized and persisted to Parquet
- ✅ 1000 LegalEntity nodes inserted into Neo4j Aura
- ✅ Query performance: <100ms on 1000 nodes
- ✅ Schema constraints and indices verified

## References

- [GLEIF Data](https://www.gleif.org/en/about-lei/get-the-data)
- [Neo4j Aura](https://neo4j.com/cloud/aura/)
- [GraphRAG Documentation](docs/GRAPHRAG.md)
- [MVP Queries](MVP_QUERIES.md)
- [Implementation Details](MVP_IMPLEMENTATION.md)

## License

MIT
