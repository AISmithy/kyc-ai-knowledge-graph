-- Schema additions for KYC graph expansions

// Adverse media nodes and relationships
CREATE CONSTRAINT IF NOT EXISTS FOR (a:AdverseMedia) REQUIRE a.id IS UNIQUE;
CREATE INDEX IF NOT EXISTS FOR (a:AdverseMedia) ON (a.source);

// Ensure LegalEntity.lei uniqueness (should already exist from schema.py)
CREATE CONSTRAINT IF NOT EXISTS FOR (le:LegalEntity) REQUIRE le.lei IS UNIQUE;

// Helpful indices
CREATE INDEX IF NOT EXISTS FOR (le:LegalEntity) ON (le.legalName);
CREATE INDEX IF NOT EXISTS FOR (le:LegalEntity) ON (le.jurisdiction);

// Relationship types used by ingestion/expansion
// MENTIONED_IN: (LegalEntity)-[:MENTIONED_IN]->(AdverseMedia)
// PARENT_OF: ownership edges (already in schema)
