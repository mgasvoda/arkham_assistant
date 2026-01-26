# AI Agent Design — Arkham Assistant

## Overview

Local AI agent for deck analysis, recommendations, and conversational assistance. Uses function calling to orchestrate backend tools.

**LLM:** OpenAI GPT-5 (or local model via Ollama/LM Studio)

---

## Agent Capabilities

The agent acts as a deckbuilding advisor with access to:
- Card database queries
- Deck composition analysis
- Simulation execution and interpretation
- Static rule/meta knowledge
- Recommendation generation

**Key principle:** Agent has no direct web access; all data comes from ChromaDB or static files.

---

## Available Tools (Function Calls)

### 1. `get_card_details(card_ids: List[str]) → List[Card]`
- Query ChromaDB for specific cards by ID
- Returns full card data (cost, type, text, icons, etc.)
- Use for: looking up cards mentioned in conversation

### 2. `get_deck(deck_id: str) → Deck`
- Retrieve deck definition from ChromaDB
- Returns: character, card list, archetype, notes, cached sim reports
- Use for: analyzing existing decks

### 3. `run_simulation(deck_id: str, n_trials: int = 1000) → SimReport`
- Execute deck simulation via backend simulator
- Returns metrics: avg draws, setup time, success rate, key card reliability
- Use for: quantitative deck evaluation

### 4. `get_static_info(topic: str) → str`
- Read markdown files from `/backend/static/`
- Topics: "rules", "meta", "owned_sets", "archetype:<name>"
- Use for: answering game rule questions, checking card ownership

### 5. `recommend_cards(deck_id: str, goal: str = "balance") → List[Recommendation]`
- LLM-driven analysis of deck composition
- Suggests swaps based on curve, archetype fit, and synergies
- Returns structured recommendations with reasoning

### 6. `summarize_deck(deck_id: str) → Summary`
- Generate high-level deck summary
- Outputs: curve shape, class distribution, archetype labels, tempo assessment
- Use for: quick deck overview in chat

---

## Agent Prompt (System Message)

```
You are an expert Arkham Horror: The Card Game deckbuilding assistant.

Your role:
- Analyze decks for balance, synergy, and consistency
- Recommend card swaps to improve performance
- Interpret simulation results in player-friendly terms
- Answer rules questions using static reference files
- Respect the user's card ownership (check owned_sets.md)

Guidelines:
- Be concise but insightful
- Use simulation data to back up recommendations
- Respect deckbuilding restrictions (check character rules)
- Avoid recommending cards the user doesn't own unless asked
- When suggesting swaps, explain WHY (curve, synergy, consistency)

Available tools: get_card_details, get_deck, run_simulation, get_static_info, 
                 recommend_cards, summarize_deck
```

---

## Conversation Flow Examples

### Example 1: Deck Analysis Request

**User:** "Analyze my deck_001"

**Agent reasoning:**
1. Call `get_deck('deck_001')`
2. Call `summarize_deck('deck_001')`
3. Call `run_simulation('deck_001')`
4. Synthesize results into response

**Response format:**
```
📊 Deck Summary: Seeker Clue-Focused (Roland Banks)
- 17 assets / 8 events / 5 skills
- Curve: slightly top-heavy (avg cost 2.4)
- Simulation: 74% success rate, 2.8 turn setup

🔧 Recommendations:
- Consider replacing "Flashlight" → "Sixth Sense" (better reliability)
- Add "Deduction" for faster clue tempo
```

---

### Example 2: Card Recommendation

**User:** "I need better card draw for this deck"

**Agent reasoning:**
1. Call `get_deck(active_deck_id)` to check class/archetype
2. Call `get_static_info('owned_sets')` to filter cards
3. Call `recommend_cards(deck_id, goal='card_draw')`
4. Return top 3-5 options with explanations

---

### Example 3: Rules Question

**User:** "Can I take two actions to move twice?"

**Agent reasoning:**
1. Call `get_static_info('rules')`
2. Find relevant section on action economy
3. Return plain-language answer

---

## Tool Call Sequencing

