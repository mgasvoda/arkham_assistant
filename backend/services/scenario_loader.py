"""Scenario data loading utility.

This module provides functionality to load and access scenario data from
static JSON files. Scenarios contain threat profiles, enemy information,
treachery data, and preparation tips for Arkham Horror LCG scenarios.

Usage:
    loader = ScenarioLoader()
    scenario = loader.get_scenario("the_gathering")
    campaign = loader.get_campaign("notz")
    all_scenarios = loader.list_scenarios()
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class EnemyData:
    """Data about an enemy in a scenario.

    Attributes:
        name: Enemy name.
        type: Enemy type (basic, elite, ancient_one, cultist).
        fight: Fight difficulty.
        health: Health value.
        evade: Evade difficulty.
        damage: Damage dealt per attack.
        horror: Horror dealt per attack.
        notes: Additional notes about the enemy.
    """

    name: str
    type: str
    fight: int
    health: int
    evade: int
    damage: int
    horror: int
    notes: str = ""


@dataclass
class TreacheryData:
    """Data about a treachery in a scenario.

    Attributes:
        name: Treachery name.
        test: Skill test required (willpower, agility, etc.) or "none".
        difficulty: Test difficulty (0 if no test).
        effect: Type of effect (horror, damage, doom, etc.).
        notes: Additional notes about the treachery.
    """

    name: str
    test: str
    difficulty: int
    effect: str
    notes: str = ""


@dataclass
class ScenarioData:
    """Complete data for a scenario.

    Attributes:
        id: Unique scenario identifier.
        name: Display name of the scenario.
        campaign: Campaign this scenario belongs to.
        position: Position in campaign (1-indexed).
        act_count: Number of acts in the scenario.
        agenda_count: Number of agendas in the scenario.
        enemy_density: Enemy density level (low, medium, high).
        treachery_profile: Dict mapping skill types to frequency.
        key_tests: List of most common skill tests.
        mechanics: List of special mechanics in this scenario.
        enemies: List of enemy data.
        treacheries: List of treachery data.
        tips: List of preparation tips.
        difficulty_notes: General difficulty assessment.
    """

    id: str
    name: str
    campaign: str
    position: int
    act_count: int
    agenda_count: int
    enemy_density: str
    treachery_profile: dict[str, int]
    key_tests: list[str]
    mechanics: list[str]
    enemies: list[EnemyData] = field(default_factory=list)
    treacheries: list[TreacheryData] = field(default_factory=list)
    tips: list[str] = field(default_factory=list)
    difficulty_notes: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ScenarioData":
        """Create ScenarioData from a dictionary.

        Args:
            data: Dictionary with scenario data.

        Returns:
            ScenarioData instance.
        """
        enemies = [
            EnemyData(**enemy) for enemy in data.get("enemies", [])
        ]
        treacheries = [
            TreacheryData(**treachery) for treachery in data.get("treacheries", [])
        ]

        return cls(
            id=data["id"],
            name=data["name"],
            campaign=data["campaign"],
            position=data.get("position", 0),
            act_count=data.get("act_count", 0),
            agenda_count=data.get("agenda_count", 0),
            enemy_density=data.get("enemy_density", "medium"),
            treachery_profile=data.get("treachery_profile", {}),
            key_tests=data.get("key_tests", []),
            mechanics=data.get("mechanics", []),
            enemies=enemies,
            treacheries=treacheries,
            tips=data.get("tips", []),
            difficulty_notes=data.get("difficulty_notes", ""),
        )


@dataclass
class CampaignData:
    """Campaign metadata.

    Attributes:
        id: Unique campaign identifier.
        name: Display name of the campaign.
        description: Campaign description.
        scenario_ids: List of scenario IDs in order.
    """

    id: str
    name: str
    description: str
    scenario_ids: list[str]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CampaignData":
        """Create CampaignData from a dictionary.

        Args:
            data: Dictionary with campaign data.

        Returns:
            CampaignData instance.
        """
        return cls(
            id=data["id"],
            name=data["name"],
            description=data.get("description", ""),
            scenario_ids=data.get("scenarios", []),
        )


# =============================================================================
# Scenario Loader
# =============================================================================


class ScenarioLoader:
    """Loads and provides access to scenario data from static files.

    The loader reads JSON files from the static/scenarios directory and
    provides methods to query scenario and campaign data.

    Attributes:
        scenarios_dir: Path to the scenarios directory.
        _scenarios: Cached scenario data.
        _campaigns: Cached campaign data.
    """

    def __init__(self, scenarios_dir: Path | None = None):
        """Initialize the scenario loader.

        Args:
            scenarios_dir: Path to scenarios directory. If None, uses default.
        """
        if scenarios_dir is None:
            self.scenarios_dir = (
                Path(__file__).parent.parent / "static" / "scenarios"
            )
        else:
            self.scenarios_dir = scenarios_dir

        self._scenarios: dict[str, ScenarioData] = {}
        self._campaigns: dict[str, CampaignData] = {}
        self._loaded = False

    def _ensure_loaded(self) -> None:
        """Ensure data is loaded from files."""
        if not self._loaded:
            self._load_all_data()
            self._loaded = True

    def _load_all_data(self) -> None:
        """Load all scenario data from JSON files."""
        if not self.scenarios_dir.exists():
            return

        for file_path in self.scenarios_dir.glob("*.json"):
            try:
                with open(file_path, encoding="utf-8") as f:
                    data = json.load(f)

                # Load campaign data
                if "campaign" in data:
                    campaign = CampaignData.from_dict(data["campaign"])
                    self._campaigns[campaign.id] = campaign

                # Load scenario data
                if "scenarios" in data:
                    for scenario_dict in data["scenarios"]:
                        scenario = ScenarioData.from_dict(scenario_dict)
                        self._scenarios[scenario.id] = scenario

            except (json.JSONDecodeError, KeyError, OSError) as e:
                # Log error but continue loading other files
                print(f"Warning: Failed to load {file_path}: {e}")

    def get_scenario(self, scenario_id: str) -> ScenarioData | None:
        """Get scenario data by ID.

        Args:
            scenario_id: The scenario identifier.

        Returns:
            ScenarioData if found, None otherwise.
        """
        self._ensure_loaded()
        return self._scenarios.get(scenario_id)

    def get_scenario_by_name(self, name: str) -> ScenarioData | None:
        """Get scenario data by name (case-insensitive).

        Args:
            name: The scenario name.

        Returns:
            ScenarioData if found, None otherwise.
        """
        self._ensure_loaded()
        name_lower = name.lower()

        for scenario in self._scenarios.values():
            if scenario.name.lower() == name_lower:
                return scenario

        # Try partial matching
        for scenario in self._scenarios.values():
            if name_lower in scenario.name.lower():
                return scenario

        return None

    def get_campaign(self, campaign_id: str) -> CampaignData | None:
        """Get campaign data by ID.

        Args:
            campaign_id: The campaign identifier.

        Returns:
            CampaignData if found, None otherwise.
        """
        self._ensure_loaded()
        return self._campaigns.get(campaign_id)

    def get_campaign_scenarios(self, campaign_id: str) -> list[ScenarioData]:
        """Get all scenarios for a campaign in order.

        Args:
            campaign_id: The campaign identifier.

        Returns:
            List of ScenarioData in campaign order.
        """
        self._ensure_loaded()
        campaign = self._campaigns.get(campaign_id)
        if not campaign:
            return []

        scenarios = []
        for scenario_id in campaign.scenario_ids:
            scenario = self._scenarios.get(scenario_id)
            if scenario:
                scenarios.append(scenario)

        return scenarios

    def list_scenarios(self) -> list[ScenarioData]:
        """Get all loaded scenarios.

        Returns:
            List of all ScenarioData.
        """
        self._ensure_loaded()
        return list(self._scenarios.values())

    def list_campaigns(self) -> list[CampaignData]:
        """Get all loaded campaigns.

        Returns:
            List of all CampaignData.
        """
        self._ensure_loaded()
        return list(self._campaigns.values())

    def search_scenarios(
        self,
        query: str | None = None,
        campaign: str | None = None,
        enemy_density: str | None = None,
        mechanic: str | None = None,
    ) -> list[ScenarioData]:
        """Search scenarios by various criteria.

        Args:
            query: Text to search in scenario name.
            campaign: Campaign name to filter by.
            enemy_density: Enemy density level to filter by.
            mechanic: Mechanic that must be present.

        Returns:
            List of matching scenarios.
        """
        self._ensure_loaded()
        results = list(self._scenarios.values())

        if query:
            query_lower = query.lower()
            results = [
                s for s in results
                if query_lower in s.name.lower() or query_lower in s.id
            ]

        if campaign:
            campaign_lower = campaign.lower()
            results = [
                s for s in results
                if campaign_lower in s.campaign.lower()
            ]

        if enemy_density:
            results = [
                s for s in results
                if s.enemy_density == enemy_density
            ]

        if mechanic:
            mechanic_lower = mechanic.lower()
            results = [
                s for s in results
                if any(mechanic_lower in m.lower() for m in s.mechanics)
            ]

        return results

    def get_threat_summary(self, scenario_id: str) -> dict[str, Any] | None:
        """Get a summarized threat profile for a scenario.

        Args:
            scenario_id: The scenario identifier.

        Returns:
            Dictionary with threat summary, or None if not found.
        """
        scenario = self.get_scenario(scenario_id)
        if not scenario:
            return None

        # Calculate dominant skill tests
        dominant_treachery = max(
            scenario.treachery_profile.items(),
            key=lambda x: x[1],
            default=("none", 0),
        )

        # Count enemy threat level
        elite_count = sum(1 for e in scenario.enemies if e.type in ("elite", "ancient_one"))
        high_fight_count = sum(1 for e in scenario.enemies if e.fight >= 4)

        return {
            "scenario_name": scenario.name,
            "campaign": scenario.campaign,
            "enemy_density": scenario.enemy_density,
            "dominant_treachery_skill": dominant_treachery[0],
            "treachery_intensity": sum(scenario.treachery_profile.values()),
            "key_tests": scenario.key_tests,
            "special_mechanics": scenario.mechanics,
            "elite_enemies": elite_count,
            "high_combat_enemies": high_fight_count,
            "recommended_priorities": _calculate_priorities(scenario),
        }


def _calculate_priorities(scenario: ScenarioData) -> list[dict[str, str]]:
    """Calculate preparation priorities for a scenario.

    Args:
        scenario: The scenario to analyze.

    Returns:
        List of priority dictionaries with capability, importance, and reason.
    """
    priorities = []

    # Treachery-based priorities
    treachery_profile = scenario.treachery_profile
    if treachery_profile.get("willpower", 0) >= 4:
        priorities.append({
            "capability": "willpower_icons",
            "importance": "critical",
            "reason": f"High willpower treachery count ({treachery_profile['willpower']})",
        })
    elif treachery_profile.get("willpower", 0) >= 2:
        priorities.append({
            "capability": "willpower_icons",
            "importance": "important",
            "reason": "Moderate willpower treachery presence",
        })

    if treachery_profile.get("agility", 0) >= 3:
        priorities.append({
            "capability": "agility_icons",
            "importance": "important",
            "reason": f"Agility tests common ({treachery_profile['agility']})",
        })

    # Combat-based priorities
    if scenario.enemy_density == "high":
        priorities.append({
            "capability": "combat",
            "importance": "critical",
            "reason": "High enemy density scenario",
        })
    elif scenario.enemy_density == "medium":
        priorities.append({
            "capability": "combat",
            "importance": "important",
            "reason": "Moderate enemy presence",
        })

    # Check for elite enemies
    elite_enemies = [e for e in scenario.enemies if e.type in ("elite", "ancient_one")]
    if elite_enemies:
        max_health = max(e.health for e in elite_enemies)
        if max_health >= 6:
            priorities.append({
                "capability": "high_damage",
                "importance": "critical",
                "reason": f"Elite enemy with {max_health} health",
            })

    # Horror assessment
    horror_dealing = sum(e.horror for e in scenario.enemies)
    if horror_dealing >= 5 or treachery_profile.get("willpower", 0) >= 4:
        priorities.append({
            "capability": "horror_soak",
            "importance": "important",
            "reason": "Multiple horror sources",
        })

    # Mechanic-based priorities
    mechanics_lower = [m.lower() for m in scenario.mechanics]
    if "doom" in mechanics_lower:
        priorities.append({
            "capability": "doom_management",
            "importance": "important",
            "reason": "Doom mechanic present - time pressure",
        })

    if "darkness" in mechanics_lower or "invisible" in mechanics_lower:
        priorities.append({
            "capability": "investigation_boost",
            "importance": "important",
            "reason": "Darkness/visibility mechanics",
        })

    # Movement efficiency
    if "train" in scenario.name.lower() or "express" in scenario.name.lower():
        priorities.append({
            "capability": "extra_actions",
            "importance": "critical",
            "reason": "Linear movement scenario - action efficiency crucial",
        })

    return priorities


# =============================================================================
# Convenience functions
# =============================================================================


_default_loader: ScenarioLoader | None = None


def get_scenario_loader() -> ScenarioLoader:
    """Get the default scenario loader instance.

    Returns:
        ScenarioLoader instance.
    """
    global _default_loader
    if _default_loader is None:
        _default_loader = ScenarioLoader()
    return _default_loader


def get_scenario(scenario_id: str) -> ScenarioData | None:
    """Get scenario data by ID using the default loader.

    Args:
        scenario_id: The scenario identifier.

    Returns:
        ScenarioData if found, None otherwise.
    """
    return get_scenario_loader().get_scenario(scenario_id)


def get_scenario_by_name(name: str) -> ScenarioData | None:
    """Get scenario data by name using the default loader.

    Args:
        name: The scenario name.

    Returns:
        ScenarioData if found, None otherwise.
    """
    return get_scenario_loader().get_scenario_by_name(name)
