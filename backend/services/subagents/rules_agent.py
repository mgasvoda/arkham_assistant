"""RulesAgent with hybrid retrieval for deckbuilding rules.

This module implements the RulesAgent subagent that handles deckbuilding rules,
card restrictions, and game rule queries using a hybrid retrieval approach:

1. Keyword search: Searches static files for relevant rule sections
2. LLM summarization: Uses the subagent LLM to interpret and explain rules

The agent can answer questions about:
- Deckbuilding rule questions
- Card legality for investigators
- Class restrictions and card access
- Signature card and weakness rules
"""

import re
from pathlib import Path
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from backend.models.subagent_models import SubagentMetadata, SubagentResponse
from backend.services.subagents.base import (
    BaseSubagent,
    SubagentConfig,
    SubagentState,
)


# =============================================================================
# Input/Output Schemas
# =============================================================================


class RulesQuery(BaseModel):
    """Input schema for rules queries.

    Attributes:
        question: The rules question to answer.
        investigator_id: Optional investigator ID for investigator-specific rules.
        card_ids: Optional list of card IDs being queried about.
    """

    question: str = Field(
        description="The rules question to answer"
    )
    investigator_id: str | None = Field(
        default=None,
        description="Investigator ID for investigator-specific rules"
    )
    card_ids: list[str] | None = Field(
        default=None,
        description="Card IDs being queried about"
    )


class RulesResponse(SubagentResponse):
    """Structured response for rules queries.

    Extends SubagentResponse with rules-specific fields.

    Attributes:
        rule_text: The relevant rule excerpt from reference materials.
        interpretation: Plain-language explanation of the rule.
        applies_to: List of what this rule affects (cards, investigators, etc.).
    """

    rule_text: str = Field(
        default="",
        description="Relevant rule excerpt from reference materials"
    )
    interpretation: str = Field(
        default="",
        description="Plain-language explanation of the rule"
    )
    applies_to: list[str] = Field(
        default_factory=list,
        description="What this rule affects (cards, investigators, etc.)"
    )

    @classmethod
    def from_base_response(
        cls,
        base_response: SubagentResponse,
        rule_text: str = "",
        interpretation: str = "",
        applies_to: list[str] | None = None,
    ) -> "RulesResponse":
        """Create a RulesResponse from a base SubagentResponse.

        Args:
            base_response: The base response to extend.
            rule_text: The relevant rule excerpt.
            interpretation: Plain-language explanation.
            applies_to: What the rule affects.

        Returns:
            RulesResponse with all fields populated.
        """
        return cls(
            content=base_response.content,
            confidence=base_response.confidence,
            sources=base_response.sources,
            metadata=base_response.metadata,
            rule_text=rule_text,
            interpretation=interpretation,
            applies_to=applies_to or [],
        )

    @classmethod
    def error_response(
        cls,
        error_message: str,
        agent_type: str = "rules",
        confidence: float = 0.0,
    ) -> "RulesResponse":
        """Create an error response for graceful degradation.

        Args:
            error_message: Description of the error.
            agent_type: The agent type (default: "rules").
            confidence: Confidence score (typically 0 for errors).

        Returns:
            A RulesResponse indicating an error occurred.
        """
        return cls(
            content=error_message,
            confidence=confidence,
            sources=[],
            metadata=SubagentMetadata(
                agent_type=agent_type,
                query_type="error",
                extra={"error": True},
            ),
            rule_text="",
            interpretation="",
            applies_to=[],
        )


# =============================================================================
# Keyword Search for Static Files
# =============================================================================


