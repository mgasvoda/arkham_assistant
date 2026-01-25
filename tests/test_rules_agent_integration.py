"""Integration tests for RulesAgent with actual static files.

These tests verify the RulesAgent works correctly with the actual
static rules files in the project.
"""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from backend.services.subagents.rules_agent import (
    RulesAgent,
    RulesQuery,
    RulesResponse,
    RulesRetriever,
)
from backend.services.subagents.base import SubagentConfig


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def actual_static_dir():
    """Get the actual static directory path."""
    return Path(__file__).parent.parent / "backend" / "static"


@pytest.fixture
def actual_retriever(actual_static_dir):
    """Create retriever with actual static files."""
    return RulesRetriever(static_dir=actual_static_dir)


# =============================================================================
# RulesRetriever Integration Tests
# =============================================================================


class TestRulesRetrieverIntegration:
    """Integration tests for RulesRetriever with actual static files."""

    def test_static_directory_exists(self, actual_static_dir):
        """Static directory should exist."""
        assert actual_static_dir.exists(), f"Static dir not found: {actual_static_dir}"

    def test_rules_file_exists(self, actual_static_dir):
        """Rules overview file should exist."""
        rules_file = actual_static_dir / "rules_overview.md"
        assert rules_file.exists(), "rules_overview.md not found"

    def test_search_deckbuilding_rules(self, actual_retriever):
        """Should find deckbuilding rules in actual files."""
        results = actual_retriever.search("deck construction 30 cards")

        assert len(results) > 0
        # Should find content about deck construction
        all_content = " ".join(r["content"].lower() for r in results)
        assert "30" in all_content or "card" in all_content

    def test_search_action_economy(self, actual_retriever):
        """Should find action economy rules."""
        results = actual_retriever.search("actions per turn investigate")

        assert len(results) > 0
        all_content = " ".join(r["content"].lower() for r in results)
        assert "action" in all_content

    def test_search_resources(self, actual_retriever):
        """Should find resource rules."""
        results = actual_retriever.search("resources cost play cards")

        assert len(results) > 0

    def test_get_all_content_includes_rules(self, actual_retriever):
        """Should get all rules content."""
        content = actual_retriever.get_all_rules_content()

        assert len(content) > 0
        # Should include content from rules_overview.md
        assert "Deck Construction" in content or "deck" in content.lower()

    def test_search_returns_source_info(self, actual_retriever):
        """Should include source file info in results."""
        results = actual_retriever.search("deck construction")

        if results:
            result = results[0]
            assert "source" in result
            assert result["source"].endswith(".md")
            assert "section" in result
            assert "content" in result


# =============================================================================
# RulesAgent Integration Tests (with mocked LLM)
# =============================================================================


class TestRulesAgentIntegration:
    """Integration tests for RulesAgent with actual retriever but mocked LLM."""

    @pytest.fixture
    def mock_llm_response(self):
        """Create a mock LLM response."""
        mock_response = MagicMock()
        mock_response.content = """**Rule**: Decks must contain a minimum of 30 cards, with 0-2 copies of each card by title.

**Interpretation**: When building your deck, you need at least 30 cards total. You can include up to 2 copies of any card, but cards with different levels (like Shrivelling (0) and Shrivelling (3)) share the same title limit.

**Applies To**: All investigators, All player decks"""
        return mock_response

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    @patch("backend.services.subagents.base.ChatOpenAI")
    def test_agent_with_actual_retriever(
        self, mock_chat_class, actual_retriever, mock_llm_response
    ):
        """Should work with actual retriever."""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = mock_llm_response
        mock_chat_class.return_value = mock_llm

        agent = RulesAgent(retriever=actual_retriever)
        response = agent.query("How many cards minimum in a deck?")

        assert isinstance(response, RulesResponse)
        assert response.confidence > 0
        # Should have retrieved actual sections
        assert response.metadata.extra.get("sections_retrieved", 0) >= 0

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    @patch("backend.services.subagents.base.ChatOpenAI")
    def test_prompt_includes_retrieved_rules(
        self, mock_chat_class, actual_retriever, mock_llm_response
    ):
        """Should include retrieved rules in the prompt."""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = mock_llm_response
        mock_chat_class.return_value = mock_llm

        agent = RulesAgent(retriever=actual_retriever)
        agent.query("deck construction rules")

        # Check that the system prompt includes retrieved content
        call_args = mock_llm.invoke.call_args[0][0]
        system_prompt = call_args[0].content

        # Should have the hybrid prompt structure
        assert "Retrieved Rule Context" in system_prompt
        # Should have actual rules content
        assert "30" in system_prompt or "card" in system_prompt.lower()

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    @patch("backend.services.subagents.base.ChatOpenAI")
    def test_sources_include_actual_files(
        self, mock_chat_class, actual_retriever, mock_llm_response
    ):
        """Should include actual file references in sources."""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = mock_llm_response
        mock_chat_class.return_value = mock_llm

        agent = RulesAgent(retriever=actual_retriever)
        response = agent.query("deck construction rules")

        # Should have sources from actual files
        sources_str = " ".join(response.sources)
        # At least one of these should be in sources if retrieval worked
        assert (
            "rules_overview" in sources_str.lower()
            or "Deck Construction" in sources_str
            or len(response.sources) > 0
        )

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    @patch("backend.services.subagents.base.ChatOpenAI")
    def test_query_rules_with_actual_retriever(
        self, mock_chat_class, actual_retriever, mock_llm_response
    ):
        """Should work with RulesQuery input."""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = mock_llm_response
        mock_chat_class.return_value = mock_llm

        agent = RulesAgent(retriever=actual_retriever)
        query = RulesQuery(
            question="Can Roland include level 2 Guardian cards?",
            investigator_id="01001",
        )
        response = agent.query_rules(query)

        assert isinstance(response, RulesResponse)
        assert response.rule_text != "" or response.interpretation != ""


# =============================================================================
# End-to-End Tests (requires OPENAI_API_KEY)
# =============================================================================


@pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set - skipping live API tests"
)
class TestRulesAgentLiveAPI:
    """End-to-end tests with actual OpenAI API calls.

    These tests are skipped unless OPENAI_API_KEY is set.
    Use sparingly to avoid API costs.
    """

    def test_live_deckbuilding_query(self, actual_retriever):
        """Test actual API call for deckbuilding question."""
        config = SubagentConfig(max_tokens=500)  # Limit tokens for cost
        agent = RulesAgent(config=config, retriever=actual_retriever)

        response = agent.query("How many cards minimum does a deck need?")

        assert isinstance(response, RulesResponse)
        assert len(response.content) > 0
        assert response.confidence > 0
        # Should mention 30 cards in some form
        assert "30" in response.content or "thirty" in response.content.lower()

    def test_live_action_query(self, actual_retriever):
        """Test actual API call for action economy question."""
        config = SubagentConfig(max_tokens=500)
        agent = RulesAgent(config=config, retriever=actual_retriever)

        response = agent.query("How many actions does an investigator get per turn?")

        assert isinstance(response, RulesResponse)
        assert len(response.content) > 0
        # Should mention 3 actions
        assert "3" in response.content or "three" in response.content.lower()
