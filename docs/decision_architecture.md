# Decision Architecture: State, Doctrine, Action Space, Rules

*Proposed architecture for deck recommendation system*

## Overview

This document describes a conceptual framework for decomposing strategic decisions into four components, and how this maps to the Arkham Assistant's subagent architecture.

## The Four Components of a Decision

| Component | Definition | Role in Decision |
|-----------|------------|------------------|
| **State** | External inputs that inform the decision | What you know |
| **Doctrine** | Internal understanding of "good" + biases | How you evaluate |
| **Action Space** | Affordances — things you CAN do | What's possible |
| **Rules** | Constraints that filter to "legal" choices | What's allowed |

### Neural Network Analogy

This framework maps cleanly onto neural network concepts:

```
     State                    Action Space
       │                          │
       ▼                          ▼
  ┌─────────┐               ┌─────────┐
  │  INPUT  │──── Doctrine ─▶│ OUTPUT  │
  │  LAYER  │    (weights)   │  LAYER  │
  └─────────┘               └─────────┘
                                  │
                                  ▼
                            ┌─────────┐
                            │  RULES  │ ← Mask
                            │ (filter)│
                            └─────────┘
                                  │
                                  ▼
                          Legal Actions
```

- **State** = Input layer activations
- **Doctrine** = Learned weights (what patterns matter, how to weight them)
- **Action Space** = Output layer (all possible actions)
- **Rules** = Output mask (set illegal nodes to zero)

## Current Implementation vs. Proposed

| Component | Current Implementation | Problem | Proposed Change |
|-----------|------------------------|---------|-----------------|
| **State** | `StateAgent` | ✓ Works well | Keep as-is |
| **Doctrine** | Implicit in LLM | Can't see/tune it | Context injection via `meta-trends.md` |
| **Action Space** | `ActionSpaceAgent` | ✓ Works well | Keep as-is |
| **Rules** | `RulesAgent` (retrieval + LLM interpretation) | Soft constraint, can fail | Hard Python mask |

## Proposed Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        ORCHESTRATOR                          │
└─────────────────────────────────────────────────────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   ▼
   ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
   │    STATE    │     │   ACTION    │     │   CONTEXT   │
   │    AGENT    │     │    SPACE    │     │   BUILDER   │
   │             │     │    AGENT    │     │             │
   │ Deck comp,  │     │             │     │ • meta-trends│
   │ curve, gaps │     │ Candidates  │     │ • player cnt │
   │             │     │             │     │ • campaign   │
   └─────────────┘     └─────────────┘     │ • archetype  │
          │                   │             └─────────────┘
          └───────────────────┼───────────────────┘
                              ▼
                    ┌───────────────────┐
                    │   LLM SYNTHESIS   │  ← Soft doctrine
                    │                   │    via rich context
                    │ Score and rank    │
                    │ candidates using  │
                    │ doctrine context  │
                    └───────────────────┘
                              │
                              ▼
                    ┌───────────────────┐
                    │   RULES FILTER    │  ← Hard mask
                    │                   │    (pure Python)
                    │ • Deck size = 30  │
                    │ • Max 2 copies    │
                    │ • Class access    │
                    │ • XP limits       │
                    └───────────────────┘
                              │
                              ▼
                      Legal Recommendations
```

## Key Changes

### 1. Rules as Hard Filter (Not Guidance)

**Current approach** (problematic):
```python
rules_text = retrieve("deckbuilding rules")
response = llm(f"Follow these rules: {rules_text}, recommend cards")
# LLM "tries" to follow rules, sometimes fails
```

**Proposed approach** (reliable):
```python
candidates = action_space_agent.search(query)
scored = llm_score_with_doctrine(candidates, context)
legal = rules_filter(scored, investigator, deck)  # Hard Python filter
```

The `RulesFilter` would be pure Python with no LLM interpretation:

```python
class RulesFilter:
    def filter(self, candidates: list[Card], investigator: Investigator, deck: Deck) -> list[Card]:
        legal = []
        for card in candidates:
            if not self._check_class_access(card, investigator):
                continue
            if not self._check_xp_limit(card, deck):
                continue
            if not self._check_copy_limit(card, deck):
                continue
            if not self._check_deck_size(deck):
                continue
            legal.append(card)
        return legal
    
    def _check_class_access(self, card: Card, investigator: Investigator) -> bool:
        """Check if card class is allowed by investigator deckbuilding rules."""
        allowed_classes = self._get_allowed_classes(investigator)
        return card.faction in allowed_classes or card.faction == "Neutral"
    
    def _check_xp_limit(self, card: Card, deck: Deck) -> bool:
        """Check if card XP is within budget."""
        return card.xp <= deck.available_xp
    
    def _check_copy_limit(self, card: Card, deck: Deck) -> bool:
        """Check max 2 copies rule (accounting for Myriad, Exceptional)."""
        current_copies = deck.count(card.name)
        max_copies = 1 if card.has_keyword("Exceptional") else 2
        if card.has_keyword("Myriad"):
            max_copies = 3
        return current_copies < max_copies
    
    def _check_deck_size(self, deck: Deck) -> bool:
        """Check if deck can accept more cards."""
        return len(deck) < deck.required_size
