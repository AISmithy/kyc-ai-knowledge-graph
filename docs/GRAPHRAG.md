# GraphRAG: LLM-Augmented Knowledge Graph Reasoning

## Overview

`GraphRAG` combines deterministic Neo4j graph queries with Claude/OpenAI LLMs to answer complex KYC questions. Rather than relying solely on LLM hallucinations, it:

1. **Executes structured graph queries** to fetch relevant ownership, risk, and screening data
2. **Assembles context** from multiple sources (beneficial owner chains, jurisdiction data, adverse media)
3. **Prompts LLM** with factual context to reason and make recommendations
4. **Returns structured answers** with citations and confidence levels

This approach ensures answers are grounded in the actual KYC knowledge graph while benefiting from LLM reasoning.

---

## Key Components

### `GraphRAG` Class

```python
from graphrag import GraphRAG
from neo4j_module.connector import Neo4jConnection

conn = Neo4jConnection(uri, user, password)
graphrag = GraphRAG(conn, model="claude-3-sonnet")
```

**Supported Models:**
- `claude-3-sonnet` (default) - Fast, good for compliance tasks
- `claude-3-opus` - Slower, most capable
- `gpt-4` - OpenAI's most capable model
- `gpt-3.5-turbo` - OpenAI's fastest model

**LLM Setup:**
- **Claude:** Requires `ANTHROPIC_API_KEY` in `.env`
- **OpenAI:** Requires `OPENAI_API_KEY` in `.env`

---

## Methods

### 1. `identify_beneficial_owners(lei, ownership_threshold=25.0)`

Identify beneficial owners of an entity using ownership chain traversal + LLM reasoning.

**Input:**
- `lei`: Legal Entity Identifier (string)
- `ownership_threshold`: Ownership % threshold for inclusion (default: 25%)

**Graph Context Gathered:**
- Direct parent entity
- Ultimate parent (root of ownership chain)
- All beneficial owner chains meeting threshold
- Top 5 ownership paths

**LLM Task:**
Analyze structures and identify beneficial owners, flag red flags (circular ownership, missing data), recommend action level (CLEAR/FURTHER_REVIEW/ESCALATE).

**Output:** `KYCAnswer` with:
```python
{
    "question": "Who are the beneficial owners of [LEI]?",
    "answer": "[LLM-generated beneficial owner analysis]",
    "context": {
        "lei": "...",
        "direct_parent": {...},
        "ultimate_parent": {...},
        "ownership_chains": [...]
    },
    "model": "claude-3-sonnet",
    "usage": {"input_tokens": 500, "output_tokens": 200}
}
```

**Example:**
```python
result = graphrag.identify_beneficial_owners("5493001W8JKWC1H2EF87")
print(result.answer)
# Output: "Based on ownership analysis, Company XYZ is ultimate parent.
#          RECOMMENDATION: FURTHER_REVIEW due to circular structure..."
```

---

### 2. `assess_jurisdiction_risk(lei, risk_countries=None)`

Evaluate jurisdiction-based AML/CFT exposure.

**Input:**
- `lei`: Legal Entity Identifier
- `risk_countries`: List of high-risk country codes (default: `['IR', 'KP', 'SY', 'SD', 'CU', 'VE']`)

**Graph Context Gathered:**
- Entity jurisdiction
- Number of high-risk neighbors (entities in sanctioned/high-risk countries)
- Connections to restricted jurisdictions

**LLM Task:**
Assess risk level (LOW/MEDIUM/HIGH/CRITICAL), identify key exposure areas, recommend actions.

**Output:** `KYCAnswer` with risk assessment and action items

**Example:**
```python
result = graphrag.assess_jurisdiction_risk("5493001W8JKWC1H2EF87")
print(result.answer)
# Output: "Risk Level: MEDIUM
#          Exposure: Entity has 2 subsidiaries in high-risk jurisdictions.
#          Action: Flag for enhanced due diligence..."
```

---

### 3. `flag_adverse_media(lei)`

Check for adverse media mentions and assess severity.

**Input:**
- `lei`: Legal Entity Identifier

**Graph Context Gathered:**
- All `AdverseMedia` nodes linked to entity (up to 20)
- Titles, sources, publication dates

