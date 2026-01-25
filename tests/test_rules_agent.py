"""Unit tests for the RulesAgent with hybrid retrieval."""

import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

import pytest

from backend.models.subagent_models import SubagentMetadata, SubagentResponse
from backend.services.subagents.rules_agent import (
    RulesAgent,
    RulesQuery,
    RulesResponse,
    RulesRetriever,
    create_rules_agent,
)
from backend.services.subagents.base import SubagentConfig


# =============================================================================
# RulesQuery Tests
# =============================================================================


class TestRulesQuery:
    """Tests for RulesQuery input schema."""

    def test_minimal_query(self):
        """Should accept just a question."""
        query = RulesQuery(question="Can Roland include Shrivelling?")
        assert query.question == "Can Roland include Shrivelling?"
        assert query.investigator_id is None
        assert query.card_ids is None

    def test_full_query(self):
        """Should accept all fields."""
        query = RulesQuery(
            question="Can Roland include these cards?",
            investigator_id="01001",
            card_ids=["01016", "01017"],
        )
        assert query.question == "Can Roland include these cards?"
        assert query.investigator_id == "01001"
        assert query.card_ids == ["01016", "01017"]

    def test_requires_question(self):
        """Should require question field."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            RulesQuery()


# =============================================================================
# RulesResponse Tests
# =============================================================================


class TestRulesResponse:
    """Tests for RulesResponse output schema."""

    def test_minimal_response(self):
        """Should create with required fields."""
        response = RulesResponse(
            content="Roland can include Guardian and Seeker cards.",
            metadata=SubagentMetadata(agent_type="rules"),
        )
        assert response.content == "Roland can include Guardian and Seeker cards."
        assert response.rule_text == ""
        assert response.interpretation == ""
        assert response.applies_to == []

    def test_full_response(self):
        """Should include all rules-specific fields."""
        response = RulesResponse(
            content="Full response text",
            confidence=0.9,
            sources=["Deck Construction Rules"],
            metadata=SubagentMetadata(
                agent_type="rules",
                query_type="legality_check",
            ),
            rule_text="30 cards minimum, 0-2 copies per card",
            interpretation="Roland can include up to 2 copies of most cards",
            applies_to=["Roland Banks", "All investigators"],
        )
        assert response.confidence == 0.9
        assert response.rule_text == "30 cards minimum, 0-2 copies per card"
        assert response.interpretation == "Roland can include up to 2 copies of most cards"
        assert "Roland Banks" in response.applies_to

    def test_from_base_response(self):
        """Should convert from base SubagentResponse."""
        base = SubagentResponse(
            content="Base content",
            confidence=0.8,
            sources=["Source 1"],
            metadata=SubagentMetadata(agent_type="rules"),
        )
        rules_response = RulesResponse.from_base_response(
            base,
            rule_text="The rule text",
            interpretation="The interpretation",
            applies_to=["Card A", "Card B"],
        )
        assert rules_response.content == "Base content"
        assert rules_response.confidence == 0.8
        assert rules_response.rule_text == "The rule text"
        assert rules_response.interpretation == "The interpretation"
        assert rules_response.applies_to == ["Card A", "Card B"]

    def test_error_response(self):
        """Should create error response."""
        response = RulesResponse.error_response("Something went wrong", "rules")
        assert response.content == "Something went wrong"
        assert response.confidence == 0.0
        assert response.metadata.agent_type == "rules"
        assert response.metadata.query_type == "error"
        assert response.metadata.extra.get("error") is True
        assert response.rule_text == ""
        assert response.applies_to == []


# =============================================================================
# RulesRetriever Tests
# =============================================================================


class TestRulesRetriever:
    """Tests for RulesRetriever keyword search."""

    @pytest.fixture
    def temp_static_dir(self):
        """Create a temporary directory with test rules files."""
        with TemporaryDirectory() as tmpdir:
            static_dir = Path(tmpdir)

            # Create test rules file
            rules_file = static_dir / "rules_overview.md"
            rules_file.write_text("""# Arkham Horror LCG Rules

## Deck Construction

- 30 cards minimum
- 0-2 copies of each card (by title, not by level)
- Must respect investigator's deckbuilding restrictions
- Include required signature cards

## Action Economy

- Each investigator gets 3 actions per turn
- Actions: Investigate, Move, Fight, Evade, Draw, Resource, Play card

## Experience and Upgrades

- Earn XP by completing scenarios
- Spend XP to upgrade cards to higher levels
- Level 0 cards are free, higher levels cost XP
""")

            # Create test meta file
            meta_file = static_dir / "meta_trends.md"
            meta_file.write_text("""# Meta Trends