```

### 2. Doctrine via Context Injection

Instead of hardcoded scoring weights, inject relevant sections of `meta-trends.md` as context for LLM scoring.

**New component: `ContextBuilder`**

```python
class ContextBuilder:
    def __init__(self, meta_trends_path: str = "static/meta_trends.md"):
        self.meta_trends = self._load_meta_trends(meta_trends_path)
        self.section_index = self._build_section_index()
    
    def build_selection_context(
        self,
        investigator: Investigator,
        archetype: str,
        state: DeckState,
        candidates: list[Card],
        player_count: int = 1,
        campaign: str | None = None
    ) -> str:
        """Build rich context for LLM card selection."""
        
        sections = []
        
        # Class-specific doctrine
        class_section = self._get_section(f"Class Doctrine: The {investigator.faction}")
        if class_section:
            sections.append(f"## Class Doctrine: {investigator.faction}\n{class_section}")
        
        # Archetype-specific guidance
        archetype_section = self._get_archetype_section(archetype)
        if archetype_section:
            sections.append(f"## Archetype: {archetype}\n{archetype_section}")
        
        # Economy principles (always relevant)
        economy_section = self._get_section("Economy of Actions")
        if economy_section:
            sections.append(f"## Economy Principles\n{economy_section}")
        
        # Player count adjustments
        if player_count == 1:
            solo_section = self._get_section("True Solo")
            if solo_section:
                sections.append(f"## Solo Play Doctrine\n{solo_section}")
        else:
            mp_section = self._get_section("Multiplayer")
            if mp_section:
                sections.append(f"## Multiplayer Doctrine\n{mp_section}")
        
        # Campaign-specific metagaming
        if campaign:
            campaign_section = self._get_campaign_section(campaign)
            if campaign_section:
                sections.append(f"## Campaign: {campaign}\n{campaign_section}")
        
        # Current deck state
        sections.append(f"## Current Deck State\n{state.to_summary()}")
        
        # Candidate cards
        sections.append(f"## Candidate Cards\n{self._format_candidates(candidates)}")
        
        return "\n\n".join(sections)
```

**LLM scoring with doctrine context:**

```python
def score_candidates_with_doctrine(
    context: str,
    candidates: list[Card],
    llm: ChatOpenAI
) -> list[ScoredCard]:
    """Score candidates using doctrine context."""
    
    prompt = f"""You are evaluating cards for an Arkham Horror LCG deck.

{context}

For each candidate card, evaluate based on:
1. **Archetype Fit**: How well does it support the deck's primary strategy?
2. **Economy Impact**: Resource cost vs. value provided (action compression)
3. **Slot Efficiency**: Does it compete for contested slots? Is that worth it?
4. **Synergies**: Does it combo with existing cards or the investigator ability?
5. **Reliability**: How consistent is its value across different board states?

Score each card 1-10 and provide brief reasoning.

Return as JSON:
[
  {{"card_id": "...", "score": N, "reasoning": "..."}},
  ...
]
"""
    
    response = llm.invoke(prompt)
    return parse_scored_cards(response.content)
```

### 3. Updated Pipeline Flow

```python
async def recommend_cards(self, request: RecommendationRequest) -> list[Recommendation]:
    # 1. Analyze current state
    state = self.state_agent.analyze(request.deck)
    
    # 2. Get candidate cards from action space
    candidates = self.action_space_agent.search(
        investigator=request.investigator,
        capability_needs=state.identified_gaps,
        limit=50
    )
    
    # 3. Build doctrine context
    context = self.context_builder.build_selection_context(
        investigator=request.investigator,
        archetype=request.archetype,
        state=state,
        candidates=candidates,
        player_count=request.player_count,
        campaign=request.campaign
    )
    
    # 4. Score with LLM + doctrine context (soft evaluation)
    scored = await self.score_candidates_with_doctrine(context, candidates)
    
    # 5. Apply hard rules filter
    legal = self.rules_filter.filter(
        candidates=scored,
        investigator=request.investigator,
        deck=request.deck
    )
    
    # 6. Return top recommendations
    return legal[:request.limit]
```

## Benefits of This Architecture

| Aspect | Current | Proposed |
|--------|---------|----------|
| **Rules reliability** | LLM interpretation (can fail) | Hard Python filter (guaranteed) |
| **Doctrine flexibility** | Implicit in LLM weights | Explicit in `meta-trends.md`, easily updated |
| **Transparency** | Opaque scoring | Reasoning visible in LLM output |
| **Maintainability** | Change code to update strategy | Edit markdown to update doctrine |
| **New archetypes** | Requires code changes | Add section to `meta-trends.md` |

## Implementation Phases

### Phase 1: Hard Rules Filter
- Create `RulesFilter` class with pure Python constraint checking
- Integrate as final step before returning recommendations
- Remove rules interpretation from LLM prompts

### Phase 2: Context Builder
- Create `ContextBuilder` class
- Index `meta-trends.md` by section headers
- Build context assembly logic for different scenarios

### Phase 3: LLM Scoring with Doctrine
- Update orchestrator to use doctrine context
- Add structured output parsing for scored cards
- Implement reasoning extraction for transparency

### Phase 4: Validation & Testing
- Compare recommendation quality before/after
- Verify rules are never violated
- Test with edge cases (unusual investigators, weird deckbuilding rules)

## References

- AlphaZero paper: Legal move masking as hard constraint
- `meta-trends.md`: Existing comprehensive doctrine document
- Current subagent architecture in `orchestrator.py`