class RulesRetriever:
    """Retrieves relevant rule sections from static files using keyword search.

    The retriever searches through markdown files in the static directory
    and returns sections that match the query keywords.
    """

    # Keywords mapped to relevant topics for better matching
    TOPIC_KEYWORDS = {
        "deckbuilding": [
            "deck construction", "30 cards", "copies", "deckbuilding",
            "include", "restriction", "level", "class"
        ],
        "actions": [
            "action", "investigate", "move", "fight", "evade", "draw",
            "resource", "play", "activate"
        ],
        "resources": [
            "resource", "cost", "pay", "gain", "spend"
        ],
        "skills": [
            "skill test", "difficulty", "success", "chaos", "token", "commit"
        ],
        "signature": [
            "signature", "required", "weakness", "basic weakness"
        ],
        "class": [
            "guardian", "seeker", "rogue", "mystic", "survivor", "neutral",
            "class", "faction"
        ],
        "xp": [
            "experience", "xp", "upgrade", "level", "advance"
        ],
        "taboo": [
            "taboo", "mutated", "forbidden", "chained", "unchained"
        ],
    }

    def __init__(self, static_dir: Path | None = None):
        """Initialize the retriever.

        Args:
            static_dir: Path to static files directory. If None, uses default.
        """
        if static_dir is None:
            self.static_dir = Path(__file__).parent.parent.parent / "static"
        else:
            self.static_dir = static_dir

    def search(self, query: str, max_sections: int = 5) -> list[dict[str, str]]:
        """Search static files for relevant rule sections.

        Args:
            query: The search query.
            max_sections: Maximum number of sections to return.

        Returns:
            List of dicts with 'source', 'section', and 'content' keys.
        """
        results = []
        query_lower = query.lower()

        # Extract keywords from query
        query_keywords = self._extract_keywords(query_lower)

        # Search each static file
        for file_path in self.static_dir.glob("*.md"):
            sections = self._parse_markdown_sections(file_path)
            for section in sections:
                score = self._score_section(section, query_keywords, query_lower)
                if score > 0:
                    results.append({
                        "source": file_path.name,
                        "section": section["heading"],
                        "content": section["content"],
                        "score": score,
                    })

        # Sort by score and limit results
        results.sort(key=lambda x: x["score"], reverse=True)
        return [
            {"source": r["source"], "section": r["section"], "content": r["content"]}
            for r in results[:max_sections]
        ]

    def _extract_keywords(self, query: str) -> set[str]:
        """Extract relevant keywords from a query.

        Args:
            query: The lowercased query string.

        Returns:
            Set of keywords found in the query.
        """
        keywords = set()

        # Check each topic's keywords
        for topic, topic_keywords in self.TOPIC_KEYWORDS.items():
            for keyword in topic_keywords:
                if keyword in query:
                    keywords.add(keyword)
                    # Also add the topic name for broader matching
                    keywords.add(topic)

        # Add individual words from query (excluding common words)
        stop_words = {
            "the", "a", "an", "is", "are", "can", "could", "what", "how",
            "why", "when", "where", "does", "do", "for", "to", "in", "of",
            "and", "or", "but", "with", "this", "that", "it"
        }
        words = re.findall(r'\b\w+\b', query)
        keywords.update(word for word in words if word not in stop_words and len(word) > 2)

        return keywords

    def _parse_markdown_sections(self, file_path: Path) -> list[dict[str, str]]:
        """Parse a markdown file into sections.

        Args:
            file_path: Path to the markdown file.

        Returns:
            List of dicts with 'heading' and 'content' keys.
        """
        try:
            content = file_path.read_text(encoding="utf-8")
        except (OSError, IOError):
            return []

        sections = []
        current_heading = "Introduction"
        current_content = []

        for line in content.split("\n"):
            # Check for markdown headings
            if line.startswith("#"):
                # Save previous section if it has content
                if current_content:
                    sections.append({
                        "heading": current_heading,
                        "content": "\n".join(current_content).strip(),
                    })

                # Start new section
                current_heading = line.lstrip("#").strip()
                current_content = []
            else:
                current_content.append(line)

        # Don't forget the last section
        if current_content:
            sections.append({
                "heading": current_heading,
                "content": "\n".join(current_content).strip(),
            })

        return sections

    def _score_section(
        self,
        section: dict[str, str],
        keywords: set[str],
        query: str
    ) -> float:
        """Score a section based on keyword matches.

        Args:
            section: Section dict with 'heading' and 'content'.
            keywords: Set of keywords to match.
            query: The original query string.

        Returns:
            Relevance score (higher is better).
        """
        score = 0.0
        heading_lower = section["heading"].lower()
        content_lower = section["content"].lower()

        # Heading matches are worth more
        for keyword in keywords:
            if keyword in heading_lower:
                score += 3.0
            if keyword in content_lower:
                score += 1.0

        # Exact phrase matches are worth even more
        if len(query) > 5 and query in content_lower:
            score += 5.0

        # Boost for sections with substantial content
        if len(section["content"]) > 100:
            score *= 1.2

        return score

    def get_all_rules_content(self) -> str:
        """Get all rules content concatenated.

        Useful when no specific matches are found.

        Returns:
            Combined content from all static files.
        """
        content_parts = []
        for file_path in sorted(self.static_dir.glob("*.md")):
            try:
                content = file_path.read_text(encoding="utf-8")
                content_parts.append(f"# {file_path.stem}\n\n{content}")
            except (OSError, IOError):
                continue
        return "\n\n---\n\n".join(content_parts)