## Popular Archetypes

- Guardian: Combat focused, tank role
- Seeker: Investigation focused, clue gathering
- Mystic: Spell-based, flexible
""")

            yield static_dir

    def test_search_finds_relevant_sections(self, temp_static_dir):
        """Should find sections matching keywords."""
        retriever = RulesRetriever(static_dir=temp_static_dir)
        results = retriever.search("deck construction copies")

        assert len(results) > 0
        # Should find the Deck Construction section
        section_names = [r["section"] for r in results]
        assert any("Deck Construction" in name for name in section_names)

    def test_search_returns_content(self, temp_static_dir):
        """Should return section content."""
        retriever = RulesRetriever(static_dir=temp_static_dir)
        results = retriever.search("actions")

        assert len(results) > 0
        # Should contain action-related content
        all_content = " ".join(r["content"] for r in results)
        assert "actions" in all_content.lower() or "action" in all_content.lower()

    def test_search_limits_results(self, temp_static_dir):
        """Should respect max_sections limit."""
        retriever = RulesRetriever(static_dir=temp_static_dir)
        results = retriever.search("card", max_sections=2)

        assert len(results) <= 2

    def test_search_scores_heading_matches_higher(self, temp_static_dir):
        """Should rank heading matches higher than content matches."""
        retriever = RulesRetriever(static_dir=temp_static_dir)
        results = retriever.search("experience upgrades")

        assert len(results) > 0
        # Experience section should be ranked high
        top_section = results[0]["section"]
        assert "Experience" in top_section or "Upgrade" in top_section

    def test_search_empty_query_returns_results(self, temp_static_dir):
        """Should handle empty query gracefully."""
        retriever = RulesRetriever(static_dir=temp_static_dir)
        results = retriever.search("")

        # May return results based on topic keywords or be empty
        assert isinstance(results, list)

    def test_get_all_rules_content(self, temp_static_dir):
        """Should concatenate all rules content."""
        retriever = RulesRetriever(static_dir=temp_static_dir)
        content = retriever.get_all_rules_content()

        assert "Deck Construction" in content
        assert "Meta Trends" in content
        assert "30 cards" in content

    def test_handles_missing_directory(self):
        """Should handle missing static directory gracefully."""
        retriever = RulesRetriever(static_dir=Path("/nonexistent/path"))
        results = retriever.search("anything")

        assert results == []

    def test_extract_keywords(self, temp_static_dir):
        """Should extract relevant keywords from query."""
        retriever = RulesRetriever(static_dir=temp_static_dir)
        keywords = retriever._extract_keywords("can roland include level 2 guardian cards")

        assert "level" in keywords or "guardian" in keywords
        # Should also extract topic keywords
        assert len(keywords) > 0


# =============================================================================
# RulesAgent Tests
# =============================================================================


class TestRulesAgent:
    """Tests for RulesAgent with mocked LLM."""

    @pytest.fixture
    def mock_llm_response(self):
        """Create a mock LLM response."""
        mock_response = MagicMock()
        mock_response.content = """**Rule**: Investigators must include at least 30 cards and can include 0-2 copies of each card by title.

**Interpretation**: Roland Banks can include up to 2 copies of most Guardian and Seeker cards level 0-2, respecting his deckbuilding restrictions.

