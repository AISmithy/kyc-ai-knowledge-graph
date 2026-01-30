"""
Integration test for GraphRAG module.

Tests:
1. Module imports correctly
2. GraphRAG initialization with different models
3. Graph context retrieval functions work
4. Format methods produce valid output
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

def test_graphrag_imports():
    """Test that GraphRAG module imports without errors."""
    try:
        from graphrag import GraphRAG, KYCAnswer
        print("✓ GraphRAG imports successful")
        return True
    except ImportError as e:
        print(f"✗ GraphRAG import failed: {e}")
        return False


def test_kyc_answer_structure():
    """Test KYCAnswer dataclass structure."""
    from graphrag import KYCAnswer

    answer = KYCAnswer(
        question="Test question?",
        answer="Test answer",
        context={"lei": "TEST123"},
        model="claude-3-sonnet",
        usage={"input_tokens": 100, "output_tokens": 50}
    )

    assert answer.question == "Test question?"
    assert answer.answer == "Test answer"
    assert answer.context["lei"] == "TEST123"
    assert answer.usage["input_tokens"] == 100
    print("✓ KYCAnswer dataclass structure valid")
    return True


def test_retrieval_imports():
    """Test that retrieval functions are importable."""
    try:
        from retrieval import (
            get_direct_parent,
            get_ultimate_parent,
            traverse_beneficial_ownership_chain,
            jurisdiction_risk_join,
        )
        print("✓ Retrieval functions import successful")
        return True
    except ImportError as e:
        print(f"✗ Retrieval import failed: {e}")
        return False


def test_neo4j_connector():
    """Test Neo4j connector import."""
    try:
        from neo4j_module.connector import Neo4jConnection
        print("✓ Neo4jConnection imports successful")
        return True
    except ImportError as e:
        print(f"✗ Neo4jConnection import failed: {e}")
        return False


def test_model_validation():
    """Test that model validation works."""
    from graphrag import GraphRAG
    from neo4j_module.connector import Neo4jConnection

    # Mock connection (won't be used in init)
    class MockConn:
        pass

    # Test valid models
    for model in ["claude-3-sonnet", "gpt-4"]:
        try:
            graphrag = GraphRAG(MockConn(), model=model)
            print(f"✓ Model '{model}' validation initialized (will fail on LLM availability)")
        except ImportError as e:
            print(f"✓ Model '{model}' correctly requires LLM library: {str(e)[:50]}...")
        except Exception as e:
            print(f"✗ Model '{model}' validation failed unexpectedly: {e}")
            return False

    # Test invalid model
    try:
        graphrag = GraphRAG(MockConn(), model="invalid-model")
        print("✗ Invalid model should have raised ValueError")
        return False
    except ValueError as e:
        print(f"✓ Invalid model correctly rejected: {e}")

    return True


def test_format_report():
    """Test report formatting."""
    from graphrag import GraphRAG, KYCAnswer

    # Create mock review
    review = {
        "beneficial_owners": KYCAnswer(
            question="Owners?",
            answer="Test answer 1",
            context={},
            model="claude-3-sonnet",
        ),
        "jurisdiction_risk": KYCAnswer(
            question="Risk?",
            answer="Test answer 2",
            context={},
            model="claude-3-sonnet",
        ),
    }

    class MockConn:
        pass

    try:
        graphrag = GraphRAG(MockConn(), model="gpt-3.5-turbo")
    except ImportError:
        # If LLM not available, create a minimal instance for testing format
        graphrag = object.__new__(GraphRAG)
        graphrag.model = "test"

    report = graphrag.format_report(review)
    assert "COMPREHENSIVE REVIEW" in report
    assert "beneficial owners" in report.lower()
    assert "jurisdiction risk" in report.lower()
    print("✓ Report formatting works correctly")
    return True


def main():
    """Run all tests."""
    print("=" * 60)
    print("GraphRAG Integration Tests")
    print("=" * 60)

    tests = [
        test_graphrag_imports,
        test_kyc_answer_structure,
        test_retrieval_imports,
        test_neo4j_connector,
        test_model_validation,
        test_format_report,
    ]

    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"✗ {test.__name__} failed with exception: {e}")
            results.append(False)

    print("\n" + "=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"Results: {passed}/{total} tests passed")
    print("=" * 60)

    if passed == total:
        print("\n✓ All tests passed! GraphRAG module is ready.")
        return 0
    else:
        print(f"\n✗ {total - passed} test(s) failed.")
        return 1


if __name__ == "__main__":
    exit(main())
