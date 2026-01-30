"""
GraphRAG: Graph-augmented retrieval with LLM reasoning for KYC workflows.

This module combines Neo4j graph queries with Claude/OpenAI LLM to answer
structured KYC questions: beneficial owner identification, risk assessment,
jurisdiction screening, adverse media flagging, etc.

Each question type has a dedicated handler that:
1. Executes deterministic graph queries
2. Assembles context from retrieved data
3. Prompts LLM with structured instruction + context
4. Parses and returns structured answer
"""

import os
import json
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from neo4j_module.connector import Neo4jConnection
from retrieval import (
    get_direct_parent,
    get_ultimate_parent,
    traverse_beneficial_ownership_chain,
    jurisdiction_risk_join,
)

logger = logging.getLogger(__name__)

# Check for LLM availability
try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    logger.warning("anthropic not installed; Claude prompts will be disabled")

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logger.warning("openai not installed; OpenAI prompts will be disabled")


@dataclass
class KYCAnswer:
    """Result of a KYC question answered by GraphRAG."""
    question: str
    answer: str
    context: Dict[str, Any]
    model: str
    usage: Optional[Dict[str, int]] = None


class GraphRAG:
    """Graph-augmented LLM reasoning for KYC."""

    def __init__(self, conn: Neo4jConnection, model: str = "claude-3-sonnet"):
        """
        Initialize GraphRAG.

        Args:
            conn: Neo4jConnection instance
            model: "claude-3-sonnet", "claude-3-opus", "gpt-4", "gpt-3.5-turbo"
        """
        self.conn = conn
        self.model = model
        self._validate_model()

    def _validate_model(self) -> None:
        """Check that the specified model is available."""
        if self.model.startswith("claude"):
            if not ANTHROPIC_AVAILABLE:
                raise ImportError(
                    f"Model {self.model} requires 'anthropic' package. "
                    "Install: pip install anthropic"
                )
        elif self.model.startswith("gpt"):
            if not OPENAI_AVAILABLE:
                raise ImportError(
                    f"Model {self.model} requires 'openai' package. "
                    "Install: pip install openai"
                )
        else:
            raise ValueError(f"Unknown model: {self.model}")

    def _prompt_claude(self, system: str, user_message: str) -> tuple[str, Dict[str, int]]:
        """Call Claude API."""
        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        response = client.messages.create(
            model=self.model,
            max_tokens=1024,
            system=system,
            messages=[{"role": "user", "content": user_message}],
        )
        text = response.content[0].text
        usage = {"input_tokens": response.usage.input_tokens, "output_tokens": response.usage.output_tokens}
        return text, usage

    def _prompt_openai(self, system: str, user_message: str) -> tuple[str, Dict[str, int]]:
        """Call OpenAI API."""
        client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            model=self.model,
            max_tokens=1024,
            system_prompt=system,
            messages=[{"role": "user", "content": user_message}],
        )
        text = response.choices[0].message.content
        usage = {"input_tokens": response.usage.prompt_tokens, "output_tokens": response.usage.completion_tokens}
        return text, usage

    def _call_llm(self, system: str, user_message: str) -> tuple[str, Dict[str, int]]:
        """Route to appropriate LLM."""
        if self.model.startswith("claude"):
            return self._prompt_claude(system, user_message)
        elif self.model.startswith("gpt"):
            return self._prompt_openai(system, user_message)
        else:
            raise ValueError(f"Unsupported model: {self.model}")

    def identify_beneficial_owners(self, lei: str, ownership_threshold: float = 25.0) -> KYCAnswer:
        """
        Identify beneficial owners of an entity.

        Uses LLM to reason about ownership chains and flag control structures.
        """
        # Gather context
        direct = get_direct_parent(self.conn, lei)
        ultimate = get_ultimate_parent(self.conn, lei)
        chains = traverse_beneficial_ownership_chain(
            self.conn, lei, threshold_pct=ownership_threshold, max_hops=10
        )

        context = {
            "lei": lei,
            "direct_parent": direct,
            "ultimate_parent": ultimate,
            "ownership_chains": chains[:5],  # Top 5 paths
            "threshold_pct": ownership_threshold,
        }

        chains_text = ""
        for i, chain in enumerate(context["ownership_chains"], 1):
            leis = " -> ".join(chain["leis"])
            chains_text += f"\nChain {i}: {leis}\n"
            for rel in chain["rels"][:3]:
                chains_text += f"  {rel['start']} owns {rel['end']}: {rel['ownership']}%\n"

        user_msg = f"""
Based on the ownership structure below, identify beneficial owners and flag any concerns.

Entity LEI: {lei}
Direct Parent: {direct.get('legalName', 'None') if direct else 'None'} ({direct.get('lei', '') if direct else ''})
Ultimate Parent: {ultimate.get('legalName', 'None') if ultimate else 'None'} ({ultimate.get('lei', '') if ultimate else ''})

Ownership Chains (threshold: {ownership_threshold}%):
{chains_text}

Provide:
1. List of identified beneficial owners with confidence
2. Any red flags (circular structures, missing data, etc.)
3. Recommendation (CLEAR / FURTHER_REVIEW / ESCALATE)
"""
        system_msg = "You are a KYC expert. Analyze ownership structures and identify beneficial owners."

        answer, usage = self._call_llm(system_msg, user_msg)

        return KYCAnswer(
            question=f"Who are the beneficial owners of {lei}?",
            answer=answer,
            context=context,
            model=self.model,
            usage=usage,
        )

    def assess_jurisdiction_risk(self, lei: str, risk_countries: Optional[List[str]] = None) -> KYCAnswer:
        """
        Assess jurisdiction risk exposure.

        Uses LLM to evaluate cross-border risk and compliance implications.
        """
        jr = jurisdiction_risk_join(self.conn, lei, risk_countries=risk_countries)

        context = {
            "lei": lei,
            "jurisdiction_risk_data": jr,
            "risk_countries": risk_countries or [],
        }

        user_msg = f"""
Assess the jurisdiction risk for this entity:

Entity: {jr.get('lei')} ({jr.get('name')})
Entity Jurisdiction: {jr.get('jurisdiction')}
High-Risk Neighbors: {jr.get('high_risk_neighbors', 0)}
Risk Countries Checked: {', '.join(risk_countries or ['IR', 'KP', 'SY', 'SD', 'CU', 'VE'])}

Provide:
1. Risk level (LOW / MEDIUM / HIGH / CRITICAL)
2. Key exposure areas
3. Recommended actions
"""
        system_msg = (
            "You are a compliance officer evaluating jurisdiction-based AML/CFT risk. "
            "Be concise and action-oriented."
        )

        answer, usage = self._call_llm(system_msg, user_msg)

        return KYCAnswer(
            question=f"What is the jurisdiction risk for {lei}?",
            answer=answer,
            context=context,
            model=self.model,
            usage=usage,
        )

    def flag_adverse_media(self, lei: str) -> KYCAnswer:
        """
        Check for adverse media and flag concerns.

        Queries AdverseMedia nodes linked to entity and uses LLM to assess severity.
        """
        cypher = """
        MATCH (e:LegalEntity {lei: $lei})-[:MENTIONED_IN]->(am:AdverseMedia)
        RETURN am.id, am.title, am.source, am.date
        LIMIT 20
        """
        with self.conn.get_session() as session:
            result = session.run(cypher, lei=lei)
            mentions = [dict(record) for record in result]

        context = {
            "lei": lei,
            "adverse_media_count": len(mentions),
            "mentions": mentions,
        }

        if not mentions:
            return KYCAnswer(
                question=f"Any adverse media for {lei}?",
                answer="No adverse media found.",
                context=context,
                model=self.model,
            )

        mentions_text = ""
        for m in mentions[:10]:
            mentions_text += f"\n- [{m.get('date', 'Unknown')}] {m.get('title')} (Source: {m.get('source')})"

        user_msg = f"""
Review adverse media mentions for entity {lei}:
{mentions_text}

Provide:
1. Summary of key issues
2. Severity assessment (LOW / MEDIUM / HIGH / CRITICAL)
3. Recommended follow-up actions
"""
        system_msg = (
            "You are a risk analyst reviewing media mentions. "
            "Assess relevance and severity for KYC/compliance purposes."
        )

        answer, usage = self._call_llm(system_msg, user_msg)

        return KYCAnswer(
            question=f"Any adverse media concerns for {lei}?",
            answer=answer,
            context=context,
            model=self.model,
            usage=usage,
        )

    def comprehensive_kyc_review(self, lei: str) -> Dict[str, KYCAnswer]:
        """
        Run all KYC checks and return comprehensive review.

        Returns dict of {check_name: KYCAnswer}
        """
        logger.info(f"Running comprehensive KYC review for {lei}")

        results = {
            "beneficial_owners": self.identify_beneficial_owners(lei),
            "jurisdiction_risk": self.assess_jurisdiction_risk(lei),
            "adverse_media": self.flag_adverse_media(lei),
        }

        return results

    def format_report(self, review: Dict[str, KYCAnswer]) -> str:
        """Format comprehensive review as readable report."""
        lines = [
            "=" * 80,
            "KYC COMPREHENSIVE REVIEW REPORT",
            "=" * 80,
        ]

        for check_name, answer in review.items():
            lines.append(f"\n{check_name.upper().replace('_', ' ')}")
            lines.append("-" * 40)
            lines.append(answer.answer)
            if answer.usage:
                lines.append(f"\n[Model: {answer.model} | Tokens: {answer.usage}]")

        return "\n".join(lines)