**Applies To**: Roland Banks, All Guardian investigators"""
        return mock_response

    @pytest.fixture
    def mock_retriever(self):
        """Create a mock retriever with test data."""
        retriever = MagicMock(spec=RulesRetriever)
        retriever.search.return_value = [
            {
                "source": "rules_overview.md",
                "section": "Deck Construction",
                "content": "30 cards minimum, 0-2 copies per card",
            }
        ]
        retriever.get_all_rules_content.return_value = "All rules content here"
        return retriever

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    @patch("backend.services.subagents.base.ChatOpenAI")
    def test_agent_initialization(self, mock_chat, mock_retriever):
        """Should initialize with retriever."""
        agent = RulesAgent(retriever=mock_retriever)

        assert agent.agent_type == "rules"
        assert agent.retriever is mock_retriever

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    @patch("backend.services.subagents.base.ChatOpenAI")
    def test_query_returns_rules_response(
        self, mock_chat_class, mock_retriever, mock_llm_response
    ):
        """Should return RulesResponse with structured fields."""
        # Setup mock
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = mock_llm_response
        mock_chat_class.return_value = mock_llm

        agent = RulesAgent(retriever=mock_retriever)
        response = agent.query("Can Roland include Shrivelling?")

        assert isinstance(response, RulesResponse)
        assert response.rule_text != ""
        assert response.interpretation != ""
        assert len(response.applies_to) > 0

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    @patch("backend.services.subagents.base.ChatOpenAI")
    def test_query_includes_retrieved_sections_in_sources(
        self, mock_chat_class, mock_retriever, mock_llm_response
    ):
        """Should include retrieved sections in sources."""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = mock_llm_response
        mock_chat_class.return_value = mock_llm

        agent = RulesAgent(retriever=mock_retriever)
        response = agent.query("deck construction rules")

        # Should have sources from retrieval
        assert any("rules_overview.md" in s for s in response.sources)

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    @patch("backend.services.subagents.base.ChatOpenAI")
    def test_query_with_context(
        self, mock_chat_class, mock_retriever, mock_llm_response
    ):
        """Should use context in prompt."""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = mock_llm_response
        mock_chat_class.return_value = mock_llm

        agent = RulesAgent(retriever=mock_retriever)
        response = agent.query(
            "Can this investigator include Shrivelling?",
            context={"investigator_name": "Roland Banks"},
        )

        # Verify LLM was called
        assert mock_llm.invoke.called
        # Check prompt includes context
        call_args = mock_llm.invoke.call_args[0][0]
        system_prompt = call_args[0].content
        assert "Roland Banks" in system_prompt

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    @patch("backend.services.subagents.base.ChatOpenAI")
    def test_query_rules_method(
        self, mock_chat_class, mock_retriever, mock_llm_response
    ):
        """Should accept RulesQuery input schema."""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = mock_llm_response
        mock_chat_class.return_value = mock_llm

        agent = RulesAgent(retriever=mock_retriever)
        rules_query = RulesQuery(
            question="Can Roland include this card?",
            investigator_id="01001",
            card_ids=["01016"],
        )
        response = agent.query_rules(rules_query)

        assert isinstance(response, RulesResponse)

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    @patch("backend.services.subagents.base.ChatOpenAI")
    def test_metadata_includes_hybrid_retrieval_flag(
        self, mock_chat_class, mock_retriever, mock_llm_response
    ):
        """Should indicate hybrid retrieval was used."""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = mock_llm_response
        mock_chat_class.return_value = mock_llm

        agent = RulesAgent(retriever=mock_retriever)
        response = agent.query("deck construction rules")

        assert response.metadata.extra.get("hybrid_retrieval") is True
        assert response.metadata.extra.get("sections_retrieved") == 1

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    @patch("backend.services.subagents.base.ChatOpenAI")
    def test_handles_llm_error(self, mock_chat_class, mock_retriever):
        """Should return error response on LLM failure."""
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = Exception("API Error")
        mock_chat_class.return_value = mock_llm

        agent = RulesAgent(retriever=mock_retriever)
        response = agent.query("any question")

        assert isinstance(response, RulesResponse)
        assert "failed" in response.content.lower() or "error" in response.content.lower()
        assert response.confidence == 0.0


# =============================================================================
# Query Type Classification Tests
# =============================================================================


class TestQueryTypeClassification:
    """Tests for query type classification."""

    @pytest.fixture
    def agent(self, mock_retriever):
        """Create agent with mocked dependencies."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch("backend.services.subagents.base.ChatOpenAI"):
                return RulesAgent(retriever=mock_retriever)

    @pytest.fixture
    def mock_retriever(self):
        retriever = MagicMock(spec=RulesRetriever)
        retriever.search.return_value = []
        return retriever

    def test_legality_check_query(self, agent):
        """Should classify legality questions."""
        assert agent._determine_query_type("Can Roland include Shrivelling?") == "legality_check"
        assert agent._determine_query_type("Is Machete legal for Wendy?") == "legality_check"

    def test_xp_rules_query(self, agent):
        """Should classify XP questions."""
        assert agent._determine_query_type("How much XP does Shrivelling (5) cost?") == "xp_rules"
        assert agent._determine_query_type("What level cards can Roland access?") == "xp_rules"

    def test_taboo_query(self, agent):
        """Should classify taboo questions."""
        assert agent._determine_query_type("Is Machete on the taboo list?") == "taboo_check"

    def test_signature_query(self, agent):
        """Should classify signature card questions."""
        assert agent._determine_query_type("What is Roland's signature card?") == "signature_rules"

    def test_weakness_query(self, agent):
        """Should classify weakness questions."""
        assert agent._determine_query_type("How do basic weaknesses work?") == "weakness_rules"

    def test_class_access_query(self, agent):
        """Should classify class access questions."""
        assert agent._determine_query_type("What classes can Roland access?") == "class_access"

    def test_general_query(self, agent):
        """Should default to general rules."""
        assert agent._determine_query_type("Tell me about the game") == "general_rules"


