"""Integration tests for the Chat API endpoint.

Tests the /chat endpoint that wires up to the orchestrator,
verifying both Q&A and deck building flows work via the API.
"""

import os
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.models.subagent_models import SubagentMetadata, SubagentResponse


@pytest.fixture
def client():
    """Create a test client for the API."""
    return TestClient(app)


# =============================================================================
# Request Validation Tests
# =============================================================================


class TestChatRequestValidation:
    """Tests for chat request validation."""

    def test_requires_message_field(self, client):
        """Should return 422 when message field is missing."""
        response = client.post("/chat/", json={})
        assert response.status_code == 422

    def test_accepts_minimal_request(self, client):
        """Should accept request with just message field."""
        with patch("backend.api.chat.process_chat_message") as mock_process:
            mock_process.return_value = {
                "reply": "Test response",
                "structured_data": {"content": "Test"},
                "agents_consulted": ["rules"],
            }

            response = client.post(
                "/chat/",
                json={"message": "What cards can Roland use?"},
            )

            assert response.status_code == 200
            mock_process.assert_called_once()

    def test_accepts_full_request(self, client):
        """Should accept request with all optional fields."""
        with patch("backend.api.chat.process_chat_message") as mock_process:
            mock_process.return_value = {
                "reply": "Test response",
                "structured_data": {"content": "Test"},
                "agents_consulted": ["rules", "action_space"],
            }

            response = client.post(
                "/chat/",
                json={
                    "message": "Build me a combat deck",
                    "deck_id": "deck_123",
                    "investigator_id": "01001",
                    "investigator_name": "Roland Banks",
                    "scenario_name": "The Gathering",
                    "upgrade_xp": 5,
                    "context": {"owned_sets": ["Core Set"]},
                },
            )

            assert response.status_code == 200
            mock_process.assert_called_once()

            # Verify context was built correctly
            call_args = mock_process.call_args
            context = call_args.kwargs["context"]
            assert context["investigator_id"] == "01001"
            assert context["investigator_name"] == "Roland Banks"
            assert context["scenario_name"] == "The Gathering"
            assert context["upgrade_xp"] == 5
            assert context["owned_sets"] == ["Core Set"]

    def test_rejects_negative_xp(self, client):
        """Should reject negative upgrade_xp values."""
        response = client.post(
            "/chat/",
            json={
                "message": "Upgrade my deck",
                "upgrade_xp": -1,
            },
        )
        assert response.status_code == 422


# =============================================================================
# Q&A Flow Tests
# =============================================================================