**Best practices:**
- Always call `get_deck()` before making recommendations
- Run `run_simulation()` for quantitative backing (but don't over-simulate)
- Use `get_static_info('owned_sets')` when suggesting new cards
- Cache simulation results in deck metadata to avoid redundant runs

---

## Structured Output Schema

For recommendations, agent returns JSON:

```json
{
  "summary": "Your deck has strong early game but weak late-game tempo.",
  "recommendations": [
    {
      "action": "swap",
      "remove": "Flashlight",
      "add": "Sixth Sense",
      "reason": "Better scaling for clue gathering in late scenario"
    },
    {
      "action": "add",
      "card": "Emergency Cache",
      "reason": "Helps smooth resource curve"
    }
  ],
  "simulation_summary": {
    "success_rate": 0.74,
    "setup_time": 2.8,
    "key_issues": ["Slow card draw", "High variance in opening hand"]
  }
}
```

---

## Integration with Backend

**Endpoint:** `POST /chat`

**Request:**
```json
{
  "deck_id": "deck_001",
  "message": "analyze this deck",
  "context": []  // optional previous messages
}
```

**Response:**
```json
{
  "reply": "📊 Deck Summary: ...",
  "structured_data": { ... },
  "tool_calls": ["get_deck", "run_simulation", "summarize_deck"]
}
```

---

## Implementation Notes

- Use OpenAI function calling API or equivalent (LangChain, etc.)
- Keep system prompt focused and concise
- Log all tool calls for debugging
- Handle tool failures gracefully (e.g., missing deck → friendly error)
- Rate-limit simulation calls (expensive operation)

---

## File Structure

```
backend/services/
├── agent_tools.py          # Tool function implementations
├── agent_orchestrator.py   # Backward-compatible exports
├── orchestrator.py         # LangGraph orchestrator implementation
└── prompts.py              # System prompts and schemas

backend/services/subagents/
├── base.py                 # BaseSubagent class with LangGraph pattern
├── rules_agent.py          # RulesAgent for deckbuilding rules
├── state_agent.py          # StateAgent for deck composition analysis
├── action_space_agent.py   # ActionSpaceAgent for card search
├── scenario_agent.py       # ScenarioAgent for scenario preparation
├── cache.py                # Subagent response caching
└── utils.py                # Shared utilities
```

---

## Orchestrator Architecture (LangGraph)

The orchestrator uses LangGraph to coordinate specialized subagents:

### Graph Structure
```
START → analyze_request → route_to_subagents → collect_responses → synthesize → END
```

### Subagent Types

| Agent | Purpose | Uses LLM |
|-------|---------|----------|
| RulesAgent | Deckbuilding rules, card legality | Yes (with hybrid retrieval) |
| StateAgent | Deck composition analysis | No (pure analysis) |
| ActionSpaceAgent | Card search and filtering | No (ChromaDB search) |
| ScenarioAgent | Scenario threat analysis | Yes (with scenario data) |

### Request/Response Models

**OrchestratorRequest:**
```python
{
    "message": str,              # User's question
    "investigator_id": str?,     # e.g., "01001"
    "investigator_name": str?,   # e.g., "Roland Banks"
    "deck_id": str?,             # Deck to analyze
    "deck_cards": list | dict?,  # Card IDs in deck
    "scenario_name": str?,       # e.g., "The Gathering"
    "campaign_name": str?,       # e.g., "Night of the Zealot"
    "upgrade_xp": int?,          # Available XP
    "owned_sets": list[str]?     # Owned expansions
}
```

**OrchestratorResponse:**
```python
{
    "content": str,              # Synthesized response
    "recommendation": str?,      # Specific actionable advice
    "confidence": float,         # 0-1 score
    "subagent_results": list,    # Individual subagent responses
    "agents_consulted": list,    # Which agents were used
    "metadata": dict             # Routing info, stats
}
```

### Routing Logic

The orchestrator routes queries based on keywords and context:
- **Rules questions** → RulesAgent (keywords: "legal", "include", "taboo")
- **Deck analysis** → StateAgent (keywords: "analyze", "gaps", "curve")
- **Card search** → ActionSpaceAgent (keywords: "find", "recommend", "suggest")
- **Scenario prep** → ScenarioAgent (keywords: "scenario", "prepare", "threats")

Context also triggers routing:
- Deck context provided → StateAgent added
- Scenario name provided → ScenarioAgent added
- Upgrade XP provided → ActionSpaceAgent added

### Usage Example

```python
from backend.services.orchestrator import create_orchestrator, OrchestratorRequest

orchestrator = create_orchestrator()

request = OrchestratorRequest(
    message="What cards should I add for The Gathering?",
    investigator_name="Roland Banks",
    deck_cards=["01016", "01017"],
    scenario_name="The Gathering",
    upgrade_xp=5,
)

response = orchestrator.process(request)
print(response.content)
print(f"Consulted: {response.agents_consulted}")
```

### Backward Compatibility

The original `process_chat_message()` function is still available:

```python
from backend.services.agent_orchestrator import process_chat_message

result = process_chat_message(
    message="Can Roland include Shrivelling?",
    deck_id="deck_001",
    context={"investigator_name": "Roland Banks"},
)
print(result["reply"])
```

