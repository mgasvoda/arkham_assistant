"""ContextBuilder for doctrine context injection.

This module parses and indexes strategic doctrine documents (like meta-trends.md)
to provide relevant context to LLM calls. Instead of hardcoded scoring weights,
the LLM receives doctrine excerpts that inform its recommendations.

Design philosophy:
- Doctrine is knowledge, not rules - it guides LLM reasoning
- Context is retrieved by relevance to the current query
- Sections are indexed by keywords for fast lookup
- The LLM interprets doctrine; it's not rigidly applied

This is Phase 3 of the decision architecture: Context-Aware Recommendations.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from backend.core.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class DoctrineSection:
    """A parsed section from the doctrine document.

    Attributes:
        heading: The section heading (e.g., "2.1 Weapon Density")
        level: Heading level (1=##, 2=###, 3=####)
        content: The section content (text between this heading and next)
        parent: Parent section heading (for subsections)
        keywords: Extracted keywords for search/matching
    """

    heading: str
    level: int
    content: str
    parent: str | None = None
    keywords: set[str] = field(default_factory=set)

    def __str__(self) -> str:
        return f"{'#' * (self.level + 1)} {self.heading}\n\n{self.content}"


class ContextBuilder:
    """Builds context from doctrine documents for LLM injection.

    Parses markdown documents into sections and provides retrieval methods
    to find relevant doctrine for a given query or investigator class.

    Usage:
        builder = ContextBuilder()
        builder.load_document("/path/to/meta_trends.md")

        # Get context for a Guardian deck build
        context = builder.get_context_for_class("Guardian")

        # Get context for specific topics
        context = builder.get_context_for_topics(["weapons", "economy"])

        # Get context matching a query
        context = builder.get_context_for_query("how to build a big gun deck")
    """

    # Class name mapping for flexible matching
    CLASS_ALIASES = {
        "guardian": ["guardian", "blue", "combat", "fight", "weapon"],
        "seeker": ["seeker", "yellow", "clue", "intellect", "investigate"],
        "rogue": ["rogue", "green", "money", "evade", "agility"],
        "mystic": ["mystic", "purple", "spell", "willpower", "arcane"],
        "survivor": ["survivor", "red", "fail", "discard", "recursion"],
    }

    # Topic keywords for section matching
    TOPIC_KEYWORDS = {
        "economy": ["economy", "resource", "cost", "money", "curve", "tempo"],
        "weapons": ["weapon", "damage", "fight", "combat", "gun", "ammo"],
        "clues": ["clue", "investigate", "shroud", "intellect", "discover"],
        "movement": ["move", "movement", "pathfinder", "shortcut", "map"],
        "allies": ["ally", "charisma", "soak", "slot"],
        "spells": ["spell", "arcane", "willpower", "charge"],
        "skills": ["skill", "commit", "icon", "boost"],
        "events": ["event", "fast", "action"],
        "mulligan": ["mulligan", "opening", "hand", "setup"],
        "difficulty": ["hard", "expert", "chaos", "token", "bag"],
        "multiplayer": ["multiplayer", "solo", "player count", "team"],
        "archetypes": ["archetype", "build", "style", "strategy"],
    }

    def __init__(self, static_dir: str | Path | None = None) -> None:
        """Initialize the ContextBuilder.

        Args:
            static_dir: Path to static files directory. If None, uses default.
        """
        if static_dir is None:
            # Default to backend/static relative to this file
            static_dir = Path(__file__).parent.parent / "static"
        self.static_dir = Path(static_dir)
        self.sections: list[DoctrineSection] = []
        self._loaded_documents: set[str] = set()

    def load_document(self, filename: str = "meta_trends.md") -> int:
        """Load and parse a doctrine document.

        Args:
            filename: Name of the markdown file in static directory.

        Returns:
            Number of sections parsed.

        Raises:
            FileNotFoundError: If the document doesn't exist.
        """
        filepath = self.static_dir / filename
        if not filepath.exists():
            raise FileNotFoundError(f"Doctrine document not found: {filepath}")

        if str(filepath) in self._loaded_documents:
            logger.debug(f"Document already loaded: {filename}")
            return len(self.sections)

        content = filepath.read_text(encoding="utf-8")
        new_sections = self._parse_markdown(content)
        self.sections.extend(new_sections)
        self._loaded_documents.add(str(filepath))

        logger.info(f"Loaded {len(new_sections)} sections from {filename}")
        return len(new_sections)

    def _parse_markdown(self, content: str) -> list[DoctrineSection]:
        """Parse markdown content into sections.

        Args:
            content: Raw markdown text.

        Returns:
            List of parsed DoctrineSection objects.
        """
        sections: list[DoctrineSection] = []
        lines = content.split("\n")

        current_heading = ""
        current_level = 0
        current_content: list[str] = []
        parent_stack: list[str] = [""] * 4  # Track parents at each level

        # Regex for markdown headings
        heading_pattern = re.compile(r"^(#{2,4})\s+(.+)$")

        for line in lines:
            match = heading_pattern.match(line)
            if match:
                # Save previous section if exists
                if current_heading:
                    section = self._create_section(
                        current_heading,
                        current_level,
                        "\n".join(current_content).strip(),
                        parent_stack[current_level - 1] if current_level > 1 else None,
                    )
                    sections.append(section)

                # Start new section
                hashes, heading_text = match.groups()
                current_level = len(hashes) - 1  # ## = 1, ### = 2, #### = 3
                current_heading = heading_text.strip()
                current_content = []

                # Update parent stack
                parent_stack[current_level] = current_heading
            else:
                current_content.append(line)

        # Don't forget the last section
        if current_heading:
            section = self._create_section(
                current_heading,
                current_level,
                "\n".join(current_content).strip(),
                parent_stack[current_level - 1] if current_level > 1 else None,
            )
            sections.append(section)

        return sections

    def _create_section(
        self,
        heading: str,
        level: int,
        content: str,
        parent: str | None,
    ) -> DoctrineSection:
        """Create a DoctrineSection with extracted keywords.

        Args:
            heading: Section heading text.
            level: Heading level (1-3).
            content: Section content.
            parent: Parent section heading.

        Returns:
            DoctrineSection with keywords extracted.
        """
        # Extract keywords from heading and content
        keywords = self._extract_keywords(heading + " " + content)

        return DoctrineSection(
            heading=heading,
            level=level,
            content=content,
            parent=parent,
            keywords=keywords,
        )

    def _extract_keywords(self, text: str) -> set[str]:
        """Extract searchable keywords from text.

        Args:
            text: Text to extract keywords from.

        Returns:
            Set of lowercase keywords.
        """
        # Normalize text
        text_lower = text.lower()

        keywords: set[str] = set()

        # Add class names found
        for class_name, aliases in self.CLASS_ALIASES.items():
            for alias in aliases:
                if alias in text_lower:
                    keywords.add(class_name)
                    break

        # Add topic keywords found
        for topic, topic_words in self.TOPIC_KEYWORDS.items():
            for word in topic_words:
                if word in text_lower:
                    keywords.add(topic)
                    break

        # Extract investigator names (capitalized proper nouns)
        investigator_pattern = re.compile(r"\b([A-Z][a-z]+\s+[A-Z][a-z]+)\b")
        for match in investigator_pattern.finditer(text):
            name = match.group(1).lower()
            # Filter common non-names
            if name not in {"the card", "the game", "the deck", "the scenario"}:
                keywords.add(name)

        return keywords

    def get_context_for_class(
        self,
        class_name: str,
        include_foundations: bool = True,
        max_sections: int = 5,
    ) -> str:
        """Get doctrine context for a specific investigator class.

        Args:
            class_name: Class name (Guardian, Seeker, etc.)
            include_foundations: Include foundational doctrine sections.
            max_sections: Maximum number of sections to return.

        Returns:
            Concatenated doctrine text.
        """
        self._ensure_loaded()

        class_key = class_name.lower()
        relevant_sections: list[DoctrineSection] = []

        for section in self.sections:
            # Check if section is about this class
            if class_key in section.keywords:
                relevant_sections.append(section)
            # Include foundational sections if requested
            elif include_foundations and section.heading.startswith("1."):
                relevant_sections.append(section)

        # Prioritize by relevance (class-specific first)
        relevant_sections.sort(
            key=lambda s: (
                0 if class_key in s.heading.lower() else 1,
                s.level,
            )
        )

        return self._format_context(relevant_sections[:max_sections])

    def get_context_for_topics(
        self,
        topics: list[str],
        max_sections: int = 5,
    ) -> str:
        """Get doctrine context for specific topics.

        Args:
            topics: List of topics (e.g., ["weapons", "economy"])
            max_sections: Maximum sections to return.

        Returns:
            Concatenated doctrine text.
        """
        self._ensure_loaded()

        topic_keys = {t.lower() for t in topics}
        relevant_sections: list[DoctrineSection] = []
        section_scores: dict[str, int] = {}

        for section in self.sections:
            # Score by number of matching topics
            score = len(section.keywords & topic_keys)
            if score > 0:
                section_scores[section.heading] = score
                relevant_sections.append(section)

        # Sort by score (most relevant first)
        relevant_sections.sort(
            key=lambda s: section_scores.get(s.heading, 0),
            reverse=True,
        )

        return self._format_context(relevant_sections[:max_sections])

    def get_context_for_query(
        self,
        query: str,
        max_sections: int = 3,
    ) -> str:
        """Get doctrine context matching a natural language query.

        Uses keyword extraction from the query to find relevant sections.

        Args:
            query: Natural language query.
            max_sections: Maximum sections to return.

        Returns:
            Concatenated doctrine text.
        """
        self._ensure_loaded()

        query_keywords = self._extract_keywords(query)

        if not query_keywords:
            # Fallback: search for words in query
            words = set(query.lower().split())
            query_keywords = words

        relevant_sections: list[DoctrineSection] = []
        section_scores: dict[str, float] = {}

        for section in self.sections:
            # Score by keyword overlap
            overlap = len(section.keywords & query_keywords)
            if overlap > 0:
                # Normalize by section keyword count to avoid bias toward large sections
                score = overlap / (len(section.keywords) + 1)
                section_scores[section.heading] = score
                relevant_sections.append(section)

        # Sort by score
        relevant_sections.sort(
            key=lambda s: section_scores.get(s.heading, 0),
            reverse=True,
        )

        return self._format_context(relevant_sections[:max_sections])

    def get_context_for_investigator(
        self,
        investigator_name: str,
        max_sections: int = 5,
    ) -> str:
        """Get doctrine context for a specific investigator.

        Looks for sections mentioning the investigator by name, plus their class.

        Args:
            investigator_name: Investigator name (e.g., "Roland Banks")
            max_sections: Maximum sections to return.

        Returns:
            Concatenated doctrine text.
        """
        self._ensure_loaded()

        name_key = investigator_name.lower()
        relevant_sections: list[DoctrineSection] = []

        for section in self.sections:
            # Check for investigator name mention
            if name_key in section.content.lower():
                relevant_sections.append(section)
                continue

            # Check for investigator's class (infer from name or context)
            # This is a simplified heuristic
            for class_name in self.CLASS_ALIASES:
                if class_name in section.keywords and class_name in name_key:
                    relevant_sections.append(section)
                    break

        return self._format_context(relevant_sections[:max_sections])

    def get_section_by_heading(self, heading_pattern: str) -> str | None:
        """Get a specific section by heading pattern.

        Args:
            heading_pattern: Regex pattern or exact heading text.

        Returns:
            Section content or None if not found.
        """
        self._ensure_loaded()

        pattern = re.compile(heading_pattern, re.IGNORECASE)

        for section in self.sections:
            if pattern.search(section.heading):
                return str(section)

        return None

    def list_sections(self) -> list[str]:
        """List all section headings.

        Returns:
            List of section headings.
        """
        self._ensure_loaded()
        return [s.heading for s in self.sections]

    def _ensure_loaded(self) -> None:
        """Ensure the default document is loaded."""
        if not self.sections:
            try:
                self.load_document("meta_trends.md")
            except FileNotFoundError:
                logger.warning("meta_trends.md not found, context will be empty")

    def _format_context(self, sections: list[DoctrineSection]) -> str:
        """Format sections into context string for LLM injection.

        Args:
            sections: List of sections to format.

        Returns:
            Formatted context string.
        """
        if not sections:
            return ""

        parts = ["--- STRATEGIC DOCTRINE CONTEXT ---\n"]

        for section in sections:
            parts.append(str(section))
            parts.append("\n---\n")

        parts.append("--- END DOCTRINE CONTEXT ---")

        return "\n".join(parts)


# =============================================================================
# Convenience Functions
# =============================================================================

_default_builder: ContextBuilder | None = None


def get_context_builder() -> ContextBuilder:
    """Get the singleton ContextBuilder instance.

    Returns:
        Initialized ContextBuilder.
    """
    global _default_builder
    if _default_builder is None:
        _default_builder = ContextBuilder()
    return _default_builder


def get_class_context(class_name: str) -> str:
    """Convenience function to get class doctrine context.

    Args:
        class_name: Investigator class name.

    Returns:
        Doctrine context string.
    """
    return get_context_builder().get_context_for_class(class_name)


def get_topic_context(topics: list[str]) -> str:
    """Convenience function to get topic doctrine context.

    Args:
        topics: List of topics.

    Returns:
        Doctrine context string.
    """
    return get_context_builder().get_context_for_topics(topics)
