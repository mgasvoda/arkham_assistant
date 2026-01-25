"""Unit tests for subagent Pydantic models."""

import pytest
from pydantic import ValidationError

from backend.models.subagent_models import SubagentMetadata, SubagentResponse


class TestSubagentMetadata:
    """Tests for SubagentMetadata model."""

    def test_requires_agent_type(self):
        """Should require agent_type field."""
        with pytest.raises(ValidationError):
            SubagentMetadata()

    def test_accepts_minimal_metadata(self):
        """Should accept just agent_type."""
        meta = SubagentMetadata(agent_type="rules")
        assert meta.agent_type == "rules"
        assert meta.query_type is None
        assert meta.context_used == {}
        assert meta.extra == {}

    def test_accepts_full_metadata(self):
        """Should accept all fields."""
        meta = SubagentMetadata(
            agent_type="state",
            query_type="coverage_gaps",
            context_used={"investigator_name": "Roland Banks"},
            extra={"analysis_depth": "detailed"},
        )
        assert meta.agent_type == "state"
        assert meta.query_type == "coverage_gaps"
        assert meta.context_used["investigator_name"] == "Roland Banks"
        assert meta.extra["analysis_depth"] == "detailed"

    def test_context_used_defaults_to_empty_dict(self):
        """context_used should default to empty dict."""
        meta = SubagentMetadata(agent_type="rules")
        assert isinstance(meta.context_used, dict)
        assert len(meta.context_used) == 0

    def test_extra_defaults_to_empty_dict(self):
        """extra should default to empty dict."""
        meta = SubagentMetadata(agent_type="rules")
        assert isinstance(meta.extra, dict)
        assert len(meta.extra) == 0


class TestSubagentResponse:
    """Tests for SubagentResponse model."""

    def test_requires_content_and_metadata(self):
        """Should require content and metadata fields."""
        with pytest.raises(ValidationError):
            SubagentResponse()

        with pytest.raises(ValidationError):
            SubagentResponse(content="test")

    def test_accepts_valid_response(self):
        """Should accept valid response with all required fields."""
        response = SubagentResponse(
            content="Roland Banks can include Guardian cards level 0-5.",
            metadata=SubagentMetadata(agent_type="rules"),
        )
        assert "Roland Banks" in response.content
        assert response.metadata.agent_type == "rules"

    def test_confidence_defaults_to_one(self):
        """Confidence should default to 1.0."""
        response = SubagentResponse(
            content="test",
            metadata=SubagentMetadata(agent_type="rules"),
        )
        assert response.confidence == 1.0

    def test_confidence_bounds_validation(self):
        """Confidence must be between 0 and 1."""
        with pytest.raises(ValidationError):
            SubagentResponse(
                content="test",
                confidence=-0.1,
                metadata=SubagentMetadata(agent_type="rules"),
            )

        with pytest.raises(ValidationError):
            SubagentResponse(
                content="test",
                confidence=1.1,
                metadata=SubagentMetadata(agent_type="rules"),
            )

    def test_accepts_edge_confidence_values(self):
        """Should accept confidence at 0 and 1."""
        response_zero = SubagentResponse(
            content="test",
            confidence=0.0,
            metadata=SubagentMetadata(agent_type="rules"),
        )
        assert response_zero.confidence == 0.0

        response_one = SubagentResponse(
            content="test",
            confidence=1.0,
            metadata=SubagentMetadata(agent_type="rules"),
        )
        assert response_one.confidence == 1.0

    def test_sources_defaults_to_empty_list(self):
        """Sources should default to empty list."""
        response = SubagentResponse(
            content="test",
            metadata=SubagentMetadata(agent_type="rules"),
        )
        assert isinstance(response.sources, list)
        assert len(response.sources) == 0

    def test_accepts_sources_list(self):
        """Should accept list of source strings."""
        response = SubagentResponse(
            content="test",
            sources=["Core Rules", "Investigator: Roland Banks", "Taboo List"],
            metadata=SubagentMetadata(agent_type="rules"),
        )
        assert len(response.sources) == 3
        assert "Core Rules" in response.sources

    def test_error_response_factory(self):
        """error_response should create error responses correctly."""
        response = SubagentResponse.error_response(
            error_message="LLM invocation failed: rate limit exceeded",
            agent_type="state",
        )

        assert "rate limit exceeded" in response.content
        assert response.confidence == 0.0
        assert response.sources == []
        assert response.metadata.agent_type == "state"
        assert response.metadata.query_type == "error"
        assert response.metadata.extra.get("error") is True

    def test_error_response_with_custom_confidence(self):
        """error_response should accept custom confidence."""
        response = SubagentResponse.error_response(
            error_message="Partial failure",
            agent_type="rules",
            confidence=0.3,
        )
        assert response.confidence == 0.3


class TestSubagentResponseIntegration:
    """Integration tests for SubagentResponse usage patterns."""

    def test_full_response_workflow(self):
        """Test creating a complete response as in production."""
        response = SubagentResponse(
            content=(
                "Roland Banks has access to Guardian cards (level 0-5), "
                "Seeker cards (level 0-2), and Neutral cards. "
                "Shrivelling is a Mystic card and is NOT legal for Roland."
            ),
            confidence=0.95,
            sources=[
                "Investigator: Roland Banks",
                "Card: Shrivelling",
                "Deckbuilding Rules",
            ],
            metadata=SubagentMetadata(
                agent_type="rules",
                query_type="legality_check",
                context_used={
                    "investigator_name": "Roland Banks",
                    "deck_id": "deck_123",
                },
                extra={
                    "cards_checked": ["Shrivelling"],
                    "ruling": "illegal",
                },
            ),
        )

        assert response.confidence > 0.9
        assert len(response.sources) == 3
        assert response.metadata.query_type == "legality_check"
        assert "Roland Banks" in response.metadata.context_used["investigator_name"]

    def test_response_can_be_serialized(self):
        """Response should be serializable to dict/JSON."""
        response = SubagentResponse(
            content="Test content",
            confidence=0.8,
            sources=["Source 1"],
            metadata=SubagentMetadata(agent_type="rules"),
        )

        # Should not raise
        response_dict = response.model_dump()
        assert isinstance(response_dict, dict)
        assert response_dict["content"] == "Test content"
        assert response_dict["confidence"] == 0.8
        assert response_dict["metadata"]["agent_type"] == "rules"

    def test_response_can_be_deserialized(self):
        """Response should be deserializable from dict."""
        data = {
            "content": "Test content",
            "confidence": 0.7,
            "sources": ["Source 1", "Source 2"],
            "metadata": {
                "agent_type": "state",
                "query_type": "analysis",
                "context_used": {},
                "extra": {},
            },
        }

        response = SubagentResponse.model_validate(data)
        assert response.content == "Test content"
        assert response.confidence == 0.7
        assert response.metadata.agent_type == "state"