# =============================================================================
# Confidence Calculation Tests
# =============================================================================


class TestConfidenceCalculation:
    """Tests for confidence score calculation."""

    @pytest.fixture
    def agent(self, mock_retriever):
        """Create agent with mocked dependencies."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch("backend.services.subagents.base.ChatOpenAI"):
                return RulesAgent(retriever=mock_retriever)

    @pytest.fixture
    def mock_retriever(self):
        retriever = MagicMock(spec=RulesRetriever)
        retriever.search.return_value = []
        return retriever

    def test_high_confidence_with_definitive_language(self, agent):
        """Should give high confidence for definitive statements."""
        from backend.services.subagents.base import SubagentState

        state = SubagentState(query="test", context={"_retrieved_sections": []})
        content = "According to the rules, Roland cannot include Shrivelling."

        confidence = agent._calculate_confidence(content, state)
        assert confidence >= 0.7

    def test_higher_confidence_with_retrieved_sections(self, agent):
        """Should boost confidence when sections were retrieved."""
        from backend.services.subagents.base import SubagentState

        state = SubagentState(
            query="test",
            context={"_retrieved_sections": [{"section": "Test", "content": "test"}]},
        )
        content = "The answer is yes."

        confidence = agent._calculate_confidence(content, state)
        assert confidence > 0.5

    def test_lower_confidence_with_uncertainty(self, agent):
        """Should lower confidence for uncertain language."""
        from backend.services.subagents.base import SubagentState

        state = SubagentState(query="test", context={"_retrieved_sections": []})
        content = "I'm not sure, but it might be allowed."

        confidence = agent._calculate_confidence(content, state)
        assert confidence < 0.5


# =============================================================================
# Factory Function Tests
# =============================================================================


class TestFactoryFunction:
    """Tests for create_rules_agent factory."""

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    @patch("backend.services.subagents.base.ChatOpenAI")
    def test_create_rules_agent_default(self, mock_chat):
        """Should create agent with default config."""
        agent = create_rules_agent()

        assert isinstance(agent, RulesAgent)
        assert agent.agent_type == "rules"

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    @patch("backend.services.subagents.base.ChatOpenAI")
    def test_create_rules_agent_with_config(self, mock_chat):
        """Should accept custom config."""
        config = SubagentConfig(temperature=0.5, max_tokens=1024)
        agent = create_rules_agent(config=config)

        assert agent.config.temperature == 0.5
        assert agent.config.max_tokens == 1024

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    @patch("backend.services.subagents.base.ChatOpenAI")
    def test_create_rules_agent_with_retriever(self, mock_chat):
        """Should accept custom retriever."""
        mock_retriever = MagicMock(spec=RulesRetriever)
        agent = create_rules_agent(retriever=mock_retriever)

        assert agent.retriever is mock_retriever


# =============================================================================
# Response Parsing Tests
# =============================================================================


class TestResponseParsing:
    """Tests for LLM response parsing."""

    @pytest.fixture
    def agent(self):
        """Create agent with mocked dependencies."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch("backend.services.subagents.base.ChatOpenAI"):
                mock_retriever = MagicMock(spec=RulesRetriever)
                mock_retriever.search.return_value = []
                return RulesAgent(retriever=mock_retriever)

    def test_parses_structured_response(self, agent):
        """Should parse structured markdown response."""
        content = """**Rule**: Deck minimum is 30 cards.

**Interpretation**: You must have at least 30 cards in your deck.

**Applies To**: All investigators, All decks"""

        rule_text, interpretation, applies_to = agent._parse_llm_response(content)

        assert "30 cards" in rule_text
        assert "at least 30 cards" in interpretation
        assert len(applies_to) >= 2

    def test_handles_unstructured_response(self, agent):
        """Should handle responses without structure."""
        content = "Roland can include Guardian and Seeker cards level 0-2."

        rule_text, interpretation, applies_to = agent._parse_llm_response(content)

        # Should fall back to using content as interpretation
        assert interpretation == content
        assert rule_text == ""

    def test_parses_applies_to_list(self, agent):
        """Should parse comma-separated applies_to."""
        content = """**Rule**: Test rule

**Interpretation**: Test interpretation

**Applies To**: Roland Banks, Agnes Baker, All Guardians"""

        _, _, applies_to = agent._parse_llm_response(content)

        assert "Roland Banks" in applies_to
        assert "Agnes Baker" in applies_to