# =============================================================================
# RulesAgent Implementation
# =============================================================================


class RulesAgent(BaseSubagent):
    """RulesAgent with hybrid retrieval for deckbuilding rules.

    This agent extends the base subagent pattern with:
    1. Keyword search on static files to retrieve relevant rules
    2. LLM summarization to interpret and explain the rules

    The agent handles:
    - Deckbuilding rule questions
    - Card legality for investigators
    - Class restrictions and card access
    - Signature card and weakness rules
    """

    # Prompt template for the hybrid retrieval approach
    HYBRID_PROMPT_TEMPLATE = """You are the Rules Agent, a specialist in Arkham Horror: The Card Game deckbuilding rules and card legality.

## Retrieved Rule Context

The following rule sections may be relevant to the user's question:

{retrieved_rules}

## Your Task

Using the retrieved rules above (and your knowledge of Arkham Horror LCG rules), answer the user's question.

When answering:
1. **Cite specific rules** when explaining restrictions
2. **Be precise** about level requirements and XP costs
3. **Clarify edge cases** (e.g., Dunwich investigators, Versatile, etc.)
4. **Distinguish** between "cannot include" vs "can include but shouldn't"

## Response Format

Structure your response as follows:
- **Rule**: The specific rule or restriction that applies
- **Interpretation**: A plain-language explanation
- **Applies To**: What cards/investigators this affects

{context_block}"""

    def __init__(
        self,
        config: SubagentConfig | None = None,
        retriever: RulesRetriever | None = None,
    ) -> None:
        """Initialize the RulesAgent.

        Args:
            config: Optional configuration for the subagent.
            retriever: Optional custom retriever. If None, creates default.
        """
        super().__init__(agent_type="rules", config=config)
        self.retriever = retriever or RulesRetriever()

    def _prepare_prompt_node(self, state: SubagentState) -> dict[str, Any]:
        """Prepare the system prompt with retrieved rules context.

        This overrides the base implementation to inject retrieved rules
        into the prompt for hybrid retrieval.

        Args:
            state: Current graph state with query and context.

        Returns:
            State update with formatted system prompt and updated context.
        """
        try:
            # Retrieve relevant rules
            retrieved_sections = self.retriever.search(state.query)

            # Format retrieved rules
            if retrieved_sections:
                rules_text = "\n\n".join(
                    f"### {section['section']} ({section['source']})\n{section['content']}"
                    for section in retrieved_sections
                )
            else:
                # Fall back to all content if no specific matches
                rules_text = self.retriever.get_all_rules_content()
                if not rules_text:
                    rules_text = "*No rule documentation available*"

            # Build context block
            context_lines = []
            if state.context.get("investigator_name"):
                context_lines.append(
                    f"**Investigator**: {state.context['investigator_name']}"
                )
            if state.context.get("deck_id"):
                context_lines.append(f"**Deck ID**: {state.context['deck_id']}")

            context_block = (
                "## Current Context\n" + "\n".join(context_lines)
                if context_lines
                else ""
            )

            # Format the hybrid prompt
            system_prompt = self.HYBRID_PROMPT_TEMPLATE.format(
                retrieved_rules=rules_text,
                context_block=context_block,
            )

            # Return both prompt and updated context with retrieved sections
            updated_context = dict(state.context)
            updated_context["_retrieved_sections"] = retrieved_sections

            return {"system_prompt": system_prompt, "context": updated_context}
        except Exception as e:
            return {"error": f"Failed to prepare prompt: {e}"}

    def _invoke_llm_node(self, state: SubagentState) -> dict[str, Any]:
        """Invoke the LLM and create a RulesResponse.

        This overrides the base implementation to return a RulesResponse
        instead of a generic SubagentResponse.

        Args:
            state: Current graph state with prompt and query.

        Returns:
            State update with RulesResponse.
        """
        # Check for errors from previous nodes
        if state.error:
            return {
                "response": RulesResponse.error_response(
                    error_message=state.error,
                    agent_type=self.agent_type,
                )
            }

        # Build messages
        messages = [
            SystemMessage(content=state.system_prompt),
            HumanMessage(content=state.query),
        ]

        try:
            # Invoke LLM
            result = self.llm.invoke(messages)

            # Extract content
            content = (
                result.content
                if isinstance(result.content, str)
                else str(result.content)
            )

            # Parse response to extract structured fields
            rule_text, interpretation, applies_to = self._parse_llm_response(content)

            # Build sources from retrieved sections
            retrieved = state.context.get("_retrieved_sections", [])
            sources = self._extract_sources(content, state)
            for section in retrieved:
                source_ref = f"{section['section']} ({section['source']})"
                if source_ref not in sources:
                    sources.append(source_ref)

            # Build response
            response = RulesResponse(
                content=content,
                confidence=self._calculate_confidence(content, state),
                sources=sources,
                metadata=SubagentMetadata(
                    agent_type=self.agent_type,
                    query_type=self._determine_query_type(state.query),
                    context_used={
                        k: v
                        for k, v in state.context.items()
                        if v is not None and not k.startswith("_")
                    },
                    extra={
                        "sections_retrieved": len(retrieved),
                        "hybrid_retrieval": True,
                    },
                ),
                rule_text=rule_text,
                interpretation=interpretation,
                applies_to=applies_to,
            )
            return {"response": response}

        except Exception as e:
            return {
                "response": RulesResponse.error_response(
                    error_message=f"LLM invocation failed: {e}",
                    agent_type=self.agent_type,
                )
            }

    def _parse_llm_response(self, content: str) -> tuple[str, str, list[str]]:
        """Parse the LLM response to extract structured fields.

        Looks for patterns like:
        - **Rule**: <text>
        - **Interpretation**: <text>
        - **Applies To**: <text>

        Args:
            content: The LLM response content.

        Returns:
            Tuple of (rule_text, interpretation, applies_to list).
        """
        rule_text = ""
        interpretation = ""
        applies_to: list[str] = []

        # Try to extract rule text
        rule_match = re.search(
            r'\*\*Rule\*\*:\s*(.+?)(?=\*\*|$)',
            content,
            re.IGNORECASE | re.DOTALL
        )
        if rule_match:
            rule_text = rule_match.group(1).strip()

        # Try to extract interpretation
        interp_match = re.search(
            r'\*\*Interpretation\*\*:\s*(.+?)(?=\*\*|$)',
            content,
            re.IGNORECASE | re.DOTALL
        )
        if interp_match:
            interpretation = interp_match.group(1).strip()

        # Try to extract applies_to
        applies_match = re.search(
            r'\*\*Applies To\*\*:\s*(.+?)(?=\*\*|$)',
            content,
            re.IGNORECASE | re.DOTALL
        )
        if applies_match:
            applies_text = applies_match.group(1).strip()
            # Split on commas or newlines
            applies_to = [
                item.strip().lstrip("- ")
                for item in re.split(r'[,\n]', applies_text)
                if item.strip()
            ]

        # If structured parsing didn't work, use the whole content
        if not rule_text and not interpretation:
            interpretation = content

        return rule_text, interpretation, applies_to

    def _calculate_confidence(
        self, content: str, state: SubagentState
    ) -> float:
        """Calculate confidence for rules responses.

        Higher confidence when:
        - Retrieved sections were found
        - Response contains definitive language
        - Rule citations are present

        Args:
            content: The LLM response content.
            state: The current graph state.

        Returns:
            Confidence score from 0.0 to 1.0.
        """
        content_lower = content.lower()
        base_confidence = 0.5

        # Boost for retrieved context
        retrieved = state.context.get("_retrieved_sections", [])
        if retrieved:
            base_confidence += 0.15 * min(len(retrieved), 3) / 3

        # High confidence indicators
        if any(
            phrase in content_lower
            for phrase in [
                "according to the rules",
                "the rules state",
                "rule reference",
                "is legal",
                "is not legal",
                "cannot include",
                "must include",
            ]
        ):
            base_confidence += 0.2

        # Medium confidence indicators
        if any(
            phrase in content_lower
            for phrase in ["can include", "may include", "restricted to", "level 0-"]
        ):
            base_confidence += 0.1

        # Penalty for uncertainty language
        if any(
            phrase in content_lower
            for phrase in ["not sure", "unclear", "might be", "possibly", "i think"]
        ):
            base_confidence -= 0.15

        return min(max(base_confidence, 0.1), 0.95)

    def _extract_sources(
        self, content: str, state: SubagentState
    ) -> list[str]:
        """Extract rule and card references from the response.

        Args:
            content: The LLM response content.
            state: The current graph state.

        Returns:
            List of source references.
        """
        sources = []

        # Add investigator as source if mentioned
        investigator = state.context.get("investigator_name")
        if investigator and investigator.lower() in content.lower():
            sources.append(f"Investigator: {investigator}")

        # Look for rule-related keywords
        content_lower = content.lower()
        if "taboo" in content_lower:
            sources.append("Taboo List")
        if "signature" in content_lower:
            sources.append("Signature Card Rules")
        if "weakness" in content_lower:
            sources.append("Weakness Rules")
        if "deck construction" in content_lower or "deckbuilding" in content_lower:
            sources.append("Deck Construction Rules")

        return sources

    def _determine_query_type(self, query: str) -> str:
        """Classify the type of rules query.

        Args:
            query: The user's query string.

        Returns:
            String identifier for the query type.
        """
        query_lower = query.lower()

        # Check specific patterns first (order matters!)
        if "taboo" in query_lower:
            return "taboo_check"
        if any(word in query_lower for word in ["signature", "required"]):
            return "signature_rules"
        if any(word in query_lower for word in ["weakness", "basic weakness"]):
            return "weakness_rules"
        # XP/level rules - check before legality since "level" is more specific
        if any(word in query_lower for word in ["xp", "experience", "upgrade"]):
            return "xp_rules"
        if "level" in query_lower and "card" in query_lower:
            return "xp_rules"
        # Class access - check before generic legality
        if any(word in query_lower for word in ["class", "faction"]):
            return "class_access"
        if "access" in query_lower and any(
            word in query_lower for word in ["card", "what", "which"]
        ):
            return "class_access"
        # Generic legality check
        if any(word in query_lower for word in ["legal", "include", "can ", "allow"]):
            return "legality_check"

        return "general_rules"

    def query_rules(
        self,
        rules_query: RulesQuery,
        context: dict[str, Any] | None = None,
    ) -> RulesResponse:
        """Execute a rules query with the RulesQuery input schema.

        This is a convenience method that accepts a RulesQuery object
        and merges its fields into the context.

        Args:
            rules_query: The structured rules query.
            context: Optional additional context.

        Returns:
            RulesResponse with the query result.
        """
        context = context or {}

        # Merge RulesQuery fields into context
        if rules_query.investigator_id:
            context["investigator_id"] = rules_query.investigator_id
        if rules_query.card_ids:
            context["card_ids"] = rules_query.card_ids

        # Execute query
        response = self.query(rules_query.question, context)

        # Ensure we return a RulesResponse
        if isinstance(response, RulesResponse):
            return response

        # Convert SubagentResponse to RulesResponse
        return RulesResponse.from_base_response(response)


# =============================================================================
# Factory function
# =============================================================================


def create_rules_agent(
    config: SubagentConfig | None = None,
    retriever: RulesRetriever | None = None,
) -> RulesAgent:
    """Create a configured RulesAgent instance.

    Args:
        config: Optional configuration for the subagent.
        retriever: Optional custom retriever for rules lookup.

    Returns:
        Configured RulesAgent instance.
    """
    return RulesAgent(config=config, retriever=retriever)
