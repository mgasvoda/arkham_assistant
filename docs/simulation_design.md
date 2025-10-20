# Simulation Service Design — Arkham Assistant

## Overview

Monte Carlo simulation engine for evaluating Arkham Horror LCG deck performance. Simulates opening draws, mulligans, and early-game sequences to assess consistency and tempo.

**Goal:** Provide quantitative feedback on deck reliability without requiring manual playtesting.

---

## Input

```python
{
  "deck_id": "deck_001",  # or
  "card_list": ["card_001", "card_002", ...],  # direct card list
  "n_trials": 1000,  # number of simulations to run
  "config": {
    "mulligan_strategy": "aggressive",  # or "conservative"
    "target_cards": ["card_123", "card_456"],  # key cards to track
    "turns_to_simulate": 5  # simulate first N turns
  }
}
```

---

## Simulation Process

### 1. Deck Setup
- Load card list from ChromaDB (if `deck_id` provided)
- Validate deck size (30 cards for standard decks)
- Parse card costs, types, and functions

### 2. Opening Draw (per trial)
- Shuffle deck
- Draw 5 cards (standard opening hand)
- Apply mulligan strategy:
  - **Aggressive:** Mulligan if no resource or key card present
  - **Conservative:** Keep hand if at least 2 playable cards

### 3. Turn Simulation
For each of `turns_to_simulate` turns:
- Draw 1 card
- Gain 1 resource (+1 per turn)
- Simulate optimal play order:
  - Play cheap assets first
  - Hold events for specific triggers
  - Track cumulative board state
- Record metrics (see below)

### 4. Metrics Collection
Track per trial:
- **Setup time:** Turns until 2+ assets in play
- **Resource efficiency:** % of resources spent vs. generated
- **Key card arrival:** Turn when target cards drawn
- **Hand quality:** Average playable cards per turn

---

## Output Schema

```json
{
  "deck_id": "deck_001",
  "n_trials": 1000,
  "timestamp": "2025-10-20T10:30:00Z",
  "metrics": {
    "avg_setup_time": 2.8,
    "avg_draws_to_key_card": 3.1,
    "success_rate": 0.74,  // % of trials with "good" opening
    "mulligan_rate": 0.43,  // % of hands mulliganed
    "resource_efficiency": 0.68,
    "curve_distribution": {
      "0": 0.12,
      "1": 0.18,
      "2": 0.34,
      "3": 0.22,
      "4+": 0.14
    }
  },
  "key_card_reliability": {
    "card_123": {
      "avg_turn_drawn": 2.3,
      "probability_by_turn_3": 0.85
    },
    "card_456": {
      "avg_turn_drawn": 4.1,
      "probability_by_turn_3": 0.52
    }
  },
  "warnings": [
    "High variance in opening hands (consider more 0-1 cost cards)",
    "Key card 'card_456' arrives late in 48% of trials"
  ]
}
```

---

## Key Metrics Explained

### 1. Setup Time
**Definition:** Average turns until player has 2+ assets in play.

**Good:** < 3 turns  
**Poor:** > 4 turns

### 2. Success Rate
**Definition:** % of trials where:
- At least 1 key card drawn by turn 3
- At least 2 playable cards in opening hand (post-mulligan)
- Resource curve allows playing cards on-curve

**Good:** > 70%  
**Poor:** < 50%

### 3. Key Card Reliability
**Definition:** For each "key card" (specified in config or inferred):
- Average turn drawn
- Probability of drawing by turn N

**Use case:** Assess consistency of core combo pieces.

### 4. Resource Efficiency
**Definition:** Average % of resources spent by turn N.

**Interpretation:**
- Low (<50%): Deck may be too expensive or clunky
- High (>80%): Good curve and playability

---

## Mulligan Strategies

### Aggressive
Keep hand only if:
- Contains at least 1 resource-generating card, OR
- Contains at least 1 key card from `target_cards`

### Conservative
Keep hand if:
- Contains at least 2 cards playable by turn 2

---

## Simulation Assumptions

**Simplifications (v0.1):**
- No enemy or treachery interactions
- No skill tests (assume all tests pass)
- No card draw effects (beyond base 1/turn)
- No resource generation effects (assume 1/turn)
- Assets play immediately (no timing restrictions)

**Future expansions:**
- Model card draw effects (e.g., "Draw 1 card")
- Model resource generation (e.g., "Gain 1 resource")
- Simulate skill test outcomes (probabilistic)

---

## Performance Considerations

- Target: < 2 seconds for 1000 trials
- Parallelize trials (Python `multiprocessing`)
- Cache simulation results in ChromaDB (deck-level)
- Invalidate cache when deck changes

---

## Integration with Backend

**Endpoint:** `POST /run_sim`

**Request:**
```json
{
  "deck_id": "deck_001",
  "n_trials": 1000,
  "config": {
    "mulligan_strategy": "aggressive",
    "target_cards": ["card_123"],
    "turns_to_simulate": 5
  }
}
```

**Response:** Full JSON metrics (see Output Schema above)

**Caching:**
- Store result in `decks` collection under `SimulationReports`
- Include timestamp and config hash
- Serve cached result if deck unchanged

---

## File Structure

```
backend/services/
├── simulator.py         # Main simulation engine
├── sim_config.py        # Default configs and strategies
└── sim_metrics.py       # Metrics calculation helpers
```

---

## Implementation Notes

- Use `random.shuffle()` for deck shuffling
- Track state with simple data structures (lists, counters)
- Generate human-readable warnings (e.g., "curve too high")
- Expose simulation as standalone module (testable without API)

