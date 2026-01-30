# KYC Knowledge Graph MVP - Success Queries

## Objective
Lock the MVP scope with 3 "must-answer" queries that drive all architecture decisions.

---

## Query 1: Ultimate Parent + Direct Parent Chain

**Business Question:** Given a client LEI, what is the ultimate parent and direct parent?

**Use Case:** KYC/AML analyst needs to verify corporate ownership structure for sanctions screening.

**Cypher Query:**
```cypher
MATCH (client:LegalEntity {lei: $clientLei})
OPTIONAL MATCH (client)-[:PARENT_OF*1..] (parent:LegalEntity)
WITH client, parent ORDER BY LENGTH(p) LIMIT 1
OPTIONAL MATCH (client)-[:PARENT_OF] (directParent:LegalEntity)
RETURN 
  client.lei AS client_lei,
  client.legalName AS client_name,
  directParent.lei AS direct_parent_lei,
  directParent.legalName AS direct_parent_name,
  parent.lei AS ultimate_parent_lei,
  parent.legalName AS ultimate_parent_name,
  client.jurisdiction AS jurisdiction
LIMIT 1
```

**Acceptance Criteria:**
- ✓ Returns direct parent (1 hop from client)
- ✓ Returns ultimate parent (highest in chain)
- ✓ Handles orphan entities (no parent exists)
- ✓ Query executes in <100ms on 10k entities

**Test Data:** Load at least 5 family trees (parent-child-grandchild chains)

---

## Query 2: Ownership Chain + Beneficial Owner (BO) Gap Flag

**Business Question:** Show me the ownership chain and flag where beneficial owner data is missing.

**Use Case:** Compliance teams need to detect when corporate veils may hide UBOs (Ultimate Beneficial Owners).

**Cypher Query:**
```cypher
MATCH (entity:LegalEntity {lei: $entityLei})
CALL apoc.path.expandConfig({
  relationshipFilter: "PARENT_OF|SUBSIDIARY_OF|ULTIMATE_PARENT_OF",
  labelFilter: "+LegalEntity",
  maxLevel: 10,
  returnPaths: true
})
YIELD path
UNWIND nodes(path) AS node
WITH entity, node, relationships(path) AS rels
RETURN
  node.lei AS lei,
  node.legalName AS legal_name,
  node.entityStatus AS status,
  CASE WHEN node.beneficialOwnerKnown = true THEN "Known" ELSE "MISSING" END AS bo_status,
  node.jurisdiction AS jurisdiction
ORDER BY length(path)
```

**Acceptance Criteria:**
- ✓ Returns all nodes in ownership chain (breadth-first or depth-first)
- ✓ Flags BO status (missing = red flag)
- ✓ Detects circular relationships (if they exist)
- ✓ Query executes in <500ms on 100k entities

**Test Data:** Load mixed entity types with/without BO data

---

## Query 3: Complexity Score - Hops, Entities, Cross-Border

**Business Question:** How complex is this entity's ownership structure?

**Use Case:** Risk assessment - entities with complex structures (many hops, cross-border) may indicate higher AML/sanctions risk.

**Cypher Query:**
```cypher
MATCH (entity:LegalEntity {lei: $entityLei})
OPTIONAL MATCH path = (entity)-[:PARENT_OF|SUBSIDIARY_OF*]-(related:LegalEntity)
WITH entity, collect(DISTINCT related) AS relatedEntities
OPTIONAL MATCH (entity)-[:LOCATED_AT]->(addr:Address)
WITH entity, relatedEntities, addr,
  length(relatedEntities) AS num_related,
  apoc.agg.count(DISTINCT addr.country) AS num_countries
OPTIONAL MATCH (entity)-[r:PARENT_OF|SUBSIDIARY_OF]-()
WITH entity, num_related, num_countries,
  length(collect(r)) AS num_relationships
RETURN
  entity.lei AS lei,
  entity.legalName AS legal_name,
  num_related AS related_entity_count,
  num_relationships AS direct_relationships,
  num_countries AS jurisdictions,
  CASE
    WHEN num_related > 20 AND num_countries > 3 THEN "HIGH"
    WHEN num_related > 5 OR num_countries > 1 THEN "MEDIUM"
    ELSE "LOW"
  END AS complexity_score
```

**Acceptance Criteria:**
- ✓ Counts all related entities in network
- ✓ Calculates hops depth (max path length)
- ✓ Counts distinct jurisdictions
- ✓ Returns complexity tier (LOW/MEDIUM/HIGH)
- ✓ Query executes in <1s on 1M entities

**Test Data:** Create entities with varying complexity: simple (1 jurisdiction, no parents), moderate (2-3 jurisdictions, 5+ related), complex (5+ jurisdictions, deep chains)

---

## Test Dataset Requirements (MVP Scope)

To validate all 3 queries, load test data with:

| Entity Type | Count | Properties |
|------------|-------|-----------|
| Root entities (no parent) | 50 | LEI, legalName, jurisdiction, entityStatus |
| Subsidiary chains (2-5 levels) | 100 | LEI, legalName, parent_lei, jurisdiction |
| Cross-border networks (3+ countries) | 30 | LEI, legalName, jurisdiction, related_leis |
| Orphan/dead entities | 20 | LEI, legalName, entityStatus=INACTIVE |
| **Total Entities** | **200** | All required schema properties |

---

## Success Metrics

Once all 3 queries pass acceptance criteria:

1. **Query 1:** Ultimate parent + direct parent identified for 95%+ of entities with parents
2. **Query 2:** BO flags correctly identify entities with missing beneficial owner data
3. **Query 3:** Complexity score correctly tiers entities by network size and geography

All queries must execute in documented time bounds (100ms–1s depending on scope).

---

## Next Steps

1. Load sample GLEIF data (200–500 entities with relationships)
2. Execute each query against test graph
3. Measure query performance
4. Adjust schema/indices if needed
5. Document actual performance results
