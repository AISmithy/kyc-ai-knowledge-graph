# KYC Knowledge Graph Schema

## Overview
This document defines the Neo4j graph schema for the KYC (Know Your Customer) AI Knowledge Graph, built on GLEIF (Global Legal Entity Identifier Foundation) data.

---

## Node Types

### 1. **LegalEntity**
Represents a legal entity with a Global Legal Entity Identifier (LEI).

**Labels:** `:LegalEntity`

**Properties:**
| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `lei` | String | ✓ | Global Legal Entity Identifier (unique) |
| `legalName` | String | ✓ | Official legal name of the entity |
| `entityStatus` | String | | Current status (ACTIVE, INACTIVE, MERGED, etc.) |
| `entityCategory` | String | | Category (FUND, CORPORATION, etc.) |
| `legalJurisdiction` | String | | ISO 2-letter jurisdiction code |
| `entityLegalFormCode` | String | | Code representing legal form |
| `creationDate` | Date | | Date entity was created |
| `registrationDate` | Date | | Initial registration date with LEI |
| `lastUpdateDate` | Date | | Last update timestamp |
| `validationSources` | List | | Data validation sources |

**Constraints:**
- `lei` is **UNIQUE** and serves as the primary identifier
- Index on `legalName` for fast lookup

---

### 2. **Address**
Represents a physical address associated with entities.

**Labels:** `:Address`

**Properties:**
| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `addressId` | String | ✓ | Unique address identifier |
| `firstAddressLine` | String | ✓ | Primary address line |
| `additionalAddressLine` | String | | Secondary address line |
| `city` | String | ✓ | City name |
| `region` | String | | State/province/region |
| `country` | String | ✓ | ISO 2-letter country code |
| `postalCode` | String | | Postal/ZIP code |
| `addressType` | String | | Type (REGISTERED, HEADQUARTERS, etc.) |

**Constraints:**
- `addressId` is **UNIQUE**
- Index on `country`, `city`

---

### 3. **RegistrationAuthority**
Represents the authority responsible for entity registration.

**Labels:** `:RegistrationAuthority`

**Properties:**
| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `authorityId` | String | ✓ | Unique authority identifier |
| `authorityName` | String | ✓ | Name of the registration authority |
| `country` | String | ✓ | Country code where authority operates |
| `authorityType` | String | | Type (GOVERNMENTAL, REGULATORY, etc.) |

**Constraints:**
- `authorityId` is **UNIQUE**

---

### 4. **ManagingLOU**
Represents a Local Operating Unit managing LEI records.

**Labels:** `:ManagingLOU`

**Properties:**
| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `louId` | String | ✓ | Unique LOU identifier (LEI of the LOU itself) |
| `louName` | String | ✓ | Name of the LOU |
| `country` | String | | Country code |

**Constraints:**
- `louId` is **UNIQUE**

---

### 5. **RelationshipType**
Represents a type of relationship between entities.

**Labels:** `:RelationshipType`

**Properties:**
| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `relationshipTypeCode` | String | ✓ | Standardized relationship type code |
| `relationshipTypeName` | String | ✓ | Human-readable name |
| `description` | String | | Description of relationship |

**Constraints:**
- `relationshipTypeCode` is **UNIQUE**

**Examples:**
- `PARENT_OF` - Entity is parent/holding company
- `SUBSIDIARY_OF` - Entity is subsidiary
- `BRANCH_OF` - Entity is branch
- `FUND_OF` - Entity is part of fund
- `MANAGES` - Entity manages another

---

## Edge Types (Relationships)

### 1. **PARENT_OF**
Connects a parent/holding company to a subsidiary.

**Direction:** Parent → Child

**Properties:**
| Property | Type | Description |
|----------|------|-------------|
| `relationshipStatus` | String | ACTIVE, INACTIVE, MERGED |
| `startDate` | Date | When relationship began |
| `endDate` | Date | When relationship ended (if applicable) |
| `percentageOwned` | Float | Ownership percentage (optional) |
| `source` | String | Data source (GLEIF_RR, etc.) |

**Source Node:** `:LegalEntity`
**Target Node:** `:LegalEntity`

---

### 2. **SUBSIDIARY_OF**
Inverse of PARENT_OF (for convenience queries).

**Direction:** Child → Parent

**Properties:** Same as `PARENT_OF`

**Source Node:** `:LegalEntity`
**Target Node:** `:LegalEntity`

---

### 3. **REGISTERED_WITH**
Connects an entity to its registration authority.

**Direction:** Entity → RegistrationAuthority

**Properties:**
| Property | Type | Description |
|----------|------|-------------|
| `registrationNumber` | String | Official registration number |
| `registrationDate` | Date | Registration date |

**Source Node:** `:LegalEntity`
**Target Node:** `:RegistrationAuthority`

---

### 4. **LOCATED_AT**
Connects an entity to an address.

**Direction:** Entity → Address

**Properties:**
| Property | Type | Description |
|----------|------|-------------|
| `addressType` | String | REGISTERED, HEADQUARTERS, BRANCH |
| `isPrimary` | Boolean | Is this the primary address? |

**Source Node:** `:LegalEntity`
**Target Node:** `:Address`

---

### 5. **MANAGED_BY**
Connects an entity's LEI record to its managing LOU.

**Direction:** Entity → ManagingLOU

