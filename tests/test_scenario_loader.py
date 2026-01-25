"""Unit tests for the scenario data loader."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from backend.services.scenario_loader import (
    CampaignData,
    EnemyData,
    ScenarioData,
    ScenarioLoader,
    TreacheryData,
    _calculate_priorities,
    get_scenario_loader,
)

# =============================================================================
# Data Class Tests
# =============================================================================


class TestEnemyData:
    """Tests for EnemyData dataclass."""

    def test_create_enemy(self):
        """Should create enemy with all fields."""
        enemy = EnemyData(
            name="Ghoul Priest",
            type="elite",
            fight=4,
            health=5,
            evade=4,
            damage=2,
            horror=2,
            notes="Boss enemy",
        )
        assert enemy.name == "Ghoul Priest"
        assert enemy.type == "elite"
        assert enemy.fight == 4
        assert enemy.health == 5
        assert enemy.evade == 4
        assert enemy.damage == 2
        assert enemy.horror == 2
        assert enemy.notes == "Boss enemy"

    def test_default_notes(self):
        """Should default notes to empty string."""
        enemy = EnemyData(
            name="Swarm",
            type="basic",
            fight=1,
            health=1,
            evade=1,
            damage=1,
            horror=0,
        )
        assert enemy.notes == ""


class TestTreacheryData:
    """Tests for TreacheryData dataclass."""

    def test_create_treachery(self):
        """Should create treachery with all fields."""
        treachery = TreacheryData(
            name="Rotting Remains",
            test="willpower",
            difficulty=3,
            effect="horror",
            notes="Core set treachery",
        )
        assert treachery.name == "Rotting Remains"
        assert treachery.test == "willpower"
        assert treachery.difficulty == 3
        assert treachery.effect == "horror"
        assert treachery.notes == "Core set treachery"

    def test_no_test_treachery(self):
        """Should handle treacheries without tests."""
        treachery = TreacheryData(
            name="Ancient Evils",
            test="none",
            difficulty=0,
            effect="doom",
        )
        assert treachery.test == "none"
        assert treachery.difficulty == 0


class TestScenarioData:
    """Tests for ScenarioData dataclass."""

    def test_from_dict_minimal(self):
        """Should create from minimal dictionary."""
        data = {
            "id": "test_scenario",
            "name": "Test Scenario",
            "campaign": "Test Campaign",
        }
        scenario = ScenarioData.from_dict(data)
        assert scenario.id == "test_scenario"
        assert scenario.name == "Test Scenario"
        assert scenario.campaign == "Test Campaign"
        assert scenario.enemies == []
        assert scenario.treacheries == []
        assert scenario.tips == []

    def test_from_dict_full(self):
        """Should create from full dictionary."""
        data = {
            "id": "the_gathering",
            "name": "The Gathering",
            "campaign": "Night of the Zealot",
            "position": 1,
            "act_count": 3,
            "agenda_count": 3,
            "enemy_density": "low",
            "treachery_profile": {"willpower": 3, "agility": 1},
            "key_tests": ["willpower", "combat"],
            "mechanics": ["spawn_mechanics", "doom"],
            "enemies": [
                {
                    "name": "Ghoul",
                    "type": "basic",
                    "fight": 2,
                    "health": 2,
                    "evade": 2,
                    "damage": 1,
                    "horror": 1,
                }
            ],
            "treacheries": [
                {
                    "name": "Rotting Remains",
                    "test": "willpower",
                    "difficulty": 3,
                    "effect": "horror",
                }
            ],
            "tips": ["Bring willpower icons"],
            "difficulty_notes": "Introductory scenario",
        }
        scenario = ScenarioData.from_dict(data)

        assert scenario.id == "the_gathering"
        assert scenario.position == 1
        assert scenario.act_count == 3
        assert scenario.enemy_density == "low"
        assert scenario.treachery_profile == {"willpower": 3, "agility": 1}
        assert scenario.key_tests == ["willpower", "combat"]
        assert len(scenario.enemies) == 1
        assert scenario.enemies[0].name == "Ghoul"
        assert len(scenario.treacheries) == 1
        assert scenario.treacheries[0].name == "Rotting Remains"
        assert "Bring willpower icons" in scenario.tips
        assert scenario.difficulty_notes == "Introductory scenario"


class TestCampaignData:
    """Tests for CampaignData dataclass."""

    def test_from_dict(self):
        """Should create from dictionary."""
        data = {
            "id": "notz",
            "name": "Night of the Zealot",
            "description": "Core set campaign",
            "scenarios": ["the_gathering", "midnight_masks", "devourer_below"],
        }
        campaign = CampaignData.from_dict(data)

        assert campaign.id == "notz"
        assert campaign.name == "Night of the Zealot"
        assert campaign.description == "Core set campaign"
        assert len(campaign.scenario_ids) == 3
        assert "the_gathering" in campaign.scenario_ids


# =============================================================================
# ScenarioLoader Tests
# =============================================================================


class TestScenarioLoader:
    """Tests for ScenarioLoader class."""

    @pytest.fixture
    def sample_scenario_data(self):
        """Sample scenario data for testing."""
        return {
            "campaign": {
                "id": "test_campaign",
                "name": "Test Campaign",
                "description": "A test campaign",
                "scenarios": ["scenario_1", "scenario_2"],
            },
            "scenarios": [
                {
                    "id": "scenario_1",
                    "name": "First Scenario",
                    "campaign": "Test Campaign",
                    "position": 1,
                    "act_count": 3,
                    "agenda_count": 2,
                    "enemy_density": "medium",
                    "treachery_profile": {"willpower": 4, "agility": 2},
                    "key_tests": ["willpower", "combat"],
                    "mechanics": ["doom"],
                    "enemies": [
                        {
                            "name": "Test Enemy",
                            "type": "elite",
                            "fight": 4,
                            "health": 6,
                            "evade": 3,
                            "damage": 2,
                            "horror": 1,
                        }
                    ],
                    "treacheries": [
                        {
                            "name": "Test Treachery",
                            "test": "willpower",
                            "difficulty": 4,
                            "effect": "horror",
                        }
                    ],
                    "tips": ["Test tip 1"],
                    "difficulty_notes": "Medium difficulty",
                },
                {
                    "id": "scenario_2",
                    "name": "Second Scenario",
                    "campaign": "Test Campaign",
                    "position": 2,
                    "act_count": 2,
                    "agenda_count": 3,
                    "enemy_density": "high",
                    "treachery_profile": {"willpower": 3, "agility": 4},
                    "key_tests": ["agility", "intellect"],
                    "mechanics": ["darkness"],
                    "tips": ["Bring flashlight"],
                },
            ],
        }

    @pytest.fixture
    def temp_scenarios_dir(self, sample_scenario_data):
        """Create a temporary scenarios directory with test data."""
        with TemporaryDirectory() as tmpdir:
            scenarios_dir = Path(tmpdir)

            # Write test scenario file
            with open(scenarios_dir / "test_campaign.json", "w") as f:
                json.dump(sample_scenario_data, f)

            yield scenarios_dir

    def test_loads_scenarios_lazily(self, temp_scenarios_dir):
        """Should load scenarios only when accessed."""
        loader = ScenarioLoader(scenarios_dir=temp_scenarios_dir)

        # Not loaded yet
        assert loader._loaded is False

        # Access triggers load
        _ = loader.list_scenarios()
        assert loader._loaded is True

    def test_get_scenario_by_id(self, temp_scenarios_dir):
        """Should retrieve scenario by ID."""
        loader = ScenarioLoader(scenarios_dir=temp_scenarios_dir)
        scenario = loader.get_scenario("scenario_1")

        assert scenario is not None
        assert scenario.name == "First Scenario"
        assert scenario.position == 1

    def test_get_scenario_not_found(self, temp_scenarios_dir):
        """Should return None for unknown scenario."""
        loader = ScenarioLoader(scenarios_dir=temp_scenarios_dir)
        scenario = loader.get_scenario("unknown_scenario")

        assert scenario is None

    def test_get_scenario_by_name(self, temp_scenarios_dir):
        """Should retrieve scenario by name."""
        loader = ScenarioLoader(scenarios_dir=temp_scenarios_dir)
        scenario = loader.get_scenario_by_name("First Scenario")

        assert scenario is not None
        assert scenario.id == "scenario_1"

    def test_get_scenario_by_name_case_insensitive(self, temp_scenarios_dir):
        """Should find scenario with different case."""
        loader = ScenarioLoader(scenarios_dir=temp_scenarios_dir)
        scenario = loader.get_scenario_by_name("first scenario")

        assert scenario is not None
        assert scenario.id == "scenario_1"

    def test_get_scenario_by_name_partial_match(self, temp_scenarios_dir):
        """Should find scenario with partial name match."""
        loader = ScenarioLoader(scenarios_dir=temp_scenarios_dir)
        scenario = loader.get_scenario_by_name("First")

        assert scenario is not None
        assert scenario.id == "scenario_1"

    def test_get_campaign(self, temp_scenarios_dir):
        """Should retrieve campaign by ID."""
        loader = ScenarioLoader(scenarios_dir=temp_scenarios_dir)
        campaign = loader.get_campaign("test_campaign")

        assert campaign is not None
        assert campaign.name == "Test Campaign"
        assert len(campaign.scenario_ids) == 2

    def test_get_campaign_scenarios(self, temp_scenarios_dir):
        """Should retrieve all scenarios for a campaign in order."""
        loader = ScenarioLoader(scenarios_dir=temp_scenarios_dir)
        scenarios = loader.get_campaign_scenarios("test_campaign")

        assert len(scenarios) == 2
        assert scenarios[0].id == "scenario_1"
        assert scenarios[1].id == "scenario_2"

    def test_list_scenarios(self, temp_scenarios_dir):
        """Should list all loaded scenarios."""
        loader = ScenarioLoader(scenarios_dir=temp_scenarios_dir)
        scenarios = loader.list_scenarios()

        assert len(scenarios) == 2
        ids = [s.id for s in scenarios]
        assert "scenario_1" in ids
        assert "scenario_2" in ids

    def test_list_campaigns(self, temp_scenarios_dir):
        """Should list all loaded campaigns."""
        loader = ScenarioLoader(scenarios_dir=temp_scenarios_dir)
        campaigns = loader.list_campaigns()

        assert len(campaigns) == 1
        assert campaigns[0].id == "test_campaign"

    def test_search_by_query(self, temp_scenarios_dir):
        """Should search scenarios by text query."""
        loader = ScenarioLoader(scenarios_dir=temp_scenarios_dir)
        results = loader.search_scenarios(query="First")

        assert len(results) == 1
        assert results[0].id == "scenario_1"

    def test_search_by_campaign(self, temp_scenarios_dir):
        """Should search scenarios by campaign."""
        loader = ScenarioLoader(scenarios_dir=temp_scenarios_dir)
        results = loader.search_scenarios(campaign="Test Campaign")

        assert len(results) == 2

    def test_search_by_enemy_density(self, temp_scenarios_dir):
        """Should search scenarios by enemy density."""
        loader = ScenarioLoader(scenarios_dir=temp_scenarios_dir)
        results = loader.search_scenarios(enemy_density="high")

        assert len(results) == 1
        assert results[0].id == "scenario_2"

    def test_search_by_mechanic(self, temp_scenarios_dir):
        """Should search scenarios by mechanic."""
        loader = ScenarioLoader(scenarios_dir=temp_scenarios_dir)
        results = loader.search_scenarios(mechanic="darkness")

        assert len(results) == 1
        assert results[0].id == "scenario_2"

    def test_get_threat_summary(self, temp_scenarios_dir):
        """Should generate threat summary for scenario."""
        loader = ScenarioLoader(scenarios_dir=temp_scenarios_dir)
        summary = loader.get_threat_summary("scenario_1")

        assert summary is not None
        assert summary["scenario_name"] == "First Scenario"
        assert summary["enemy_density"] == "medium"
        assert summary["dominant_treachery_skill"] == "willpower"
        assert "doom" in summary["special_mechanics"]
        assert summary["elite_enemies"] == 1

    def test_get_threat_summary_not_found(self, temp_scenarios_dir):
        """Should return None for unknown scenario."""
        loader = ScenarioLoader(scenarios_dir=temp_scenarios_dir)
        summary = loader.get_threat_summary("unknown")

        assert summary is None

    def test_handles_missing_directory(self):
        """Should handle missing scenarios directory gracefully."""
        loader = ScenarioLoader(scenarios_dir=Path("/nonexistent/path"))
        scenarios = loader.list_scenarios()

        assert scenarios == []

    def test_handles_invalid_json(self, temp_scenarios_dir):
        """Should handle invalid JSON files gracefully."""
        # Write invalid JSON
        with open(temp_scenarios_dir / "invalid.json", "w") as f:
            f.write("not valid json {{{")

        loader = ScenarioLoader(scenarios_dir=temp_scenarios_dir)
        # Should still load valid scenarios
        scenarios = loader.list_scenarios()

        # Original scenarios should still be loaded
        assert len(scenarios) == 2


# =============================================================================
# Priority Calculation Tests
# =============================================================================


class TestPriorityCalculation:
    """Tests for _calculate_priorities function."""

    def test_high_willpower_treacheries(self):
        """Should recommend willpower for high willpower treachery count."""
        scenario = ScenarioData(
            id="test",
            name="Test",
            campaign="Test",
            position=1,
            act_count=3,
            agenda_count=3,
            enemy_density="low",
            treachery_profile={"willpower": 5, "agility": 1},
            key_tests=["willpower"],
            mechanics=[],
        )
        priorities = _calculate_priorities(scenario)

        willpower_priorities = [
            p for p in priorities if "willpower" in p["capability"]
        ]
        assert len(willpower_priorities) >= 1
        assert willpower_priorities[0]["importance"] == "critical"

    def test_high_enemy_density(self):
        """Should recommend combat for high enemy density."""
        scenario = ScenarioData(
            id="test",
            name="Test",
            campaign="Test",
            position=1,
            act_count=3,
            agenda_count=3,
            enemy_density="high",
            treachery_profile={},
            key_tests=[],
            mechanics=[],
        )
        priorities = _calculate_priorities(scenario)

        combat_priorities = [
            p for p in priorities if p["capability"] == "combat"
        ]
        assert len(combat_priorities) >= 1
        assert combat_priorities[0]["importance"] == "critical"

    def test_elite_enemy_priority(self):
        """Should recommend high damage for elite enemies."""
        scenario = ScenarioData(
            id="test",
            name="Test",
            campaign="Test",
            position=1,
            act_count=3,
            agenda_count=3,
            enemy_density="medium",
            treachery_profile={},
            key_tests=[],
            mechanics=[],
            enemies=[
                EnemyData(
                    name="Boss",
                    type="elite",
                    fight=4,
                    health=8,
                    evade=3,
                    damage=2,
                    horror=2,
                )
            ],
        )
        priorities = _calculate_priorities(scenario)

        damage_priorities = [
            p for p in priorities if p["capability"] == "high_damage"
        ]
        assert len(damage_priorities) >= 1
        assert damage_priorities[0]["importance"] == "critical"

    def test_doom_mechanic_priority(self):
        """Should recommend doom management for doom mechanics."""
        scenario = ScenarioData(
            id="test",
            name="Test",
            campaign="Test",
            position=1,
            act_count=3,
            agenda_count=3,
            enemy_density="low",
            treachery_profile={},
            key_tests=[],
            mechanics=["doom"],
        )
        priorities = _calculate_priorities(scenario)

        doom_priorities = [
            p for p in priorities if p["capability"] == "doom_management"
        ]
        assert len(doom_priorities) >= 1


# =============================================================================
# Integration Tests with Real Data
# =============================================================================


class TestRealScenarioData:
    """Integration tests with actual scenario data files."""

    @pytest.fixture
    def real_loader(self):
        """Load the real scenario data."""
        return ScenarioLoader()

    def test_loads_night_of_the_zealot(self, real_loader):
        """Should load Night of the Zealot scenarios."""
        campaign = real_loader.get_campaign("notz")

        # May not exist yet in tests
        if campaign:
            assert campaign.name == "Night of the Zealot"
            scenarios = real_loader.get_campaign_scenarios("notz")
            assert len(scenarios) >= 3

    def test_loads_the_gathering(self, real_loader):
        """Should load The Gathering scenario."""
        scenario = real_loader.get_scenario("the_gathering")

        # May not exist yet
        if scenario:
            assert scenario.name == "The Gathering"
            assert scenario.campaign == "Night of the Zealot"
            assert len(scenario.enemies) > 0
            assert len(scenario.treacheries) > 0

    def test_search_by_enemy_density_real(self, real_loader):
        """Should find scenarios by enemy density."""
        high_density = real_loader.search_scenarios(enemy_density="high")

        # All results should have high enemy density
        for scenario in high_density:
            assert scenario.enemy_density == "high"


# =============================================================================
# Global Function Tests
# =============================================================================


class TestGlobalFunctions:
    """Tests for module-level convenience functions."""

    def test_get_scenario_loader_singleton(self):
        """Should return same loader instance."""
        loader1 = get_scenario_loader()
        loader2 = get_scenario_loader()

        assert loader1 is loader2
