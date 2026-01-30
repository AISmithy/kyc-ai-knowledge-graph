# GraphRAG Quick Start Guide

Get LLM-powered KYC question answering up and running in 5 minutes.

## Prerequisites

- Python 3.8+
- Neo4j Aura instance with GLEIF data loaded
- Claude API key OR OpenAI API key

## Step 1: Install Dependencies

```bash
cd kyc-ai-knowledge-graph
pip install -r requirements.txt
```

This installs both `anthropic` and `openai`. You only need one.

## Step 2: Configure Environment

Create/update `.env`:

```bash
# Neo4j Aura
NEO4J_URI=neo4j+s://your-instance.databases.neo4j.io
NEO4J_USER=neo4j
NEO4J_PASSWORD=your-password

# Choose ONE:

# Option A: Claude (recommended)
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxxxxxxx

# Option B: OpenAI
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxx
```

Get API keys:
- **Claude**: [console.anthropic.com](https://console.anthropic.com)
- **OpenAI**: [platform.openai.com/api-keys](https://platform.openai.com/api-keys)

## Step 3: Verify Setup

```bash
# Test imports and Neo4j connection
python examples/graphrag_example.py
```

Expected output:
```
✓ Neo4j connection verified
✓ GraphRAG initialized (Claude)
Running KYC review for LEI: 5493001KJTIGYAFGKS75
1. Beneficial Owner Identification
[LLM-generated analysis...]
```

## Step 4: Use GraphRAG in Your Code

### Minimal Example

```python
from neo4j_module.connector import Neo4jConnection
from graphrag import GraphRAG
import os
from dotenv import load_dotenv

load_dotenv()

# Connect to Neo4j
conn = Neo4jConnection(
    os.getenv("NEO4J_URI"),
    os.getenv("NEO4J_USER"),
    os.getenv("NEO4J_PASSWORD")
)

# Initialize GraphRAG
graphrag = GraphRAG(conn, model="claude-3-sonnet")

# Ask a KYC question
lei = "5493001KJTIGYAFGKS75"  # Replace with real LEI
result = graphrag.identify_beneficial_owners(lei)

print(result.answer)
```

### Full KYC Review

```python
# Run all checks at once
review = graphrag.comprehensive_kyc_review(lei)

# Get formatted report
report = graphrag.format_report(review)
print(report)

# Access individual results
print(review["beneficial_owners"].answer)
print(review["jurisdiction_risk"].answer)
print(review["adverse_media"].answer)
```

### With Error Handling

```python
try:
    conn = Neo4jConnection(uri, user, password)
    conn.verify_connection()
    print("✓ Connected to Neo4j")
except Exception as e:
    print(f"✗ Connection failed: {e}")
    exit(1)

try:
    graphrag = GraphRAG(conn, model="claude-3-sonnet")
    print("✓ GraphRAG ready")
except ImportError as e:
    print(f"✗ LLM library missing: {e}")
    exit(1)

# Now use graphrag...
review = graphrag.comprehensive_kyc_review(lei)
```

## Step 5: Available Methods

### Method 1: Identify Beneficial Owners

```python
result = graphrag.identify_beneficial_owners(
    lei="5493001KJTIGYAFGKS75",
    ownership_threshold=25.0  # Only show owners > 25%
)
print(result.answer)
```

**Returns:** Beneficial owners, red flags (circular structures, missing data), recommendation level

### Method 2: Assess Jurisdiction Risk

```python
result = graphrag.assess_jurisdiction_risk(
    lei="5493001KJTIGYAFGKS75",
    risk_countries=["IR", "KP", "SY", "SD", "CU", "VE"]  # Default
)
print(result.answer)
```

**Returns:** Risk level (LOW/MEDIUM/HIGH/CRITICAL), exposure areas, recommended actions

### Method 3: Flag Adverse Media

```python
result = graphrag.flag_adverse_media(lei="5493001KJTIGYAFGKS75")
print(result.answer)
```

**Returns:** Media mention summary, severity level, follow-up recommendations

### Method 4: Comprehensive Review (All Checks)

```python
review = graphrag.comprehensive_kyc_review(lei="5493001KJTIGYAFGKS75")

# Access results
for check_name, answer in review.items():
    print(f"\n{check_name.upper()}:")
    print(answer.answer)
    if answer.usage:
        print(f"Tokens: {answer.usage}")

# Or get formatted report
report = graphrag.format_report(review)
print(report)
```

## Common Questions

### Q: Which LLM should I use?

**Claude 3 Sonnet** (recommended):
- Best for compliance tasks
- Good instruction following
- Fast responses (~2-3 sec)
- Cost: ~$0.006 per comprehensive review

**GPT-4**:
- Most capable reasoning
- Better at complex analysis
- Slower (~5-10 sec)
- Cost: ~$0.040 per comprehensive review

**GPT-3.5 Turbo**:
- Fast and cheap
- Less sophisticated reasoning
- Cost: ~$0.015 per comprehensive review

### Q: How much will this cost?

For 1000 comprehensive reviews:
- Claude 3: ~$6
- GPT-3.5: ~$15
- GPT-4: ~$40

Each review costs: input tokens × 0.003 + output tokens × 0.015 (Claude prices)

### Q: What if the LLM library isn't installed?

GraphRAG gracefully handles missing libraries:

```python
# If anthropic not installed but you try claude:
graphrag = GraphRAG(conn, model="claude-3-sonnet")
# → ImportError: anthropic not installed
```

Install missing library:
```bash
pip install anthropic  # For Claude
pip install openai     # For OpenAI
```

### Q: Can I use a different LLM (local/Ollama)?

Currently supported:
- ✅ Claude 3 (Anthropic)
- ✅ GPT-4, GPT-3.5-turbo (OpenAI)

To add support for local models:
1. Create method like `_prompt_local()` in `src/graphrag.py`
2. Add to `_call_llm()` router
3. Update model validation in `_validate_model()`

See `docs/GRAPHRAG.md` for extension examples.

### Q: Why is my Neo4j connection failing?

Check `.env`:
```bash
# Verify URI format (should be neo4j+s://)
NEO4J_URI=neo4j+s://xxx.databases.neo4j.io

# Test connection directly
python -c "
import os
from dotenv import load_dotenv
from neo4j_module.connector import Neo4jConnection

load_dotenv()
conn = Neo4jConnection(
    os.getenv('NEO4J_URI'),
    os.getenv('NEO4J_USER'),
    os.getenv('NEO4J_PASSWORD')
)
conn.verify_connection()
print('✓ Connected!')
"
```

### Q: No entities found in database?

Load GLEIF data first:
```bash
# Run MVP pipeline
python -m data_loader.main --nrows 1000 --neo4j
```

Or run test with sample data:
```bash
python test_mvp_simple.py
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `ModuleNotFoundError: No module named 'anthropic'` | `pip install anthropic` |
| `ModuleNotFoundError: No module named 'openai'` | `pip install openai` |
| `ANTHROPIC_API_KEY not found` | Add to .env: `ANTHROPIC_API_KEY=sk-ant-...` |
| `Neo4j connection failed` | Check URI, user, password in .env |
| `No entities found in database` | Load GLEIF data first: `python -m data_loader.main --neo4j` |
| `LLM returning generic answers` | Ensure graph has sufficient data (beneficial owner relationships) |

## Next: Full Documentation

For detailed API docs, architecture, use cases, and enhancements, see:

- **Full GraphRAG docs**: `docs/GRAPHRAG.md`
- **Implementation details**: `docs/GRAPHRAG_IMPLEMENTATION.md`
- **Example script**: `examples/graphrag_example.py`
- **Tests**: `tests/test_graphrag.py`

## Example: Complete KYC Workflow

```python
#!/usr/bin/env python3
"""Complete KYC review workflow."""

import os
import sys
from dotenv import load_dotenv
from neo4j_module.connector import Neo4jConnection
from graphrag import GraphRAG

load_dotenv()

def kyc_review_workflow(lei: str):
    """Run complete KYC review for a single entity."""
    
    # Setup
    conn = Neo4jConnection(
        os.getenv("NEO4J_URI"),
        os.getenv("NEO4J_USER"),
        os.getenv("NEO4J_PASSWORD"),
    )
    conn.verify_connection()
    
    graphrag = GraphRAG(conn, model="claude-3-sonnet")
    
    # Run review
    print(f"Running KYC review for {lei}...")
    review = graphrag.comprehensive_kyc_review(lei)
    
    # Generate report
    report = graphrag.format_report(review)
    print(report)
    
    # Make decision
    for check_name, answer in review.items():
        if "ESCALATE" in answer.answer or "CRITICAL" in answer.answer:
            print(f"\n⚠️ ALERT: {check_name} requires escalation")
            return "ESCALATE"
    
    print("\n✓ KYC review complete - approved for onboarding")
    return "APPROVED"

if __name__ == "__main__":
    lei = sys.argv[1] if len(sys.argv) > 1 else "5493001KJTIGYAFGKS75"
    decision = kyc_review_workflow(lei)
    sys.exit(0 if decision == "APPROVED" else 1)
```

Run it:
```bash
python kyc_workflow.py 5493001KJTIGYAFGKS75
```

## Summary

You now have LLM-powered KYC question answering! 

**Key methods:**
- `graphrag.identify_beneficial_owners()` - BO analysis
- `graphrag.assess_jurisdiction_risk()` - Risk scoring
- `graphrag.flag_adverse_media()` - Adverse media check
- `graphrag.comprehensive_kyc_review()` - All 3 checks

**Supported LLMs:**
- Claude 3 Sonnet (recommended)
- GPT-4 / GPT-3.5-turbo

**Cost:** ~$0.006/review (Claude) to $0.040 (GPT-4)

For more, see full docs: `docs/GRAPHRAG.md`