**LLM Task:**
Summarize key issues, assess severity (LOW/MEDIUM/HIGH/CRITICAL), recommend follow-up.

**Output:** `KYCAnswer` with media summary and severity

**Example:**
```python
result = graphrag.flag_adverse_media("5493001W8JKWC1H2EF87")
print(result.answer)
# Output: "2 adverse mentions found:
#          - Fraud investigation (2023)
#          - Sanctions evasion allegation (2022)
#          Severity: HIGH - Recommend escalation to compliance..."
```

---

### 4. `comprehensive_kyc_review(lei)`

Run all three checks (beneficial owners, jurisdiction risk, adverse media) in sequence.

**Input:**
- `lei`: Legal Entity Identifier

**Output:** `Dict[str, KYCAnswer]`
```python
{
    "beneficial_owners": KYCAnswer(...),
    "jurisdiction_risk": KYCAnswer(...),
    "adverse_media": KYCAnswer(...)
}
```

**Example:**
```python
review = graphrag.comprehensive_kyc_review("5493001W8JKWC1H2EF87")
report = graphrag.format_report(review)
print(report)
```

---

### 5. `format_report(review)`

Format comprehensive review output as a readable report.

**Input:** `Dict[str, KYCAnswer]` from `comprehensive_kyc_review()`

**Output:** Formatted string with:
- Section headers
- LLM-generated analysis for each check
- Token usage per section
- Clear readability for compliance teams

---

## Data Structures

### `KYCAnswer` Dataclass

```python
@dataclass
class KYCAnswer:
    question: str              # The KYC question asked
    answer: str                # LLM-generated answer
    context: Dict[str, Any]    # Graph data that was retrieved
    model: str                 # Model used (e.g., "claude-3-sonnet")
    usage: Optional[Dict[str, int]]  # Token usage
```

---

## Configuration

### Environment Variables (.env)

```bash
# Neo4j Aura
NEO4J_URI=neo4j+s://xxx.databases.neo4j.io
NEO4J_USER=neo4j
NEO4J_PASSWORD=xxx

# Choose ONE LLM provider:

# Claude (Anthropic)
ANTHROPIC_API_KEY=sk-ant-xxx

# OpenAI
OPENAI_API_KEY=sk-xxx
```

### Installing LLM Dependencies

```bash
# Both (recommended)
pip install -r requirements.txt

# Claude only
pip install anthropic

# OpenAI only
pip install openai
```

---

## Usage Examples

### Basic Example: Single Check

```python
from neo4j_module.connector import Neo4jConnection
from graphrag import GraphRAG

# Setup
conn = Neo4jConnection(uri, user, password)
graphrag = GraphRAG(conn, model="claude-3-sonnet")

# Identify beneficial owners
lei = "5493001KJTIGYAFGKS75"
result = graphrag.identify_beneficial_owners(lei)

print(f"Question: {result.question}")
print(f"Answer: {result.answer}")
print(f"Context LEI: {result.context['lei']}")
print(f"Tokens used: {result.usage}")
```

### Full Review Example

```python
# Run all checks
review = graphrag.comprehensive_kyc_review(lei)

# Generate report
report = graphrag.format_report(review)
print(report)

# Or access individual results
print(review["beneficial_owners"].answer)
print(review["jurisdiction_risk"].answer)
print(review["adverse_media"].answer)
```

### Custom Question with Graph Context

```python
# Use underlying retrieval functions directly for custom questions
from retrieval import get_ultimate_parent, jurisdiction_risk_join

# Get raw context
parent = get_ultimate_parent(conn, lei)
risk = jurisdiction_risk_join(conn, lei)

# Build custom prompt
prompt = f"Entity: {lei}, Ultimate Parent: {parent}, Risk Data: {risk}"

# Then prompt LLM manually or extend GraphRAG with custom method
```

---

## Architecture: How GraphRAG Works

