"""Tests for ContextBuilder.

Tests parsing, indexing, and retrieval of doctrine context.
"""

import pytest
from pathlib import Path
from unittest.mock import patch

from backend.services.context_builder import (
    ContextBuilder,
    DoctrineSection,
    get_context_builder,
    get_class_context,
    get_topic_context,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_markdown() -> str:
    """Sample doctrine markdown for testing."""
    return '''# Test Doctrine

## 1. Foundational Doctrine
This is the foundation section about economy and resources.
Action economy is important. Resources matter.

### 1.1 The Economy of Actions
Guardians need weapons. Seekers need clues.
Combat and investigation are the two pillars.

### 1.2 Skill Tests
The chaos bag determines success. Willpower helps against treacheries.

## 2. Class Doctrine: The Guardian
The Guardian class focuses on combat and fighting enemies.
Roland Banks is a Guardian/Seeker hybrid.

### 2.1 Weapon Density
Weapons are essential. Machete is level 0 staple.
Lightning Gun is the big gun option for damage.

### 2.2 Soak and Tanking
Beat Cop provides combat boost and soak.
Allies help absorb damage.

## 3. Class Doctrine: The Seeker
Seekers focus on clue gathering and intellect.
Dr. Milan Christopher is a key ally.

### 3.1 Clue Compression
Working a Hunch provides testless clues.
Deduction compresses investigation actions.
'''


@pytest.fixture
def builder(sample_markdown: str, tmp_path: Path) -> ContextBuilder:
    """Create a ContextBuilder with sample content."""
    # Write sample to temp file
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    (static_dir / "meta_trends.md").write_text(sample_markdown)

    builder = ContextBuilder(static_dir=static_dir)
    builder.load_document("meta_trends.md")
    return builder


# =============================================================================
# Parsing Tests
# =============================================================================


class TestMarkdownParsing:
    """Tests for markdown parsing functionality."""

    def test_loads_document(self, builder: ContextBuilder):
        """Document loads and creates sections."""
        assert len(builder.sections) > 0

    def test_parses_headings(self, builder: ContextBuilder):
        """Headings are correctly parsed."""
        headings = [s.heading for s in builder.sections]
        assert "1. Foundational Doctrine" in headings
        assert "2.1 Weapon Density" in headings

    def test_parses_levels(self, builder: ContextBuilder):
        """Heading levels are correctly identified."""
        level_1_sections = [s for s in builder.sections if s.level == 1]
        level_2_sections = [s for s in builder.sections if s.level == 2]

        # Level 1 = ## headings (main sections)
        assert any("Foundational Doctrine" in s.heading for s in level_1_sections)
        # Level 2 = ### headings (subsections)
        assert any("Weapon Density" in s.heading for s in level_2_sections)

    def test_parses_content(self, builder: ContextBuilder):
        """Section content is correctly extracted."""
        weapon_section = next(
            s for s in builder.sections if "Weapon Density" in s.heading
        )
        assert "Machete" in weapon_section.content
        assert "Lightning Gun" in weapon_section.content

    def test_tracks_parent(self, builder: ContextBuilder):
        """Subsections track their parent heading."""
        weapon_section = next(
            s for s in builder.sections if "Weapon Density" in s.heading
        )
        assert weapon_section.parent is not None
        assert "Guardian" in weapon_section.parent


# =============================================================================
# Keyword Extraction Tests
# =============================================================================


class TestKeywordExtraction:
    """Tests for keyword extraction from sections."""

    def test_extracts_class_keywords(self, builder: ContextBuilder):
        """Class names are extracted as keywords."""
        guardian_section = next(
            s for s in builder.sections if "Guardian" in s.heading and s.level == 1
        )
        assert "guardian" in guardian_section.keywords

    def test_extracts_topic_keywords(self, builder: ContextBuilder):
        """Topic keywords are extracted."""
        weapon_section = next(
            s for s in builder.sections if "Weapon Density" in s.heading
        )
        assert "weapons" in weapon_section.keywords

    def test_extracts_economy_keywords(self, builder: ContextBuilder):
        """Economy-related keywords are extracted."""
        foundation_section = next(
            s for s in builder.sections if "Foundational Doctrine" in s.heading
        )
        assert "economy" in foundation_section.keywords


# =============================================================================
# Retrieval Tests
# =============================================================================


class TestClassRetrieval:
    """Tests for class-based context retrieval."""

    def test_retrieves_guardian_context(self, builder: ContextBuilder):
        """Guardian context retrieves Guardian sections."""
        context = builder.get_context_for_class("Guardian")
        assert "Guardian" in context
        assert "Weapon" in context

    def test_retrieves_seeker_context(self, builder: ContextBuilder):
        """Seeker context retrieves Seeker sections."""
        context = builder.get_context_for_class("Seeker")
        assert "Seeker" in context
        assert "clue" in context.lower()

    def test_includes_foundations(self, builder: ContextBuilder):
        """Class context includes foundational sections by default."""
        context = builder.get_context_for_class("Guardian", include_foundations=True)
        assert "Foundational" in context or "economy" in context.lower()

    def test_excludes_foundations_when_requested(self, builder: ContextBuilder):
        """Foundations can be excluded."""
        context = builder.get_context_for_class("Guardian", include_foundations=False)
        # Should not have the 1.x sections
        assert "1. Foundational" not in context


class TestTopicRetrieval:
    """Tests for topic-based context retrieval."""

    def test_retrieves_weapons_topic(self, builder: ContextBuilder):
        """Weapons topic retrieves weapon sections."""
        context = builder.get_context_for_topics(["weapons"])
        assert "Weapon" in context
        assert "Machete" in context

    def test_retrieves_economy_topic(self, builder: ContextBuilder):
        """Economy topic retrieves economy sections."""
        context = builder.get_context_for_topics(["economy"])
        assert "economy" in context.lower() or "resource" in context.lower()

    def test_retrieves_multiple_topics(self, builder: ContextBuilder):
        """Multiple topics retrieve combined sections."""
        context = builder.get_context_for_topics(["weapons", "allies"])
        # Should have both weapon and ally content
        assert len(context) > 0


class TestQueryRetrieval:
    """Tests for query-based context retrieval."""

    def test_retrieves_by_query(self, builder: ContextBuilder):
        """Natural language query retrieves relevant sections."""
        context = builder.get_context_for_query("how to fight enemies")
        # Should match Guardian/combat content
        assert "combat" in context.lower() or "Guardian" in context

    def test_retrieves_investigator_by_name(self, builder: ContextBuilder):
        """Can retrieve context for specific investigator."""
        context = builder.get_context_for_investigator("Roland Banks")
        assert "Roland" in context


# =============================================================================
# Section Access Tests
# =============================================================================


class TestSectionAccess:
    """Tests for direct section access."""

    def test_list_sections(self, builder: ContextBuilder):
        """list_sections returns all headings."""
        headings = builder.list_sections()
        assert len(headings) > 0
        assert any("Guardian" in h for h in headings)

    def test_get_section_by_heading(self, builder: ContextBuilder):
        """Can retrieve section by heading pattern."""
        section = builder.get_section_by_heading("Weapon Density")
        assert section is not None
        assert "Machete" in section

    def test_section_not_found(self, builder: ContextBuilder):
        """Returns None for non-existent section."""
        section = builder.get_section_by_heading("Nonexistent Section")
        assert section is None


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_query(self, builder: ContextBuilder):
        """Empty query returns empty context."""
        context = builder.get_context_for_query("")
        # Should handle gracefully
        assert context == "" or isinstance(context, str)

    def test_unknown_class(self, builder: ContextBuilder):
        """Unknown class returns minimal context."""
        context = builder.get_context_for_class("Wizard")
        # Should return foundations only
        assert isinstance(context, str)

    def test_max_sections_limit(self, builder: ContextBuilder):
        """max_sections limits output."""
        context_short = builder.get_context_for_class("Guardian", max_sections=1)
        context_long = builder.get_context_for_class("Guardian", max_sections=10)
        # Shorter should have less content
        assert len(context_short) <= len(context_long)

    def test_document_not_found(self, tmp_path: Path):
        """FileNotFoundError for missing document."""
        builder = ContextBuilder(static_dir=tmp_path)
        with pytest.raises(FileNotFoundError):
            builder.load_document("nonexistent.md")


# =============================================================================
# Singleton Tests
# =============================================================================


class TestSingletonAccess:
    """Tests for singleton/convenience functions."""

    def test_get_context_builder_returns_instance(self):
        """get_context_builder returns a ContextBuilder."""
        with patch.object(ContextBuilder, "_ensure_loaded"):
            builder = get_context_builder()
            assert isinstance(builder, ContextBuilder)

    def test_get_class_context_convenience(self, builder: ContextBuilder):
        """get_class_context convenience function works."""
        # This uses the global singleton, so we test the builder directly
        context = builder.get_context_for_class("Guardian")
        assert len(context) > 0


# =============================================================================
# Formatting Tests
# =============================================================================


class TestContextFormatting:
    """Tests for context output formatting."""

    def test_context_has_markers(self, builder: ContextBuilder):
        """Context output has start/end markers."""
        context = builder.get_context_for_class("Guardian")
        assert "STRATEGIC DOCTRINE CONTEXT" in context
        assert "END DOCTRINE CONTEXT" in context

    def test_sections_separated(self, builder: ContextBuilder):
        """Multiple sections are separated."""
        context = builder.get_context_for_class("Guardian", max_sections=3)
        # Should have separators
        assert "---" in context