class TestQAFlow:
    """Tests for Q&A requests through the API."""

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    @patch("backend.services.orchestrator.ChatOpenAI")
    @patch("backend.services.orchestrator.create_rules_agent")
    def test_qa_returns_orchestrator_response(
        self, mock_rules_agent, mock_chat, client
    ):
        """Should return OrchestratorResponse for Q&A requests."""
        # Setup mocks
        mock_llm = MagicMock()
        mock_llm.invoke.return_value.content = "Roland can include Guardian cards level 0-5."
        mock_chat.return_value = mock_llm

        mock_agent = MagicMock()
        mock_agent.query.return_value = SubagentResponse(
            content="Guardian cards level 0-5 are allowed.",
            confidence=0.9,
            metadata=SubagentMetadata(agent_type="rules"),
        )
        mock_rules_agent.return_value = mock_agent

        response = client.post(
            "/chat/",
            json={"message": "What cards can Roland Banks include?"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "reply" in data
        assert "structured_data" in data
        assert "agents_consulted" in data
        assert data["reply"] != ""

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    @patch("backend.services.orchestrator.ChatOpenAI")
    @patch("backend.services.orchestrator.create_rules_agent")
    @patch("backend.services.orchestrator.create_scenario_agent")
    def test_qa_with_scenario_context(
        self, mock_scenario_agent, mock_rules_agent, mock_chat, client
    ):
        """Should include scenario agent when scenario_name is provided."""
        # Setup mocks
        mock_llm = MagicMock()
        mock_llm.invoke.return_value.content = "Prepare for combat and willpower tests."
        mock_chat.return_value = mock_llm

        mock_rules = MagicMock()
        mock_rules.query.return_value = SubagentResponse(
            content="Rules response",
            metadata=SubagentMetadata(agent_type="rules"),
        )
        mock_rules_agent.return_value = mock_rules

        mock_scenario = MagicMock()
        mock_scenario.query.return_value = SubagentResponse(
            content="The Gathering has ghoul enemies.",
            confidence=0.85,
            metadata=SubagentMetadata(agent_type="scenario"),
        )
        mock_scenario_agent.return_value = mock_scenario

        response = client.post(
            "/chat/",
            json={
                "message": "How should I prepare?",
                "scenario_name": "The Gathering",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "scenario" in data["agents_consulted"]


# =============================================================================
# Deck Building Flow Tests
# =============================================================================


class TestDeckBuildingFlow:
    """Tests for deck building requests through the API."""

    def test_deck_building_request(self, client):
        """Should handle deck building requests and return NewDeckResponse format."""
        with patch("backend.api.chat.process_chat_message") as mock_process:
            # Mock a NewDeckResponse-style result
            mock_process.return_value = {
                "reply": "Combat Guardian Deck",
                "structured_data": {
                    "deck_name": "Roland's Assault Force",
                    "investigator_id": "01001",
                    "investigator_name": "Roland Banks",
                    "cards": [
                        {
                            "card_id": "01016",
                            "name": "Machete",
                            "quantity": 2,
                            "reason": "Core combat weapon",
                            "category": "combat",
                        }
                    ],
                    "total_cards": 30,
                    "reasoning": "A combat-focused deck for Roland.",
                    "archetype": "Combat Guardian",
                    "warnings": [],
                    "confidence": 0.85,
                    "subagent_results": [],
                    "metadata": {},
                },
                "agents_consulted": ["rules", "action_space", "state"],
            }

            response = client.post(
                "/chat/",
                json={
                    "message": "Build me a combat deck",
                    "investigator_id": "01001",
                    "investigator_name": "Roland Banks",
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert "reply" in data
            assert "structured_data" in data
            # Deck building response includes deck_name
            structured = data["structured_data"]
            assert "deck_name" in structured
            assert structured["deck_name"] == "Roland's Assault Force"
            assert structured["investigator_name"] == "Roland Banks"
            assert len(structured["cards"]) > 0

    def test_deck_building_passes_investigator_context(self, client):
        """Should pass investigator fields to orchestrator."""
        with patch("backend.api.chat.process_chat_message") as mock_process:
            mock_process.return_value = {
                "reply": "Deck built",
                "structured_data": {"deck_name": "Test Deck"},
                "agents_consulted": [],
            }

            client.post(
                "/chat/",
                json={
                    "message": "Build me a deck",
                    "investigator_id": "01001",
                    "investigator_name": "Roland Banks",
                    "scenario_name": "The Gathering",
                },
            )

            call_args = mock_process.call_args
            context = call_args.kwargs["context"]
            assert context["investigator_id"] == "01001"
            assert context["investigator_name"] == "Roland Banks"
            assert context["scenario_name"] == "The Gathering"


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Tests for error handling in the chat API."""

    def test_returns_500_on_orchestration_error(self, client):
        """Should return 500 when orchestration fails."""
        with patch("backend.api.chat.process_chat_message") as mock_process:
            mock_process.side_effect = Exception("Unexpected error")

            response = client.post(
                "/chat/",
                json={"message": "Test message"},
            )

            assert response.status_code == 500
            assert "Orchestration failed" in response.json()["detail"]

    def test_returns_500_on_config_error(self, client):
        """Should return 500 when configuration is invalid."""
        with patch("backend.api.chat.process_chat_message") as mock_process:
            mock_process.side_effect = ValueError("OPENAI_API_KEY not set")

            response = client.post(
                "/chat/",
                json={"message": "Test message"},
            )

            assert response.status_code == 500
            assert "Configuration error" in response.json()["detail"]


# =============================================================================
# Response Format Tests
# =============================================================================


class TestResponseFormat:
    """Tests for response format compliance."""

    def test_response_contains_required_fields(self, client):
        """Should return all required response fields."""
        with patch("backend.api.chat.process_chat_message") as mock_process:
            mock_process.return_value = {
                "reply": "Test response content",
                "structured_data": {
                    "content": "Full content",
                    "confidence": 0.85,
                    "subagent_results": [],
                    "agents_consulted": ["rules"],
                },
                "agents_consulted": ["rules"],
            }

            response = client.post(
                "/chat/",
                json={"message": "Test question"},
            )

            assert response.status_code == 200
            data = response.json()

            # Required fields in ChatResponse
            assert "reply" in data
            assert "structured_data" in data
            assert "agents_consulted" in data

            # Verify types
            assert isinstance(data["reply"], str)
            assert isinstance(data["structured_data"], dict)
            assert isinstance(data["agents_consulted"], list)

    def test_structured_data_contains_confidence(self, client):
        """Should include confidence in structured_data."""
        with patch("backend.api.chat.process_chat_message") as mock_process:
            mock_process.return_value = {
                "reply": "Response",
                "structured_data": {
                    "content": "Content",
                    "confidence": 0.9,
                    "subagent_results": [],
                    "agents_consulted": ["rules"],
                },
                "agents_consulted": ["rules"],
            }

            response = client.post(
                "/chat/",
                json={"message": "Question"},
            )

            data = response.json()
            assert "confidence" in data["structured_data"]
            assert data["structured_data"]["confidence"] == 0.9


# =============================================================================
# Context Handling Tests
# =============================================================================


class TestContextHandling:
    """Tests for proper context handling."""

    def test_merges_context_fields(self, client):
        """Should merge explicit fields into context dict."""
        with patch("backend.api.chat.process_chat_message") as mock_process:
            mock_process.return_value = {
                "reply": "Response",
                "structured_data": {"content": "Content"},
                "agents_consulted": [],
            }

            client.post(
                "/chat/",
                json={
                    "message": "Question",
                    "investigator_id": "01001",
                    "context": {"deck_cards": ["01016"]},
                },
            )

            call_args = mock_process.call_args
            context = call_args.kwargs["context"]

            # Both explicit field and context field should be present
            assert context["investigator_id"] == "01001"
            assert context["deck_cards"] == ["01016"]

    def test_explicit_fields_override_context(self, client):
        """Should use explicit fields when duplicated in context."""
        with patch("backend.api.chat.process_chat_message") as mock_process:
            mock_process.return_value = {
                "reply": "Response",
                "structured_data": {"content": "Content"},
                "agents_consulted": [],
            }

            client.post(
                "/chat/",
                json={
                    "message": "Question",
                    "investigator_name": "Roland Banks",
                    "context": {"investigator_name": "Daisy Walker"},
                },
            )

            call_args = mock_process.call_args
            context = call_args.kwargs["context"]

            # Explicit field should override context
            assert context["investigator_name"] == "Roland Banks"