```
User Question (e.g., "Who owns entity X?")
           ↓
    GraphRAG Router
           ↓
    [Graph Query Phase]
    - get_ultimate_parent()
    - traverse_beneficial_ownership_chain()
    - jurisdiction_risk_join()
    - Query AdverseMedia nodes
           ↓
    [Context Assembly]
    - Collect relevant entities/edges
    - Format as readable text
    - Include sources/dates
           ↓
    [LLM Prompt Engineering]
    - System: "You are a KYC expert..."
    - User: "Based on this graph context, answer the question..."
           ↓
    [LLM API Call]
    - Send to Claude/OpenAI
    - Get reasoning + recommendation
           ↓
    [Response Formatting]
    - Parse LLM output
    - Attach citations (which graph nodes supported the answer)
    - Return KYCAnswer with metadata
           ↓
    User receives grounded, reasoned answer
```

---

## KYC Use Cases

### 1. Onboarding Review (Customer Due Diligence)

```python
# New customer provided LEI, need comprehensive KYC
lei = customer_provided_lei
review = graphrag.comprehensive_kyc_review(lei)

# Check recommendation levels
if "ESCALATE" in review["beneficial_owners"].answer:
    send_to_compliance_team(review)
elif "HIGH" in review["jurisdiction_risk"].answer:
    request_additional_documentation(lei)
else:
    approve_onboarding(lei)
```

### 2. Ongoing Monitoring (Transaction Screening)

```python
# During transaction, check for new adverse media
result = graphrag.flag_adverse_media(transaction_party_lei)

if "CRITICAL" in result.answer:
    block_transaction(result)
else:
    approve_transaction(transaction)
```

### 3. Beneficial Ownership Investigation

```python
# Regulatory inquiry: "Trace ownership of entity to natural persons"
result = graphrag.identify_beneficial_owners(
    lei, 
    ownership_threshold=10  # Lower threshold for comprehensive map
)

# LLM identifies chain and flags control gaps
report = generate_regulatory_report(result)
```

---

## Performance Considerations

### Token Usage & Costs

Each check costs approximately:
- **Beneficial Owners:** 500-800 input tokens, 200-400 output
- **Jurisdiction Risk:** 300-500 input tokens, 100-200 output
- **Adverse Media:** 400-600 input tokens, 200-300 output

**Cost estimates (as of 2024):**
- Claude 3 Sonnet: ~$0.003-0.01 per comprehensive review
- GPT-4: ~$0.03-0.10 per comprehensive review

### Optimization Tips

1. **Cache context for batch reviews:**
   ```python
   for lei in lei_list:
       # GraphRAG queries once per check, reuses Neo4j results
       review = graphrag.comprehensive_kyc_review(lei)
   ```

2. **Use faster models for routine checks:**
   ```python
   graphrag = GraphRAG(conn, model="gpt-3.5-turbo")  # Faster, cheaper
   ```

3. **Limit adverse media scope:**
   ```python
   # Query only last 2 years instead of all mentions
   ```

---

## Troubleshooting

### "LLM initialization failed: anthropic not installed"

```bash
pip install anthropic
```

### "ANTHROPIC_API_KEY not found in .env"

Update `.env`:
```bash
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxxxxxx
```

### "Neo4j connection failed"

Verify credentials in `.env`:
```bash
NEO4J_URI=neo4j+s://your-instance.databases.neo4j.io
NEO4J_USER=neo4j
NEO4J_PASSWORD=your-password
```

### LLM returning generic answers

Ensure graph has sufficient data:
```python
# Check entity exists
with conn.get_session() as session:
    result = session.run(
        "MATCH (e:LegalEntity {lei: $lei}) RETURN e",
        lei=your_lei
    )
    if not result.single():
        print("Entity not in graph - run MVP pipeline first")
```

---

## Future Enhancements

1. **Streaming responses** - Return LLM answer as it generates (tokens streamed)
2. **Multi-hop reasoning** - Query beyond immediate neighbors (e.g., "Who benefits if entity X defaults?")
3. **Custom prompts** - Allow users to specify custom KYC questions
4. **Cached contexts** - Store assembled contexts to reduce token usage on repeated queries
5. **Confidence scoring** - LLM confidence + graph coverage scoring
6. **Explanation traces** - Show which graph nodes/edges contributed to each conclusion

---

## References

- **Neo4j Graph Queries:** See `src/retrieval.py`
- **Context Assembly:** See `src/rag.py`
- **Example Usage:** See `examples/graphrag_example.py`