**Properties:**
| Property | Type | Description |
|----------|------|-------------|
| `managementStartDate` | Date | When management began |
| `managementStatus` | String | ACTIVE, TRANSFERRED, etc. |

**Source Node:** `:LegalEntity`
**Target Node:** `:ManagingLOU`

---

### 6. **IN_JURISDICTION**
Connects an entity to its legal jurisdiction.

**Direction:** Entity → Jurisdiction (represented as a String property on Entity)

**Properties:**
| Property | Type | Description |
|----------|------|-------------|
| `jurisdictionCode` | String | ISO jurisdiction code |

**Alternative:** Store jurisdiction as a property on the Entity node.

---

## Indices and Constraints

### Unique Constraints
```cypher
CREATE CONSTRAINT lei_unique IF NOT EXISTS FOR (e:LegalEntity) REQUIRE e.lei IS UNIQUE;
CREATE CONSTRAINT address_id_unique IF NOT EXISTS FOR (a:Address) REQUIRE a.addressId IS UNIQUE;
CREATE CONSTRAINT authority_id_unique IF NOT EXISTS FOR (ra:RegistrationAuthority) REQUIRE ra.authorityId IS UNIQUE;
CREATE CONSTRAINT lou_id_unique IF NOT EXISTS FOR (l:ManagingLOU) REQUIRE l.louId IS UNIQUE;
CREATE CONSTRAINT rel_type_unique IF NOT EXISTS FOR (rt:RelationshipType) REQUIRE rt.relationshipTypeCode IS UNIQUE;
```

### Indices for Performance
```cypher
CREATE INDEX lei_index IF NOT EXISTS FOR (e:LegalEntity) ON (e.lei);
CREATE INDEX legal_name_index IF NOT EXISTS FOR (e:LegalEntity) ON (e.legalName);
CREATE INDEX entity_status_index IF NOT EXISTS FOR (e:LegalEntity) ON (e.entityStatus);
CREATE INDEX country_index IF NOT EXISTS FOR (a:Address) ON (a.country);
CREATE INDEX city_index IF NOT EXISTS FOR (a:Address) ON (a.city);
CREATE INDEX authority_country_index IF NOT EXISTS FOR (ra:RegistrationAuthority) ON (ra.country);
```

---

## Example Queries

### Find all subsidiaries of a parent company
```cypher
MATCH (parent:LegalEntity {lei: '5493001KJTIIGC8Y1R12'})
       -[r:PARENT_OF]->(child:LegalEntity)
RETURN parent.legalName, child.legalName, r.relationshipStatus
ORDER BY child.legalName;
```

### Find the full organizational hierarchy
```cypher
MATCH (root:LegalEntity {lei: '5493001KJTIIGC8Y1R12'})
MATCH path = (root)-[:PARENT_OF*0..10]->(descendant:LegalEntity)
RETURN path, length(path) as depth
ORDER BY depth DESC;
```

### Find entities by jurisdiction
```cypher
MATCH (e:LegalEntity)
WHERE e.legalJurisdiction = 'GB'
RETURN e.lei, e.legalName, e.entityStatus
LIMIT 100;
```

### Find entities registered with a specific authority
```cypher
MATCH (e:LegalEntity)-[r:REGISTERED_WITH]->(ra:RegistrationAuthority {authorityName: 'Companies House'})
RETURN e.lei, e.legalName, r.registrationNumber
LIMIT 100;
```

### Find all addresses of an entity
```cypher
MATCH (e:LegalEntity {lei: '5493001KJTIIGC8Y1R12'})
       -[rel:LOCATED_AT]->(addr:Address)
RETURN e.legalName, rel.addressType, addr.firstAddressLine, addr.city, addr.country;
```

### Detect network patterns (entities with common jurisdictions)
```cypher
MATCH (e1:LegalEntity)-[:PARENT_OF]->(e2:LegalEntity)
WHERE e1.legalJurisdiction = e2.legalJurisdiction
RETURN e1.legalName, e2.legalName, e1.legalJurisdiction
LIMIT 50;
```

---

## Data Validation Rules

1. **LEI Format:** Must be 20 alphanumeric characters (ISO 17442)
2. **Country Codes:** ISO 3166-1 alpha-2 standard (GB, US, etc.)
3. **Jurisdiction Codes:** ISO 20275 standard
4. **Dates:** ISO 8601 format (YYYY-MM-DD)
5. **Ownership Percentage:** 0-100 range if specified

---

## Migration Path from GLEIF Data

1. **LEI Records** → `:LegalEntity` nodes
2. **Relationship Records** → `:PARENT_OF` / `:SUBSIDIARY_OF` edges
3. **Address Information** → `:Address` nodes + `:LOCATED_AT` edges
4. **Registration Authority** → `:RegistrationAuthority` nodes + `:REGISTERED_WITH` edges
5. **Managing LOU** → `:ManagingLOU` nodes + `:MANAGED_BY` edges

---

## Future Extensions

- **Sanctions/PEP Nodes:** `:SanctionedEntity`, `:PoliticallyExposedPerson`
- **Risk Assessment:** `:RiskProfile` nodes with risk scores
- **Beneficial Ownership:** Detailed BO chain with `:BENEFICIAL_OWNER` edges
- **Documents:** `:Document` nodes for filing/registration documents
- **Events:** `:ComplianceEvent` for audit trails and status changes
